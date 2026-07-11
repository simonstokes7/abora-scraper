import os
import re
import html
import sqlite3
import requests
import pandas as pd
from sqlalchemy import create_engine, text

# ==========================================
# CONFIGURATION PATHS
# ==========================================
DB_PATH = r"C:\Data_Projects\abora-scraper\uplifting_only.db"
LOCAL_MD = r"C:\Data_Projects\abora-scraper\Tracklists with Times.md"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def setup_database(engine):
    print("Initializing clean relational database schemas...")
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS tracks"))
        conn.execute(text("DROP TABLE IF EXISTS episodes"))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS episodes (
                episode_id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_name TEXT UNIQUE,
                air_date TEXT,
                soundcloud_url TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tracks (
                track_id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id INTEGER,
                track_number TEXT,
                start_time TEXT,
                artist TEXT,
                track_title TEXT,
                label TEXT,
                raw_line TEXT,
                FOREIGN KEY (episode_id) REFERENCES episodes (episode_id)
            )
        """))
        conn.commit()

def clean_track_metadata(artist, title, raw_label):
    """Clean tags and extract the actual record label from trailing bracketed text."""
    label = raw_label.strip() if raw_label else "Unknown Label"
    
    if "[" in title or "]" in title:
        full_tail = f"{title} {raw_label}".strip() if raw_label else title.strip()
        label_match = re.search(r"\[(.*?)\]", full_tail)
        if label_match:
            label = label_match.group(1).strip()
            title = re.sub(r"\[" + re.escape(label) + r"\]", "", full_tail).strip()
        else:
            title = full_tail
    
    title = re.sub(r"\[.*?PREMIERE.*?\]", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\(FAN FAVORITE.*?\)", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\(BREAKDOWN OF THE WEEK.*?\)", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip().rstrip("-").strip()
    
    if label == "Unknown Label" and raw_label:
        label = raw_label.strip()
        
    return artist.strip(), title, label

def parse_markdown(engine):
    if not os.path.exists(LOCAL_MD):
        print(f"Error: Missing source file '{LOCAL_MD}'")
        return False

    print(f"Reading local archive: {LOCAL_MD}")
    with open(LOCAL_MD, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current_episode_id = None
    episode_map = {}
    tracks_to_insert = []

    for line in lines:
        text_line = line.strip()
        if not text_line:
            continue

        if "Uplifting Only" in text_line and ("(" in text_line or "Episode" in text_line):
            try:
                date_match = re.search(r"\(([^)]+)\)", text_line)
                air_date = date_match.group(1).strip() if date_match else "Unknown Date"
                episode_name = re.sub(r"\([^)]+\)", "", text_line).strip().lstrip("# ").strip()

                if episode_name not in episode_map:
                    with engine.connect() as conn:
                        conn.execute(
                            text("INSERT OR IGNORE INTO episodes (episode_name, air_date) VALUES (:name, :date)"),
                            {"name": episode_name, "date": air_date}
                        )
                        conn.commit()
                        res = conn.execute(
                            text("SELECT episode_id FROM episodes WHERE episode_name = :name"),
                            {"name": episode_name}
                        ).fetchone()
                        if res:
                            episode_map[episode_name] = res[0]
                
                current_episode_id = episode_map.get(episode_name)
                continue
            except Exception:
                continue

        if any(x in text_line for x in ["Listen/Download", "Other Links:", "TRACKLIST:"]):
            continue

        if " - " in text_line and re.match(r"^\d+", text_line):
            try:
                num_match = re.match(r"^(\d+)", text_line)
                track_number = num_match.group(1) if num_match else ""
                clean_text = re.sub(r"^\d+[\.\s\-]+", "", text_line).strip()
                
                start_time = None
                time_match = re.search(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]:?", clean_text)
                if time_match:
                    start_time = time_match.group(1)
                    clean_text = re.sub(r"^\[\d{1,2}:\d{2}(?::\d{2})?\]:?\s*", "", clean_text).strip()

                parts = clean_text.split(" - ", 1)
                raw_artist = parts[0].strip()
                raw_tail = parts[1].strip() if len(parts) > 1 else ""

                artist, title, label = clean_track_metadata(raw_artist, raw_tail, "")

                tracks_to_insert.append({
                    "episode_id": current_episode_id,
                    "track_number": track_number,
                    "start_time": start_time,
                    "artist": artist,
                    "track_title": title,
                    "label": label,
                    "raw_line": text_line
                })
            except Exception:
                continue

    if tracks_to_insert:
        df = pd.DataFrame(tracks_to_insert)
        df.drop_duplicates(subset=["episode_id", "track_number", "artist", "track_title"], inplace=True)
        df.to_sql("tracks", con=engine, if_exists="append", index=False)
        print(f"Successfully cataloged {len(df)} tracks from Markdown source.")
        return True
    return False

def patch_soundcloud_links():
    print("Verifying live SoundCloud endpoints...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT episode_id, episode_name FROM episodes")
    rows = cursor.fetchall()

    for ep_id, ep_name in rows:
        digits = "".join(filter(str.isdigit, ep_name))
        if not digits:
            continue
        num = int(digits)

        if num == 438:
            cursor.execute("UPDATE episodes SET soundcloud_url = ? WHERE episode_id = ?", ("https://soundcloud.com/oriuplift/uponly-438-no-talking", ep_id))
            conn.commit()
            continue
        if num == 700:
            cursor.execute("UPDATE episodes SET soundcloud_url = ? WHERE episode_id = ?", ("https://soundcloud.com/oriuplift/uplifting-only-700", ep_id))
            conn.commit()
            continue

        url_variations = [
            f"https://soundcloud.com/oriuplift/uponly-{digits}",
            f"https://soundcloud.com/oriuplift/uponly-{num}",
            f"https://soundcloud.com/oriuplift/uplifting-only-{num}",
            f"https://soundcloud.com/oriuplift/uplifting-only-episode-{num}"
        ]

        for url in url_variations:
            try:
                res = requests.get(url, headers=HEADERS, timeout=3, allow_redirects=True, stream=True)
                if res.status_code == 200:
                    cursor.execute("UPDATE episodes SET soundcloud_url = ? WHERE episode_id = ?", (res.url, ep_id))
                    conn.commit()
                    break
            except Exception:
                continue
    conn.close()
    print("SoundCloud route mappings finalized.")

def recover_missing_times_from_soundcloud():
    print("Analyzing database for blank track timestamps...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT e.episode_id, e.episode_name, e.soundcloud_url 
        FROM episodes e
        LEFT JOIN tracks t ON e.episode_id = t.episode_id
        WHERE t.start_time IS NULL OR t.track_id IS NULL AND e.soundcloud_url IS NOT NULL
    """)
    missing_episodes = cursor.fetchall()

    if not missing_episodes:
        print("No missing tracklist times detected. Database looks solid!")
        conn.close()
        return

    print(f"Attempting tracklist recovery for {len(missing_episodes)} metadata-deficient episodes via SoundCloud...")

    for ep_id, ep_name, url in missing_episodes:
        try:
            response = requests.get(url, headers=HEADERS, timeout=5)
            if response.status_code != 200:
                continue
            
            html_content = response.text
            track_matches = re.findall(r"(\d+)[\.\s\-]+\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?[\s:]+([^-]+)-\s*([^[\n\r]+)(?:\[(.*?)\])?", html_content)

            if track_matches:
                cursor.execute("DELETE FROM tracks WHERE episode_id = ?", (ep_id,))
                
                seen_tracks = set()
                inserted_count = 0

                for match in track_matches:
                    tr_num = match[0].strip()
                    s_time = match[1].strip()
                    
                    raw_artist = match[2].strip()
                    raw_title = match[3].strip()
                    raw_label = match[4].strip() if match[4] else ""
                    
                    try:
                        artist_clean = raw_artist.encode('utf-8').decode('unicode-escape')
                        title_clean = raw_title.encode('utf-8').decode('unicode-escape')
                        label_clean = raw_label.encode('utf-8').decode('unicode-escape')
                    except Exception:
                        artist_clean, title_clean, label_clean = raw_artist, raw_title, raw_label

                    artist_decoded = html.unescape(artist_clean)
                    title_decoded = html.unescape(title_clean)
                    label_decoded = html.unescape(label_clean)
                    
                    artist, title, label = clean_track_metadata(artist_decoded, title_decoded, label_decoded)

                    track_fingerprint = f"{tr_num}-{artist}-{title}"
                    if track_fingerprint in seen_tracks:
                        continue
                        
                    seen_tracks.add(track_fingerprint)
                    inserted_count += 1

                    cursor.execute("""
                        INSERT INTO tracks (episode_id, track_number, start_time, artist, track_title, label, raw_line)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (ep_id, tr_num, s_time, artist, title, label, f"{tr_num}. [{s_time}]: {artist} - {title} [{label}]"))
                
                conn.commit()
                print(f"✓ Harvested {inserted_count} unique timestamped tracks for: {ep_name}")
            
        except Exception as e:
            print(f"Error scraping metadata parameters for {ep_name}: {e}")
            continue

    conn.close()
    print("SoundCloud backup metadata extraction sweep complete.")

if __name__ == "__main__":
    db_engine = create_engine(f"sqlite:///{DB_PATH}")
    
    setup_database(db_engine)
    if parse_markdown(db_engine):
        patch_soundcloud_links()
        recover_missing_times_from_soundcloud()
        print("\nData vault ingestion pipeline successfully completed!")