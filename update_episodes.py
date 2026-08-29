# update_episodes.py
"""
Incremental Episode Updater
Scrapes the latest tracklists directly from Abora Recordings and inserts any
episodes newer than what's already in uplifting_vault_v2.db, then rebuilds
the desktop and mobile dashboards.

Source of truth for new episodes: the spreadsheet ("Ori Uplift - Tracklists -
excerpt.xlsx") is no longer being updated, so this is the primary path for
adding new episodes going forward. Safe to re-run anytime: episodes already
in the database are left untouched and never re-inserted.

Newly-aired episodes almost never have per-track timestamps yet (Ori adds
those retroactively, sometimes weeks later) - see recheck_episodes.py, which
re-scrapes already-inserted episodes to pick up those later corrections.

Usage: python update_episodes.py
"""

import sqlite3
import subprocess
import sys

import episode_scraper as es

DB_PATH = "uplifting_vault_v2.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(CAST(episode_id AS INTEGER)) FROM episodes")
    max_existing = cursor.fetchone()[0] or 0
    print(f"Current database has episodes up to {max_existing}.")

    print(f"Fetching {es.TRACKLIST_PAGE} ...")
    text = es.fetch_tracklist_text()
    all_episodes = es.parse_all_episodes(text)
    new_ep_nums = sorted((n for n in all_episodes if int(n) > max_existing), key=int)

    if not new_ep_nums:
        print("No new episodes found on the site. Database is already up to date.")
        conn.close()
        return

    print(f"Found {len(new_ep_nums)} new episode(s): {', '.join(new_ep_nums)}")

    for ep_num in new_ep_nums:
        data = all_episodes[ep_num]
        header_text = es.clean_ws(data['header'])
        episode_name = f"Uplifting Only {ep_num}"
        air_date = es.parse_embedded_date(header_text)
        soundcloud_url = f"https://soundcloud.com/oriuplift/uponly-{ep_num.zfill(3)}"

        cursor.execute(
            "INSERT OR IGNORE INTO episodes (episode_id, episode_name, air_date, soundcloud_url) VALUES (?, ?, ?, ?)",
            (int(ep_num), episode_name, air_date, soundcloud_url)
        )

        tracks = data['tracks']
        rendered = es.build_listen_buttons(tracks, soundcloud_url)
        for (track_num, seconds, artist, title, label), (duration, btn_html) in zip(tracks, rendered):
            cursor.execute(
                "INSERT INTO tracks (episode_id, track_number, duration, artist, track_title, label, listen_button) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (int(ep_num), track_num, duration, artist, title, label or "Independent", btn_html)
            )
        timed = sum(1 for t in tracks if t[1] is not None)
        note = f" ({timed} with real timestamps)" if timed else ""
        print(f"  Episode {ep_num} ({air_date}): {len(tracks)} tracks inserted{note}")

    conn.commit()

    print("Recomputing leaderboards over the full track set...")
    es.recompute_leaderboards(cursor, conn)
    conn.close()

    print("Rebuilding desktop dashboard...")
    subprocess.run([sys.executable, "dashboard_v2.py"], check=True)
    print("Rebuilding mobile app...")
    subprocess.run([sys.executable, "build_mobile_app.py"], check=True)

    print("\nDone. Review the changes, then publish with the 'Full Update' step in 'How to run.txt' "
          "(skip the 'python import_spreadsheet.py' line - that would overwrite this data from the stale spreadsheet).")


if __name__ == "__main__":
    main()
