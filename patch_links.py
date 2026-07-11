import sqlite3

def inject_soundcloud_links():
    conn = sqlite3.connect("uplifting_only.db")
    cursor = conn.cursor()
    
    # 1. Add the soundcloud_url column if it doesn't exist yet
    try:
        cursor.execute("ALTER TABLE episodes ADD COLUMN soundcloud_url TEXT;")
        conn.commit()
        print("Added soundcloud_url column to episodes table.")
    except sqlite3.OperationalError:
        # Column already exists, which is perfectly fine
        print("soundcloud_url column already exists. Ready to update.")

    # 2. Pull all episodes to process them
    cursor.execute("SELECT episode_id, episode_name FROM episodes;")
    episodes = cursor.fetchall()
    
    updated_count = 0
    for ep_id, ep_name in episodes:
        # Extract the digits from the episode name (e.g., "Uplifting Only 001" -> "001")
        digits = "".join(filter(str.isdigit, ep_name))
        
        if digits:
            # Drop leading zeros if needed depending on SoundCloud's naming format (e.g., "001" -> "1" or keep "001")
            # Most SoundCloud tracks for UpOnly follow the standard slug pattern:
            episode_num = int(digits)
            sc_url = f"https://soundcloud.com/oriuplift/uplifting-only-{episode_num}"
            
            cursor.execute(
                "UPDATE episodes SET soundcloud_url = ? WHERE episode_id = ?;", 
                (sc_url, ep_id)
            )
            updated_count += 1

    conn.commit()
    conn.close()
    print(f"Successfully calculated and injected SoundCloud URLs for {updated_count} episodes!")

if __name__ == "__main__":
    inject_soundcloud_links()