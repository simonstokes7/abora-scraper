# episode_scraper.py
"""
Shared scraping/parsing helpers for update_episodes.py and recheck_episodes.py.

Fetches the "with times" tracklist iframe from Abora Recordings and parses it
into per-episode track lists. Ori adds per-track timestamps retroactively
(often weeks after an episode airs), so the same episode can be parsed twice
with different results: first with no timestamps (duration '--:--', a plain
"Play Mix" button), later with real per-track start times once he fixes it up
(a "Play @ h:mm:ss" button that seeks the mix, matching the format
import_spreadsheet.py produces from the master spreadsheet).
"""

import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

TRACKLIST_PAGE = "https://www.abora-recordings.com/uplifting-only-tracklists"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

WORLD_PREMIERE_RE = re.compile(r'\s*\[WORLD PREMIERE\]\s*$', re.IGNORECASE)
BRACKET_TAIL_RE = re.compile(r'\s*\[([^\[\]]+)\]\s*$')
EXT_ORIG_SUFFIX_RE = re.compile(r'\s*\((?:Extended|Original) Mix\)\s*$', re.IGNORECASE)
HEADER_RE = re.compile(r'^Uplifting Only (\d+)\b.*$', re.MULTILINE)

# "12. [1:02:30]: PREFIX TAG: Artist - Title [Label]" (timestamp and prefix are each optional,
# and in practice never both appear on the same line, but the pattern tolerates it either way).
TRACK_LINE_RE = re.compile(
    r"^(\d+)\.\s*"
    r"(?:\[(\d{1,2}:\d{2}(?::\d{2})?)\]:\s*)?"
    r"(?:([A-Z0-9][A-Z0-9 &'\-]*):\s*)?"
    r"(.+)$",
    re.MULTILINE
)


def clean_ws(s):
    return re.sub(r'\s+', ' ', s.replace('\xa0', ' ')).strip()


def parse_track_line(line):
    """Split a raw 'Artist - Title [Label] [WORLD PREMIERE]' line into (artist, title, label)."""
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


def timestamp_to_seconds(ts):
    if not ts:
        return None
    parts = [int(p) for p in ts.split(':')]
    if len(parts) == 3:
        h, m, s = parts
    else:
        h = 0
        m, s = parts
    return h * 3600 + m * 60 + s


def fetch_tracklist_text():
    """Fetch and flatten the live 'with times' tracklist iframe to one clean line per track."""
    r = requests.get(TRACKLIST_PAGE, headers=HEADERS, timeout=20)
    r.encoding = 'utf-8'
    soup = BeautifulSoup(r.text, 'lxml')
    iframe = soup.find('iframe', src=re.compile(r'tracklists_with_times'))
    if not iframe:
        raise RuntimeError("Could not find the 'with times' tracklist iframe on the page — site layout may have changed.")
    iframe_url = iframe['src']
    if iframe_url.startswith('//'):
        iframe_url = 'https:' + iframe_url

    r2 = requests.get(iframe_url, headers=HEADERS, timeout=30)
    r2.encoding = 'utf-8'
    soup2 = BeautifulSoup(r2.text, 'lxml')
    for br in soup2.find_all('br'):
        br.replace_with('\n')
    # No separator: inline tags (<a>, <strong>) must NOT split a track onto multiple lines.
    return soup2.get_text('')


def parse_all_episodes(text):
    """
    Returns {episode_number_str: {'header': str, 'tracks': [(track_num, seconds_or_None, artist, title, label)]}}
    """
    headers = list(HEADER_RE.finditer(text))
    episodes = {}
    for i, m in enumerate(headers):
        ep_num = m.group(1)
        start = m.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[start:end]
        tl_idx = block.find('TRACKLIST:')
        body = block[tl_idx:] if tl_idx != -1 else block

        tracks = []
        for tm in TRACK_LINE_RE.finditer(body):
            track_num = int(tm.group(1))
            seconds = timestamp_to_seconds(tm.group(2))
            rest = tm.group(4)
            if ' - ' not in rest:
                continue
            artist, title, label = parse_track_line(rest)
            if not artist or not title:
                continue
            tracks.append((track_num, seconds, artist, title, label))

        episodes[ep_num] = {'header': m.group(0).strip(), 'tracks': tracks}
    return episodes


def build_listen_buttons(tracks, soundcloud_url):
    """
    Given an episode's [(track_num, seconds_or_None, artist, title, label)] tracks (in order) and
    its SoundCloud URL, returns a parallel list of (duration_str, listen_button_html), matching
    import_spreadsheet.py's pre-rendered format exactly (including the timed "Play @ h:mm:ss"
    variant when real per-track start times are available).
    """
    results = []
    for idx, (track_num, seconds, artist, title, label) in enumerate(tracks):
        next_seconds = tracks[idx + 1][1] if idx + 1 < len(tracks) else None

        if seconds is None:
            duration = '--:--'
            btn_html = (
                f'<div class="d-flex align-items-center gap-1">'
                f'<button onclick="loadTrack(\'{soundcloud_url}\', 0)" class="btn btn-sm btn-outline-secondary text-nowrap flex-grow-1">▶ Play Mix</button>'
                f'<a href="{soundcloud_url}" target="_blank" class="btn btn-sm btn-dark flex-shrink-0" title="Open mix on SoundCloud" style="background: #ff5500; border: none;">☁️</a>'
                f'</div>'
            )
        else:
            if next_seconds is not None and next_seconds > seconds:
                dur_s = next_seconds - seconds
                duration = f"{dur_s // 60}:{dur_s % 60:02d}"
            else:
                duration = '--:--'

            t_str = f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}" if seconds >= 3600 \
                else f"{seconds // 60}:{seconds % 60:02d}"
            h_param, m_param, s_param = seconds // 3600, (seconds % 3600) // 60, seconds % 60
            sc_timestamp_url = f"{soundcloud_url}#t={h_param}:{m_param}:{s_param}"
            lbl = f" @ {t_str}"
            btn_html = (
                f'<div class="d-flex align-items-center gap-1">'
                f'<button onclick="loadTrack(\'{soundcloud_url}\', {seconds})" class="btn btn-sm btn-orange text-nowrap flex-grow-1">▶ Play{lbl}</button>'
                f'<a href="{sc_timestamp_url}" target="_blank" class="btn btn-sm btn-dark flex-shrink-0" title="Jump to track on SoundCloud website" style="background: #334155; border: none;">☁️</a>'
                f'</div>'
            )
        results.append((duration, btn_html))
    return results


def get_spreadsheet_max_episode(xlsx_path="Ori Uplift - Tracklists - excerpt.xlsx"):
    """
    Highest episode number covered by the master spreadsheet. Episodes at or below this
    number come from curated spreadsheet data (specific label codes, dedup logic, etc.) and
    must never be touched by the scrape-based scripts - only episodes strictly above this
    number were ever inserted by scraping, and are safe to re-scrape/replace.
    """
    df = pd.read_excel(xlsx_path, sheet_name='UpOnly Tracklists', usecols=['Episode # / Set Code #'])
    nums = pd.to_numeric(df['Episode # / Set Code #'], errors='coerce').dropna()
    # This column mixes real weekly episode numbers with occasional non-episode "Set Code"
    # entries (e.g. mixcomps) that can be far larger than any real episode number - exclude
    # those outliers rather than let one bad value silently disable every future safety check.
    plausible = nums[nums < 2000]
    return int(plausible.max())


def recompute_leaderboards(cursor, conn):
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
