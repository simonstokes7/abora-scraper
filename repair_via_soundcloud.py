import os
import time
import sqlite3
import requests
from urllib.parse import quote_plus

DB_NAME = "uplifting_only.db"

def initialize_schema_extensions(cursor):
    """
    Safely adds the track_link column to the tracks table if it doesn't already exist.
    """
    try:
        cursor.execute("ALTER TABLE tracks ADD COLUMN track_link TEXT;")
        print("Database architecture updated: Added 'track_link' column.")
    except sqlite3.OperationalError:
        # The column already exists, which is perfect
        pass

def search_soundcloud_metadata(track_title):
    time.sleep(1.5)  # 1.5-second pacing delay to respect endpoints and avoid bans
    encoded_query = quote_plus(track_title)
    target_url = f"https://soundcloud.com/oembed?url=https://soundcloud.com/search?q={encoded_query}&format=json"
    
    try:
        response = requests.get(target_url, timeout=10)
        if response.status_code == 200:
            payload = response.json()
            return payload.get("provider_url", "https://soundcloud.com")
    except requests.exceptions.RequestException as e:
        print(f"Pacing Alert: Network connection bypassed for: {track_title}. Error: {e}")
    
    return None

def run_metadata_repair_pipeline():
    if not os.path.exists(DB_NAME):
        print(f"Database {DB_NAME} not found.")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Ensure the destination column exists
    initialize_schema_extensions(cursor)
    
    # 2. Only pull tracks that haven't been processed yet (where track_link is missing)
    try:
        cursor.execute("""
            SELECT track_id, artist, track_title 
            FROM tracks 
            WHERE track_link IS NULL OR track_link = ''
        """)
        unprocessed_tracks = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Query error: {e}")
        conn.close()
        return

    print(f"Found {len(unprocessed_tracks)} records requiring enrichment.")
    
    # 3. Process a safe batch of 10 tracks per run to watch it work
    for track_id, artist, track_title in unprocessed_tracks[:10]: 
        combined_query = f"{artist} - {track_title}"
        print(f"Enriching: {combined_query}")
        
        track_url = search_soundcloud_metadata(combined_query)
        if track_url:
            cursor.execute("""
                UPDATE tracks 
                SET track_link = ? 
                WHERE track_id = ?
            """, (track_url, track_id))
            conn.commit()
            print(f" -> Saved to database: {track_url}")
                
    conn.close()
    print("\nBatch processing commit completed successfully.")

if __name__ == "__main__":
    run_metadata_repair_pipeline()