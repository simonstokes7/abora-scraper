import os
import time
import sqlite3
import requests
from urllib.parse import quote_plus

DB_NAME = "uplifting_only.db"

def search_soundcloud_metadata(track_title):
    time.sleep(1.5)  # 1.5-second pacing delay
    encoded_query = quote_plus(track_title)
    target_url = f"https://soundcloud.com/oembed?url=https://soundcloud.com/search?q={encoded_query}&format=json"
    
    try:
        response = requests.get(target_url, timeout=10)
        if response.status_code == 200:
            payload = response.json()
            provider_url = payload.get("provider_url", "https://soundcloud.com")
            
            # CRITICAL FIX: If the API just sends back the generic main homepage link, 
            # it means a specific track player target wasn't found. Let it skip.
            if provider_url.strip("/") == "https://soundcloud.com":
                print(f" -> Notice: Generic homepage returned for specific string: '{track_title}'. Skipping placeholder URL.")
                return None
                
            return provider_url
    except requests.exceptions.RequestException as e:
        print(f"Pacing Alert: Network connection bypassed for: {track_title}. Error: {e}")
    
    return None

def run_metadata_repair_pipeline():
    if not os.path.exists(DB_NAME):
        print(f"Database {DB_NAME} not found.")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Process only records that don't have a valid stream track URL attached
    try:
        cursor.execute("""
            SELECT track_id, artist, track_title 
            FROM tracks 
            WHERE track_link IS NULL OR track_link = '' OR track_link = 'https://soundcloud.com'
        """)
        unprocessed_tracks = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Query error: {e}")
        conn.close()
        return

    print(f"Found {len(unprocessed_tracks)} records requiring evaluation/correction.")
    
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
        else:
            # Explicitly mark compilation entries so they don't block subsequent script runs
            cursor.execute("""
                UPDATE tracks 
                SET track_link = 'N/A - Compilation Show' 
                WHERE track_id = ?
            """, (track_id,))
            conn.commit()
                
    conn.close()
    print("\nBatch update processing execution completed successfully.")

if __name__ == "__main__":
    run_metadata_repair_pipeline()