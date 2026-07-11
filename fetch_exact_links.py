import re
import sqlite3
import time
import requests
from bs4 import BeautifulSoup

DB_PATH = r"C:\Data_Projects\abora-scraper\uplifting_only.db"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def repair_soundcloud_links():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all episodes that need updating
    cursor.execute("SELECT episode_id, episode_name FROM episodes")
    rows = cursor.fetchall()

    print(f"Scanning {len(rows)} episodes for exact live web links...")

    for ep_id, ep_name in rows:
        # Extract digits to find the true episode code
        digits = "".join(filter(str.isdigit, ep_name))
        if not digits:
            continue

        episode_num = int(digits)

        # Target the explicit dedicated episode page directly
        target_url = f"https://www.abora-recordings.com/uponly-{episode_num}"

        try:
            response = requests.get(target_url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "lxml")

                # Search the page structure for standard anchor links pointing to SoundCloud
                found_url = None
                for anchor in soup.find_all("a", href=True):
                    href = anchor["href"]
                    if "soundcloud.com" in href and "oriuplift" in href:
                        found_url = href
                        break

                if found_url:
                    cursor.execute(
                        "UPDATE episodes SET soundcloud_url = ? WHERE episode_id = ?",
                        (found_url, ep_id),
                    )
                    conn.commit()
                    print(f"✓ Updated Episode {episode_num} -> {found_url}")
                else:
                    print(
                        f"✗ Page loaded for {episode_num}, but no SoundCloud link found."
                    )
            else:
                print(
                    f"✗ Could not reach page for Episode {episode_num} (Status {response.status_code})"
                )

            # Polite delay to keep network requests stable
            time.sleep(1)

        except Exception as e:
            print(f"⚠️ Connection error on Episode {episode_num}: {e}")
            continue

    conn.close()
    print("\nLink validation patch complete!")


if __name__ == "__main__":
    repair_soundcloud_links()