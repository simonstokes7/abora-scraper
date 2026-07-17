# import_spreadsheet.py
"""
Data Ingestion Pipeline for Abora Recordings & Music Dashboard
Calculates track durations, pre-renders HTML snippets, and generates leaderboards.
Source of Truth: Ori's Master Tracklist Spreadsheet (Ori Uplift - Tracklists - excerpt.xlsx)
Target: SQLite Database (uplifting_vault_v2.db)
"""

import os
import sys
import logging
import sqlite3
import argparse
import re
import urllib.parse
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
    """Creates tables optimized for direct dashboard consumption."""
    logger.info(f"Initializing connection to target database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("DROP TABLE IF EXISTS tracks;")
    cursor.execute("DROP TABLE IF EXISTS episodes;")
    cursor.execute("DROP TABLE IF EXISTS leaderboards;")
    
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
            duration TEXT,
            artist TEXT,
            track_title TEXT,
            label TEXT,
            listen_button TEXT,
            FOREIGN KEY(episode_id) REFERENCES episodes(episode_id)
        );
    """)

    cursor.execute("""
        CREATE TABLE leaderboards (
            type TEXT PRIMARY KEY,
            html_content TEXT
        );
    """)
    
    conn.commit()
    return conn

def clean_string(value):
    val_str = str(value).strip()
    if val_str.lower() in ['nan', '#n/a', 'null', 'none', '', '#ref!']:
        return None
    return val_str

def parse_track_title(row):
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
    col_html = 'With times - Final code for webpage'
    if col_html in row and pd.notna(row[col_html]):
        html_content = str(row[col_html])
        match = re.search(r'href=["\'](https://soundcloud\.com/[^"\']+)["\']', html_content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None

def parse_seconds_string(time_str):
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
    col_html = 'With times - Final code for webpage'
    if col_html not in row or pd.isna(row[col_html]):
        return 0
    text_blob = str(row[col_html])
    
    url_time_pattern = rf'(?:<strong>)?{track_num}\.(?:</strong>)?\s*[^\n]*?href=["\'][^"\']*?[#&]t=(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?'
    url_match = re.search(url_time_pattern, text_blob, re.IGNORECASE)
    if url_match:
        h = int(url_match.group(1)) if url_match.group(1) else 0
        m = int(url_match.group(2)) if url_match.group(2) else 0
        s = int(url_match.group(3)) if url_match.group(3) else 0
        return h * 3600 + m * 60 + s

    num_pattern = rf'(?:<strong>)?{track_num}\.(?:</strong>)?\s*(\d{{1,2}}:\d{{2}}(?::\d{{2}})?)[^\n]*'
    num_match = re.search(num_pattern, text_blob, re.IGNORECASE)
    if num_match:
        return parse_seconds_string(num_match.group(1))
            
    return 0

def parse_seconds(time_val, row, track_num, artist, title):
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
                if h >= 4: is_corrupted_wall_clock = True
                else: calculated_seconds = h * 3600 + int(float(parts[1])) * 60 + int(float(parts[2]))
            elif len(parts) == 2:
                calculated_seconds = int(float(parts[0])) * 60 + int(float(parts[1]))
        except Exception:
            is_corrupted_wall_clock = True

    if is_corrupted_wall_clock or calculated_seconds == 0:
        return extract_fallback_from_webcode(row, track_num, artist, title)
    return calculated_seconds

def parse_embedded_date(text_value):
    if pd.isna(text_value):
        return None
    matches = re.findall(r'\(([^)]+)\)', str(text_value))
    if not matches:
        return None
    for candidate in reversed(matches):
        date_str = candidate.strip().replace('.', '').replace(',', '')
        if date_str.lower().startswith('sept'):
            date_str = re.sub(r'^sept', 'Sep', date_str, flags=re.IGNORECASE)
        try:
            parsed_dt = pd.to_datetime(date_str, errors='raise')
            if pd.notna(parsed_dt):
                return parsed_dt.strftime('%Y-%m-%d')
        except Exception:
            pass
        for fmt in ['%B %d %Y', '%b %d %Y']:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except Exception:
                pass
    return None

def import_excel_to_dashboard(excel_path, db_path):
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
    
    # Pre-parse structure lists
    parsed_tracks = []
    episodes_dict = {}
    
    current_episode_name = None
    current_air_date = "Unknown"
    current_soundcloud_url = None
    
    logger.info("Parsing spreadsheet lines and calculating layout values...")
    for idx, row in df.iterrows():
        episode_name = clean_string(row.get('Episode # / Set Code #'))
        track_val = row.get('Track')
        
        if not episode_name or pd.isna(track_val):
            continue
            
        if not episode_name.lower().startswith('uplifting only'):
            episode_name = f"Uplifting Only {episode_name}"
            
        try:
            track_num = int(float(str(track_val).strip()))
        except ValueError:
            continue
        
        if track_num == 0:
            current_episode_name = episode_name
            extracted_date = parse_embedded_date(row.get('Tracklist'))
            current_air_date = extracted_date if extracted_date else "Unknown"
            
            soundcloud_url = extract_soundcloud_url(row)
            if not soundcloud_url:
                url_num = episode_name.split(' ')[-1]
                soundcloud_url = f"https://soundcloud.com/oriuplift/uponly-{url_num.zfill(3)}"
            current_soundcloud_url = soundcloud_url
            
            episodes_dict[current_episode_name] = {
                "air_date": current_air_date,
                "soundcloud_url": current_soundcloud_url
            }
            continue

        artist = clean_string(row.get('Artist'))
        if not artist or artist == '0' or current_episode_name is None:
            continue

        title = parse_track_title(row)
        raw_timestamp = row['Official Show Timestampts']
        seconds = parse_seconds(raw_timestamp, row, track_num, artist, title)
        
        label = clean_string(row.get('Label')) or clean_string(row.get('Publisher (Label) - blue means either use labelcopy, or double check with labelcopy')) or "Independent"

        parsed_tracks.append({
            "episode_name": current_episode_name,
            "track_number": track_num,
            "artist": artist,
            "track_title": title,
            "label": label,
            "start_seconds": seconds
        })

    # Convert to DataFrame to process block calculations effortlessly
    tracks_df = pd.DataFrame(parsed_tracks)
    
    # Calculate durations
    tracks_df['next_seconds'] = tracks_df.groupby('episode_name')['start_seconds'].shift(-1)
    tracks_df['duration_seconds'] = tracks_df['next_seconds'] - tracks_df['start_seconds']
    
    # Generate formatting strings
    tracks_df['duration_str'] = tracks_df['duration_seconds'].apply(lambda s: f"{int(s)//60}:{int(s)%60:02d}" if pd.notna(s) and s > 0 else '--:--')
    
    def precompute_time_str(s):
        if s >= 3600: return f"{int(s)//3600}:{int(s)%3600//60:02d}:{int(s)%60:02d}"
        return f"{int(s)//60}:{int(s)%60:02d}" if s > 0 else '--:--'
    tracks_df['start_time_str'] = tracks_df['start_seconds'].apply(precompute_time_str)

    # Insert episode structures and map IDs
    cursor = conn.cursor()
    episode_ids = {}
    for ep_name, ep_data in episodes_dict.items():
        cursor.execute("""
            INSERT OR IGNORE INTO episodes (episode_name, air_date, soundcloud_url)
            VALUES (?, ?, ?)
        """, (ep_name, ep_data['air_date'], ep_data['soundcloud_url']))
        cursor.execute("SELECT episode_id FROM episodes WHERE episode_name = ?", (ep_name,))
        episode_ids[ep_name] = cursor.fetchone()[0]

    # Pre-render HTML button elements
    logger.info("Pre-rendering database dashboard layouts...")
    for _, trk in tracks_df.iterrows():
        ep_name = trk['episode_name']
        ep_id = episode_ids.get(ep_name)
        if not ep_id: continue
        
        url = episodes_dict[ep_name]['soundcloud_url']
        secs = int(trk['start_seconds'])
        t_str = trk['start_time_str']
        duration = trk['duration_str']
        
        lbl = f" @ {t_str}" if t_str != '--:--' else ""
        if secs == 0 and duration == '--:--':
            btn_html = f'<button onclick="loadTrack(\'{url}\', 0)" class="btn btn-sm btn-outline-secondary text-nowrap">▶ Play Mix</button>'
        else:
            btn_html = f'<button onclick="loadTrack(\'{url}\', {secs})" class="btn btn-sm btn-orange text-nowrap">▶ Play{lbl}</button>'

        cursor.execute("""
            INSERT INTO tracks (episode_id, track_number, duration, artist, track_title, label, listen_button)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ep_id, int(trk['track_number']), duration, trk['artist'], trk['track_title'], trk['label'], btn_html))

    # Pre-compute Leaderboards HTML fragments
    logger.info("Pre-compiling leaderboard widgets...")
    top_artists = tracks_df[tracks_df['artist'].str.strip().str.lower() != '']['artist'].value_counts().head(50)
    artist_html = "".join([
        f"""<div onclick="filterBySearch('{a.replace("'", "\\'")}')" class="d-flex justify-content-between align-items-center mb-1 leaderboard-row">
            <span><strong>#{r}</strong> {a}</span>
            <span class="badge bg-light text-dark rounded-pill border count-badge">{c} plays</span>
        </div>""" for r, (a, c) in enumerate(top_artists.items(), 1)
    ])
    
    tracks_df['full_track'] = tracks_df['artist'].str.strip() + " - " + tracks_df['track_title'].str.strip()
    top_tracks = tracks_df[tracks_df['full_track'].str.strip() != '-']['full_track'].value_counts().head(50)
    track_html = "".join([
        f"""<div onclick="filterBySearch('{t.replace("'", "\\'")}')" class="d-flex justify-content-between align-items-center mb-1 leaderboard-row">
            <span class="text-truncate me-2"><strong>#{r}</strong> {t}</span>
            <span class="badge bg-light text-dark rounded-pill border count-badge flex-shrink-0">{c} plays</span>
        </div>""" for r, (t, c) in enumerate(top_tracks.items(), 1)
    ])

    cursor.execute("INSERT OR REPLACE INTO leaderboards (type, html_content) VALUES ('artists', ?)", (artist_html,))
    cursor.execute("INSERT OR REPLACE INTO leaderboards (type, html_content) VALUES ('tracks', ?)", (track_html,))

    conn.commit()
    conn.close()
    logger.info("=== Heavy Loading Import Complete ===")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Import Ori's Master Tracklist Spreadsheet.")
    parser.add_argument('--excel', type=str, default='Ori Uplift - Tracklists - excerpt.xlsx', help='Path to Excel file')
    parser.add_argument('--db', type=str, default=r"C:\Data_Projects\abora-scraper\uplifting_vault_v2.db", help='Path to target SQLite DB')
    
    args = parser.parse_args()
    import_excel_to_dashboard(args.excel, args.db)