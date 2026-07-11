import re
import os
import pandas as pd
from sqlalchemy import create_engine, text

LOCAL_MD = r"C:\Data_Projects\abora-scraper\Tracklists with Times.md"

def setup_database(engine):
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

def parse_markdown_with_times():
    if not os.path.exists(LOCAL_MD):
        print(f"Error: Could not find '{LOCAL_MD}'.")
        return

    print(f"Reading local markdown file: {LOCAL_MD}...")
    with open(LOCAL_MD, "r", encoding="utf-8") as f:
        lines = f.readlines()

    engine = create_engine("sqlite:///C:/Data_Projects/abora-scraper/uplifting_only.db")
    setup_database(engine)

    current_episode_id = None
    episode_map = {}
    tracks_to_insert = []

    print(f"Parsing {len(lines)} lines for fixed timestamp pattern...")

    for line in lines:
        text_line = line.strip()
        if not text_line:
            continue

        # 1. MATCH EPISODE HEADER
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

        # 2. MATCH TRACK LINE (Handles optional hours and the trailing colon)
        if " - " in text_line and re.match(r"^\d+", text_line):
            try:
                num_match = re.match(r"^(\d+)", text_line)
                track_number = num_match.group(1) if num_match else ""
                
                clean_text = re.sub(r"^\d+[\.\s\-]+", "", text_line).strip()
                
                # UPDATED REGEX: Matches [0:00:33]: or [00:00]: or [00:00] optionally followed by a colon
                start_time = None
                time_match = re.search(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]:?", clean_text)
                if time_match:
                    start_time = time_match.group(1)
                    # Strip the entire timestamp block including any trailing colon and trailing spaces
                    clean_text = re.sub(r"^\[\d{1,2}:\d{2}(?::\d{2})?\]:?\s*", "", clean_text).strip()

                # Extract trailing Record Label
                label = "Unknown Label"
                label_match = re.search(r"\[(.*?)\]\s*$", clean_text)
                if label_match:
                    label = label_match.group(1).strip()
                    clean_text = re.sub(r"\[(.*?)\]\s*$", "", clean_text).strip()

                # Split out Artist and Title
                parts = clean_text.split(" - ", 1)
                artist = parts[0].strip()
                track_title = parts[1].strip()

                tracks_to_insert.append({
                    "episode_id": current_episode_id,
                    "track_number": track_number,
                    "start_time": start_time,
                    "artist": artist,
                    "track_title": track_title,
                    "label": label,
                    "raw_line": text_line
                })
            except Exception:
                continue

    if tracks_to_insert:
        df = pd.DataFrame(tracks_to_insert)
        df.drop_duplicates(subset=["episode_id", "track_number", "artist", "track_title"], inplace=True)
        
        print(f"Streaming {len(df)} tracks into the database...")
        df.to_sql("tracks", con=engine, if_exists="append", index=False)
        print("\nSUCCESS! Re-built database with confirmed timestamps extracted.")
    else:
        print("Parsing anomaly. Check file contents.")

if __name__ == "__main__":
    parse_markdown_with_times()