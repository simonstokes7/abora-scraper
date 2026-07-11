import sqlite3

DB_PATH = r"C:\Data_Projects\abora-scraper\uplifting_only.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. Let's inspect what is currently sitting in the table
cursor.execute("SELECT episode_name, soundcloud_url FROM episodes WHERE episode_name LIKE '%438%'")
row = cursor.fetchone()
print(f"Current string in DB: {row}")

# 2. Force overwrite it with the direct, verified streaming track page
verified_url = "https://soundcloud.com/oriuplift/uponly-438-no-talking"

cursor.execute(
    "UPDATE episodes SET soundcloud_url = ? WHERE episode_name LIKE '%438%'",
    (verified_url,)
)
conn.commit()
print(f"✓ Successfully forced Episode 438 to: {verified_url}")

conn.close()