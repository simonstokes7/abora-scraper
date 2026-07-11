import sqlite3
import time
import requests

DB_PATH = r"C:\Data_Projects\abora-scraper\uplifting_only.db"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def repair_400_series():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Target just the 400 series episodes to see if they fix up cleanly
    cursor.execute("SELECT episode_id, episode_name FROM episodes WHERE episode_name LIKE '%438%' OR episode_name LIKE '%445%' OR episode_name LIKE '%463%'")
    rows = cursor.fetchall()

    print(f"Verifying live SoundCloud links for target episodes...")

    for ep_id, ep_name in rows:
        digits = "".join(filter(str.isdigit, ep_name))
        if not digits:
            continue
        num = int(digits)

        # The variations Ori Uplift actually uses across different years
        url_variations = [
            f"https://soundcloud.com/oriuplift/uplifting-only-{num}",
            f"https://soundcloud.com/oriuplift/uplifting-only-episode-{num}",
            f"https://soundcloud.com/oriuplift/uponly-{digits}",
            f"https://soundcloud.com/oriuplift/uponly-{num}"
        ]

        for url in url_variations:
            try:
                # stream=True fetches just the headers instantly to see if the page exists
                res = requests.get(url, headers=HEADERS, timeout=5, allow_redirects=True, stream=True)
                if res.status_code == 200:
                    real_live_url = res.url  # Captures the actual working redirect destination!
                    cursor.execute(
                        "UPDATE episodes SET soundcloud_url = ? WHERE episode_id = ?",
                        (real_live_url, ep_id)
                    )
                    conn.commit()
                    print(f"✓ Found exact live link for Ep {num}: {real_live_url}")
                    break
            except Exception:
                continue
        time.sleep(0.5)

    conn.close()
    print("\nTarget patch complete!")

if __name__ == "__main__":
    repair_400_series()