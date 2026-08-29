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

Usage: python update_episodes.py
"""

import re
import sqlite3
import subprocess
import sys

import pandas as pd
import requests
from bs4 import BeautifulSoup

DB_PATH = "uplifting_vault_v2.db"
TRACKLIST_PAGE = "https://www.abora-recordings.com/uplifting-only-tracklists"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

WORLD_PREMIERE_RE = re.compile(r'\s*\[WORLD PREMIERE\]\s*$', re.IGNORECASE)
BRACKET_TAIL_RE = re.compile(r'\s*\[([^\[\]]+)\]\s*$')
EXT_ORIG_SUFFIX_RE = re.compile(r'\s*\((?:Extended|Original) Mix\)\s*$', re.IGNORECASE)
HEADER_RE = re.compile(r'^Uplifting Only (\d+)\b.*$', re.MULTILINE)
TRACK_RE = re.compile(r'^(\d+)\.[ \t]*(.*?)[ \t]*\n+([^\n]+?)\s*$', re.MULTILINE)


def clean_ws(s):
    return re.sub(r'\s+', ' ', s.replace('\xa0', ' ')).strip()


def parse_track_line(line):
    line = clean_ws(line)
    line = WORLD_PREMIERE_RE.sub('', line)
    label = None
    m = BRACKET_TAIL_RE.search(line)
    if m:
        label = clean_ws(m.group(1))
        line = line[:m.start()].rstrip()
    artist, _, title = line.partition(' - ')
    artist = clean_ws(artist)
    title = EXT_ORIG_SUFFIX_RE.sub('', clean_ws(title)).strip()
    return artist, title, label


def parse_embedded_date(header_text):
    tokens = re.findall(r'[\(\[]([^\]\)]+)[\]\)]', header_text)
    for item in reversed(tokens):
        try:
            dt = pd.to_datetime(item.strip(), errors='raise')
            if pd.notna(dt):
                return dt.strftime('%Y-%m-%d')
        except Exception:
            pass
    return "Unknown"


def fetch_tracklist_text():
    print(f"Fetching {TRACKLIST_PAGE} ...")
    r = requests.get(TRACKLIST_PAGE, headers=HEADERS, timeout=20)
    r.encoding = 'utf-8'
    soup = BeautifulSoup(r.text, 'lxml')
    iframe = soup.find('iframe', src=re.compile(r'tracklists_with_times'))
    if not iframe:
        raise RuntimeError("Could not find the 'with times' tracklist iframe on the page — site layout may have changed.")
    iframe_url = iframe['src']
    if iframe_url.startswith('//'):
        iframe_url = 'https:' + iframe_url

    print(f"Fetching iframe content: {iframe_url} ...")
    r2 = requests.get(iframe_url, headers=HEADERS, timeout=30)
    r2.encoding = 'utf-8'
    return BeautifulSoup(r2.text, 'lxml').get_text('\n')


def parse_all_episodes(text):
    headers = list(HEADER_RE.finditer(text))
    episodes = {}
    for i, m in enumerate(headers):
        ep_num = m.group(1)
        start, end = m.start(), headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[start:end]
        tl_idx = block.find('TRACKLIST:')
        body = block[tl_idx:] if tl_idx != -1 else block
        tracks = [(int(tm.group(1)), tm.group(3).strip())
                  for tm in TRACK_RE.finditer(body) if ' - ' in tm.group(3)]
        episodes[ep_num] = {'header': m.group(0).strip(), 'tracks': tracks}
    return episodes


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(CAST(episode_id AS INTEGER)) FROM episodes")
    max_existing = cursor.fetchone()[0] or 0
    print(f"Current database has episodes up to {max_existing}.")

    text = fetch_tracklist_text()
    all_episodes = parse_all_episodes(text)
    new_ep_nums = sorted((n for n in all_episodes if int(n) > max_existing), key=int)

    if not new_ep_nums:
        print("No new episodes found on the site. Database is already up to date.")
        conn.close()
        return

    print(f"Found {len(new_ep_nums)} new episode(s): {', '.join(new_ep_nums)}")

    for ep_num in new_ep_nums:
        data = all_episodes[ep_num]
        header_text = clean_ws(data['header'])
        episode_name = f"Uplifting Only {ep_num}"
        air_date = parse_embedded_date(header_text)
        soundcloud_url = f"https://soundcloud.com/oriuplift/uponly-{ep_num.zfill(3)}"

        cursor.execute(
            "INSERT OR IGNORE INTO episodes (episode_id, episode_name, air_date, soundcloud_url) VALUES (?, ?, ?, ?)",
            (int(ep_num), episode_name, air_date, soundcloud_url)
        )

        btn_html = (
            f'<div class="d-flex align-items-center gap-1">'
            f'<button onclick="loadTrack(\'{soundcloud_url}\', 0)" class="btn btn-sm btn-outline-secondary text-nowrap flex-grow-1">▶ Play Mix</button>'
            f'<a href="{soundcloud_url}" target="_blank" class="btn btn-sm btn-dark flex-shrink-0" title="Open mix on SoundCloud" style="background: #ff5500; border: none;">☁️</a>'
            f'</div>'
        )

        count = 0
        for track_num, raw_line in data['tracks']:
            artist, title, label = parse_track_line(raw_line)
            if not artist or not title:
                print(f"  SKIPPED ep{ep_num} track {track_num}: could not parse '{raw_line}'")
                continue
            cursor.execute(
                "INSERT INTO tracks (episode_id, track_number, duration, artist, track_title, label, listen_button) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (int(ep_num), track_num, '--:--', artist, title, label or "Independent", btn_html)
            )
            count += 1
        print(f"  Episode {ep_num} ({air_date}): {count} tracks inserted")

    conn.commit()

    print("Recomputing leaderboards over the full track set...")
    tracks_df = pd.read_sql_query("SELECT artist, track_title FROM tracks", conn)

    top_artists = tracks_df[tracks_df['artist'].str.strip().str.lower() != '']['artist'].value_counts().head(50)
    artist_html = "".join([
        f"""<div onclick="filterBySearch('{a.replace("'", "\\'")}')" class="d-flex justify-content-between align-items-center mb-1 leaderboard-row">
            <span><strong>#{r}</strong> {a}</span>
            <span class="badge bg-light text-dark rounded-pill border count-badge">{c} plays</span>
        </div>""" for r, (a, c) in enumerate(top_artists.items(), 1)
    ])

    tracks_df['full_track'] = tracks_df['artist'].str.strip() + " - " + tracks_df['track_title'].str.strip()
    top_tracks = tracks_df[tracks_df['full_track'].str.strip() != '-']['full_track'].value_counts().head(50)
    track_html = "".join([
        f"""<div onclick="filterBySearch('{t.replace("'", "\\'")}')" class="d-flex justify-content-between align-items-center mb-1 leaderboard-row">
            <span class="text-truncate me-2"><strong>#{r}</strong> {t}</span>
            <span class="badge bg-light text-dark rounded-pill border count-badge flex-shrink-0">{c} plays</span>
        </div>""" for r, (t, c) in enumerate(top_tracks.items(), 1)
    ])

    cursor.execute("INSERT OR REPLACE INTO leaderboards (type, html_content) VALUES ('artists', ?)", (artist_html,))
    cursor.execute("INSERT OR REPLACE INTO leaderboards (type, html_content) VALUES ('tracks', ?)", (track_html,))
    conn.commit()
    conn.close()

    print("Rebuilding desktop dashboard...")
    subprocess.run([sys.executable, "dashboard_v2.py"], check=True)
    print("Rebuilding mobile app...")
    subprocess.run([sys.executable, "build_mobile_app.py"], check=True)

    print("\nDone. Review the changes, then publish with the 'Full Update' step in 'How to run.txt' "
          "(skip the 'python import_spreadsheet.py' line - that would overwrite this data from the stale spreadsheet).")


if __name__ == "__main__":
    main()
