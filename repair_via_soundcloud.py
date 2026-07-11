import os
import time
import sqlite3
import requests
from urllib.parse import quote_plus

DB_NAME = "uplifting_only.db"

def search_soundcloud_metadata(track_title):
    time.sleep(1.5)  # Respectful pacing delay to protect connection
    encoded_query = quote_plus(track_title)
    target_url = f"https://soundcloud.com/oembed?url=https://soundcloud.com/search?q={encoded_query}&format=json"
    
    try:
        response = requests.get(target_url, timeout=10)
        if response.status_code == 200:
            payload = response.json()
            return {
                "enriched_title": payload.get("title", track_title),
                "provider_url": payload.get("provider_url", "https://soundcloud.com")
            }
    except requests.exceptions.RequestException as e:
        print(f"Pacing Alert: Connection bypassed for query: {track_title}. Error: {e}")
    
    return None

def run_metadata_repair_pipeline():
    if not os.path.exists(DB_NAME):
        print(f"Database {DB_NAME} not found.")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # query matched exactly to your 'tracks' table schema columns
    try:
        cursor.execute("SELECT track_id, artist, track_title FROM tracks")
        all_tracks = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Database schema mismatch error: {e}")
        conn.close()
        return

    print(f"Successfully connected to database. Found {len(all_tracks)} records to process.")
    
    # Testing with a small batch of 5 records to verify pipeline orchestration
    for track_id, artist, track_title in all_tracks[:5]: 
        combined_query = f"{artist} - {track_title}"
        print(f"Enriching: {combined_query}")
        
        result = search_soundcloud_metadata(combined_query)
        if result:
            print(f" -> Successfully matched target: {result['provider_url']}")
                
    conn.close()
    print("Batch processing pipeline verification completed.")

if __name__ == "__main__":
    run_metadata_repair_pipeline()