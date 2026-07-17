# import_spreadsheet.py
"""
Data Ingestion Pipeline for Abora Recordings & Music Dashboard
Source of Truth: Ori's Master Tracklist Spreadsheet (Ori Uplift - Tracklists - excerpt.xlsx)
Target: SQLite Database (uplifting_vault_v2.db)
"""

import os
import sys
import logging
import sqlite3
import argparse
import re
import pandas as pd
from datetime import time, datetime

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def initialize_database(db_path):
    """Ensures that the tracks layout matches the expected dashboard schema."""
    logger.info(f"Initializing connection to target database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("DROP TABLE IF EXISTS tracks;")
    cursor.execute("DROP TABLE IF EXISTS episodes;")
    
    cursor.execute("""
        CREATE TABLE episodes (
            episode_id INTEGER PRIMARY KEY AUTOINCREMENT,
            episode_name TEXT UNIQUE,
            air_date TEXT,
            soundcloud_url TEXT
        );
    """)
    
    cursor.execute("""
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY AUTOINCREMENT,
            episode_id INTEGER,
            track_number INTEGER,
            start_seconds INTEGER,
            artist TEXT,
            track_title TEXT,
            label TEXT,
            FOREIGN KEY(episode_id) REFERENCES episodes(episode_id)
        );
    """)
    conn.commit()
    return conn

def clean_string(value):
    """Sanitizes cells, removing whitespace and Excel errors like #N/A."""
    val_str = str(value).strip()
    if val_str.lower() in ['nan', '#n/a', 'null', 'none', '', '#ref!']:
        return None
    return val_str

def parse_track_title(row):
    """Resolves the clean track title using Ori's sheet hierarchy."""
    col_clean = 'Track Names w/out "Original"/"Extended"'
    if col_clean in row and pd.notna(row[col_clean]):
        cleaned = clean_string(row[col_clean])
        if cleaned:
            return cleaned

    col_next = 'Next Track'
    if col_next in row and pd.notna(row[col_next]):
        cleaned_next = clean_string(row[col_next])
        if cleaned_next:
            artist_prefix = clean_string(row.get('Artist', ''))
            if artist_prefix and artist_prefix in cleaned_next:
                split_parts = cleaned_next.split(' - ', 1)
                if len(split_parts) > 1:
                    return split_parts[1].strip()
            return cleaned_next
            
    return "Unknown Title"

def extract_soundcloud_url(row):
    """Scans Ori's webpage code block to extract the genuine embedded SoundCloud link."""
    col_html = 'With times - Final code for webpage'
    if col_html in row and pd.notna(row[col_html]):
        html_content = str(row[col_html])
        match = re.search(r'href=["\'](https://soundcloud\.com/[^"\']+)["\']', html_content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None

def parse_seconds_string(time_str):
    """Safely converts standard string timestamps into duration seconds."""
    if not time_str:
        return 0
    time_str = str(time_str).strip().replace('[', '').replace(']', '')
    try:
        parts = time_str.split(':')
        if len(parts) == 3:
            return int(float(parts[0])) * 3600 + int(float(parts[1])) * 60 + int(float(parts[2]))
        elif len(parts) == 2:
            return int(float(parts[0])) * 60 + int(float(parts[1]))
    except Exception:
        return 0
    return 0

def extract_fallback_from_webcode(row, track_num, artist, title):
    """Scans the manual text layout using structural HTML track number markers first."""
    col_html = 'With times - Final code for webpage'
    if col_html not in row or pd.isna(row[col_html]):
        return 0
        
    text_blob = str(row[col_html])
    
    # URL TIMING RESCUE: Look for a track line pattern that embeds a timestamp link
    # Matches patterns like href="...#t=14m54s" or href="...#t=74m" or href="...&t=420s"
    url_time_pattern = rf'(?:<strong>)?{track_num}\.(?:</strong>)?\s*[^\n]*?href=["\'][^"\']*?[#&]t=(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?'
    url_match = re.search(url_time_pattern, text_blob, re.IGNORECASE)
    if url_match:
        h = int(url_match.group(1)) if url_match.group(1) else 0
        m = int(url_match.group(2)) if url_match.group(2) else 0
        s = int(url_match.group(3)) if url_match.group(3) else 0
        if h or m or s:
            return h * 3600 + m * 60 + s

    # Text pattern variant match: <strong>2. </strong> 14:54
    num_pattern = rf'(?:<strong>)?{track_num}\.(?:</strong>)?\s*(\d{{1,2}}:\d{{2}}(?::\d{{2}})?)[^\n]*'
    num_match = re.search(num_pattern, text_blob, re.IGNORECASE)
    if num_match:
        return parse_seconds_string(num_match.group(1))

    # Alternate layout fallback using names if the track number structure isn't present
    if artist and title:
        clean_artist = re.escape(artist[:12])
        clean_title = re.escape(title[:12])
        
        pattern = rf'(\d{{1,2}}:\d{{2}}(?::\d{{2}})?)[^\n]*{clean_artist}.*{clean_title}'
        match = re.search(pattern, text_blob, re.IGNORECASE)
        if match:
            return parse_seconds_string(match.group(1))
            
        pattern_alt = rf'{clean_artist}.*{clean_title}[^\n]*(\d{{1,2}}:\d{{2}}(?::\d{{2}})?)'
        match_alt = re.search(pattern_alt, text_blob, re.IGNORECASE)
        if match_alt:
            return parse_seconds_string(match_alt.group(1))
        
    # Last resort index capture
    pattern_broad = r'(\d{1,2}:\d{2}(?::\d{2})?)'
    matches = re.findall(pattern_broad, text_blob)
    if matches and track_num <= len(matches):
        return parse_seconds_string(matches[track_num - 1])
            
    return 0

def parse_seconds(time_val, row, track_num, artist, title):
    """Evaluates type serialization and discards out-of-bounds wall-clock markers."""
    if pd.isna(time_val) or time_val == '':
        return extract_fallback_from_webcode(row, track_num, artist, title)
        
    calculated_seconds = 0
    is_corrupted_wall_clock = False

    if isinstance(time_val, time) or isinstance(time_val, datetime):
        if time_val.hour >= 4:  
            is_corrupted_wall_clock = True
        else:
            calculated_seconds = time_val.hour * 3600 + time_val.minute * 60 + time_val.second
            
    elif isinstance(time_val, (int, float)) and not isinstance(time_val, bool):
        if time_val < 1.0:
            total = int(round(time_val * 86400))
            if total >= 14400:  
                is_corrupted_wall_clock = True
            else:
                calculated_seconds = total
        else:
            calculated_seconds = int(time_val)
            
    else:
        time_str = str(time_val).strip()
        if ' ' in time_str:
            time_str = time_str.split(' ')[-1]
        try:
            parts = time_str.split(':')
            if len(parts) == 3:
                h = int(float(parts[0]))
                if h >= 4:
                    is_corrupted_wall_clock = True
                else:
                    calculated_seconds = h * 3600 + int(float(parts[1])) * 60 + int(float(parts[2]))
            elif len(parts) == 2:
                calculated_seconds = int(float(parts[0])) * 60 + int(float(parts[1]))
        except Exception:
            is_corrupted_wall_clock = True

    if is_corrupted_wall_clock or calculated_seconds == 0:
        return extract_fallback_from_webcode(row, track_num, artist, title)
        
    return calculated_seconds

def import_excel_to_dashboard(excel_path, db_path):
    """Reads the spreadsheet tab and runs clean batch inserts into SQLite."""
    if not os.path.exists(excel_path):
        logger.error(f"Spreadsheet file not found at path: {excel_path}")
        sys.exit(1)
        
    logger.info(f"Loading sheet 'UpOnly Tracklists' from {excel_path}...")
    try:
        df = pd.read_excel(excel_path, sheet_name='UpOnly Tracklists')
    except Exception as e:
        logger.error(f"Failed to parse Excel file: {str(e)}")
        sys.exit(1)
        
    conn = initialize_database(db_path)
    cursor = conn.cursor()
    
    inserted_count = 0
    skipped_count = 0
    episode_cache = {}
    
    for idx, row in df.iterrows():
        artist = clean_string(row.get('Artist'))
        episode_name = clean_string(row.get('Episode # / Set Code #'))
        
        if not artist or not episode_name or artist == '0' or row.get('Track') == 0:
            skipped_count += 1
            continue
            
        if not episode_name.lower().startswith('uplifting only'):
            episode_name = f"Uplifting Only {episode_name}"
            
        if episode_name not in episode_cache:
            soundcloud_url = extract_soundcloud_url(row)
            if not soundcloud_url:
                url_num = episode_name.split(' ')[-1]
                soundcloud_url = f"https://soundcloud.com/oriuplift/uponly-{url_num.zfill(3)}"
            
            air_date = clean_string(row.get('Date')) or "2026-06-18"
            
            cursor.execute("""
                INSERT OR IGNORE INTO episodes (episode_name, air_date, soundcloud_url)
                VALUES (?, ?, ?)
            """, (episode_name, air_date, soundcloud_url))
            
            cursor.execute("SELECT episode_id FROM episodes WHERE episode_name = ?", (episode_name,))
            episode_cache[episode_name] = cursor.fetchone()[0]
            
        ep_id = episode_cache[episode_name]
        
        track_num = int(row.get('Track', 1))
        title = parse_track_title(row)
        
        raw_timestamp = row['Official Show Timestampts']
        seconds = parse_seconds(raw_timestamp, row, track_num, artist, title)
        
        label = clean_string(row.get('Label'))
        if not label:
            label = clean_string(row.get('Publisher (Label) - blue means either use labelcopy, or double check with labelcopy'))
        if not label:
            label = "Independent"

        cursor.execute("""
            INSERT INTO tracks (episode_id, track_number, start_seconds, artist, track_title, label)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ep_id, track_num, seconds, artist, title, label))
        inserted_count += 1

    conn.commit()
    conn.close()
    
    logger.info("=== Import Process Summary ===")
    logger.info(f"Processed Rows Loaded: {len(df)}")
    logger.info(f"Successfully Inserted: {inserted_count} tracks")
    logger.info(f"Skipped Placeholder: {skipped_count} rows")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Import Ori's Master Tracklist Spreadsheet.")
    parser.add_argument('--excel', type=str, default='Ori Uplift - Tracklists - excerpt.xlsx', help='Path to Excel file')
    parser.add_argument('--db', type=str, default=r"C:\Data_Projects\abora-scraper\uplifting_vault_v2.db", help='Path to target SQLite DB')
    
    args = parser.parse_args()
    import_excel_to_dashboard(args.excel, args.db)