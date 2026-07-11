import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text

# Target the direct iframe endpoint discovered in the network tools
IFRAME_URL = "https://www.abora-recordings.com/uponly_tracklists_no_times_no_links_for_iframe_1588535752.html"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def setup_database(engine):
    """Creates the final schema including explicit web media link mappings."""
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS tracks"))
        conn.execute(text("DROP TABLE IF EXISTS episodes"))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS episodes (
                episode_id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_name TEXT UNIQUE,
                air_date TEXT,
                soundcloud_url TEXT,
                youtube_url TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tracks (
                track_id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id INTEGER,
                track_number TEXT,
                artist TEXT,
                track_title TEXT,
                label TEXT,
                raw_line TEXT,
                FOREIGN KEY (episode_id) REFERENCES episodes (episode_id)
            )
        """))
        conn.commit()

def run_master_scraper():
    print("Connecting directly to Abora's internal iframe database...")
    response = requests.get(IFRAME_URL, headers=HEADERS)
    
    if response.status_code != 200:
        print(f"Failed to access source endpoint. Status code: {response.status_code}")
        return

    print("Data stream established. Parsing HTML source nodes...")
    soup = BeautifulSoup(response.text, "lxml")
    
    engine = create_engine("sqlite:///uplifting_only.db")
    setup_database(engine)

    current_episode_id = None
    episode_map = {}
    tracks_to_insert = []

    # Look through the paragraphs inside the iframe document
    paragraphs = soup.find_all(["p", "div"])
    print(f"Scanning {len(paragraphs)} raw lines for metadata and streaming elements...")

    for p in paragraphs:
        text_line = p.get_text().strip()
        if not text_line:
            continue

        # 1. PARSE EPISODE LINES & EXTRACTION OF EMBEDDED MEDIA LINKS
        if "Uplifting Only" in text_line and ("(" in text_line or "Episode" in text_line):
            try:
                # Extract the air date out of the brackets
                date_match = re.search(r"\(([^)]+)\)", text_line)
                air_date = date_match.group(1).strip() if date_match else "Unknown Date"
                episode_name = re.sub(r"\([^)]+\)", "", text_line).strip()

                # Search the text element for hyperlinked audio streams
                soundcloud_url = None
                youtube_url = None
                
                # Check adjacent or child anchors for link attributes
                anchors = p.find_all("a", href=True)
                for a in anchors:
                    href = a["href"]
                    if "soundcloud.com" in href:
                        soundcloud_url = href
                    elif "youtube.com" in href or "youtu.be" in href:
                        youtube_url = href

                if episode_name not in episode_map:
                    with engine.connect() as conn:
                        conn.execute(
                            text("""
                                INSERT OR IGNORE INTO episodes (episode_name, air_date, soundcloud_url, youtube_url) 
                                VALUES (:name, :date, :sc, :yt)
                            """),
                            {"name": episode_name, "date": air_date, "sc": soundcloud_url, "yt": youtube_url}
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

        # 2. PARSE TRACK DETAILS
        if " - " in text_line and re.match(r"^\d+", text_line):
            try:
                num_match = re.match(r"^(\d+)", text_line)
                track_number = num_match.group(1) if num_match else ""
                
                clean_text = re.sub(r"^\d+[\.\s\-]+", "", text_line).strip()
                
                label = "Unknown Label"
                label_match = re.search(r"\[(.*?)\]\s*$", clean_text)
                if label_match:
                    label = label_match.group(1).strip()
                    clean_text = re.sub(r"\[(.*?)\]\s*$", "", clean_text).strip()

                parts = clean_text.split(" - ", 1)
                artist = parts[0].strip()
                track_title = parts[1].strip()

                tracks_to_insert.append({
                    "episode_id": current_episode_id,
                    "track_number": track_number,
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
        
        print("Writing updated, media-linked tables to SQLite database...")
        df.to_sql("tracks", con=engine, if_exists="append", index=False)
        print("\nSUCCESS! Complete relational music archive compiled successfully.")
    else:
        print("Verification error. No tracks recorded.")

if __name__ == "__main__":
    run_master_scraper()