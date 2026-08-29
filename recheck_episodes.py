# recheck_episodes.py
"""
Retrospective Fix Checker
Ori corrects/finishes episode tracklists after they first air - most notably
adding per-track timestamps, sometimes weeks later, occasionally also fixing
a typo'd artist/title/label. update_episodes.py only ever inserts an episode
once, so it never picks those corrections up.

This script re-scrapes every SCRAPED episode (episode number strictly above
whatever the master spreadsheet covers - see episode_scraper.get_spreadsheet_
max_episode) that's still marked as fully untimed (every track has
duration = '--:--'), compares it against the current live tracklist, and if
anything differs (timestamps now present, track count changed, or any
track's text corrected), replaces that episode's tracks with the fresh data.

IMPORTANT: episodes at or below the spreadsheet's max episode number are
NEVER touched, even if all their tracks show '--:--' - most of the older
spreadsheet-derived episodes never got real per-track timestamps either, so
"untimed" alone is not a safe signal that an episode came from scraping. An
earlier version of this script ignored that distinction and overwrote ~76
curated historical episodes with re-scraped (differently formatted) data
before this guard was added - see episode_scraper.get_spreadsheet_max_episode.

Safe to re-run anytime: episodes with no change are left untouched, and once
a scraped episode has real timestamps it's no longer a candidate for
rechecking (Ori doesn't remove timestamps once added).

Usage: python recheck_episodes.py
"""

import sqlite3
import subprocess
import sys

import episode_scraper as es

DB_PATH = "uplifting_vault_v2.db"


def get_untimed_episodes(cursor, min_episode_id):
    """
    Episodes eligible for rechecking: strictly above min_episode_id (never touches
    spreadsheet-curated episodes - see get_spreadsheet_max_episode) AND not yet timed
    (once Ori adds real timestamps, the episode is no longer a candidate).
    """
    cursor.execute("""
        SELECT DISTINCT episode_id FROM tracks
        WHERE CAST(episode_id AS INTEGER) > ?
          AND episode_id NOT IN (SELECT DISTINCT episode_id FROM tracks WHERE duration != '--:--')
        ORDER BY CAST(episode_id AS INTEGER)
    """, (min_episode_id,))
    return [row[0] for row in cursor.fetchall()]


def get_current_tracks(cursor, ep_id):
    cursor.execute(
        "SELECT track_number, artist, track_title, label FROM tracks WHERE episode_id = ? ORDER BY track_number",
        (ep_id,)
    )
    return cursor.fetchall()


def has_changed(current, fresh_tracks):
    if len(current) != len(fresh_tracks):
        return True
    for (c_num, c_artist, c_title, c_label), (f_num, f_seconds, f_artist, f_title, f_label) in zip(current, fresh_tracks):
        if f_seconds is not None:
            return True  # timestamps newly available
        if (c_artist, c_title, c_label) != (f_artist, f_title, f_label or "Independent"):
            return True
    return False


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    spreadsheet_max = es.get_spreadsheet_max_episode()
    print(f"Spreadsheet covers up to episode {spreadsheet_max} - only scraped episodes above that are eligible for rechecking.")

    candidate_ids = get_untimed_episodes(cursor, spreadsheet_max)
    if not candidate_ids:
        print("No untimed scraped episodes in the database - nothing to recheck.")
        conn.close()
        return

    print(f"Rechecking {len(candidate_ids)} untimed episode(s): {', '.join(str(i) for i in candidate_ids)}")

    print(f"Fetching {es.TRACKLIST_PAGE} ...")
    text = es.fetch_tracklist_text()
    all_episodes = es.parse_all_episodes(text)

    fixed = []
    for ep_id in candidate_ids:
        ep_num = str(ep_id)
        data = all_episodes.get(ep_num)
        if not data:
            print(f"  Episode {ep_num}: not found on the live site (skipping)")
            continue

        cursor.execute("SELECT soundcloud_url FROM episodes WHERE episode_id = ?", (ep_id,))
        row = cursor.fetchone()
        soundcloud_url = row[0] if row else f"https://soundcloud.com/oriuplift/uponly-{ep_num.zfill(3)}"

        current = get_current_tracks(cursor, ep_id)
        fresh_tracks = data['tracks']

        if not has_changed(current, fresh_tracks):
            continue

        rendered = es.build_listen_buttons(fresh_tracks, soundcloud_url)
        cursor.execute("DELETE FROM tracks WHERE episode_id = ?", (ep_id,))
        for (track_num, seconds, artist, title, label), (duration, btn_html) in zip(fresh_tracks, rendered):
            cursor.execute(
                "INSERT INTO tracks (episode_id, track_number, duration, artist, track_title, label, listen_button) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ep_id, track_num, duration, artist, title, label or "Independent", btn_html)
            )

        timed = sum(1 for t in fresh_tracks if t[1] is not None)
        detail = f"now has {timed} real timestamps" if timed else f"track count/content changed ({len(current)} -> {len(fresh_tracks)})"
        print(f"  Episode {ep_num}: UPDATED - {detail}")
        fixed.append(ep_num)

    if not fixed:
        print("Checked all untimed episodes - no changes found on the site yet.")
        conn.close()
        return

    conn.commit()
    print(f"\n{len(fixed)} episode(s) updated: {', '.join(fixed)}")

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
