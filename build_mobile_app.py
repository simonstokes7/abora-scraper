# build_mobile_app.py
"""
Build script for Uplifting Only Mobile Web App / PWA.
Reads from uplifting_vault_v2.db and compiles a standalone, ultra-fast,
mobile-optimized music app interface (mobile.html).
Decoupled completely from desktop dashboard_v2.py and music_dashboard.html.
"""

import os
import sys
import json
import sqlite3
import re
from datetime import datetime

DB_PATH = r"C:\Data_Projects\abora-scraper\uplifting_vault_v2.db"
OUTPUT_HTML = r"C:\Data_Projects\abora-scraper\mobile.html"
APP_VERSION = "1.0.0"
BUILD_TIME = datetime.now().strftime("%b %d, %Y")

def build_mobile_app():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        sys.exit(1)

    print(f"Connecting to database: {DB_PATH}")
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # 1. Fetch episodes
    ep_rows = cur.execute("""
        SELECT e.episode_id, e.episode_name, e.air_date, e.soundcloud_url, COUNT(t.track_id) as trk_count
        FROM episodes e
        LEFT JOIN tracks t ON e.episode_id = t.episode_id
        GROUP BY e.episode_id
        ORDER BY e.episode_id DESC
    """).fetchall()

    episodes = []
    episodes_map = {}
    for r in ep_rows:
        ep_id, name, air_date, sc_url, trk_count = r
        ep_data = {
            "id": ep_id,
            "name": name or f"Episode {ep_id}",
            "date": air_date or "Unknown Date",
            "url": sc_url or "",
            "count": trk_count
        }
        episodes.append(ep_data)
        episodes_map[ep_id] = ep_data

    # 2. Fetch tracks
    trk_rows = cur.execute("""
        SELECT t.track_id, t.episode_id, t.track_number, t.duration, t.artist, t.track_title, t.label, t.listen_button, e.soundcloud_url
        FROM tracks t
        JOIN episodes e ON t.episode_id = e.episode_id
        ORDER BY t.episode_id DESC, t.track_number ASC
    """).fetchall()

    tracks = []
    for r in trk_rows:
        t_id, ep_id, num, dur, artist, title, label, btn, sc_url = r
        secs = 0
        if btn:
            m = re.search(r"loadTrack\('([^']+)',\s*(\d+)\)", btn)
            if m:
                sc_url = m.group(1)
                secs = int(m.group(2))
        tracks.append([
            t_id,
            ep_id,
            num or 1,
            dur or "--:--",
            artist or "Unknown Artist",
            title or "Unknown Title",
            label or "Abora",
            secs,
            sc_url or ""
        ])

    # 3. Fetch Leaderboards
    top_artists = cur.execute("""
        SELECT artist, COUNT(*) as c 
        FROM tracks 
        WHERE TRIM(artist) != '' 
        GROUP BY artist 
        ORDER BY c DESC 
        LIMIT 50
    """).fetchall()

    top_tracks = cur.execute("""
        SELECT artist, track_title, COUNT(*) as c 
        FROM tracks 
        WHERE TRIM(track_title) != '' AND TRIM(track_title) != 'Unknown Title'
        GROUP BY artist, track_title 
        ORDER BY c DESC 
        LIMIT 50
    """).fetchall()

    con.close()

    print(f"Loaded {len(episodes)} episodes, {len(tracks)} tracks, {len(top_artists)} top artists, {len(top_tracks)} top tracks.")

    # Convert to JSON
    tracks_json = json.dumps(tracks, separators=(',', ':'))
    episodes_json = json.dumps(episodes, separators=(',', ':'))
    top_artists_json = json.dumps(top_artists, separators=(',', ':'))
    top_tracks_json = json.dumps(top_tracks, separators=(',', ':'))

    default_sc_url = episodes[0]["url"] if episodes and episodes[0]["url"] else "https://soundcloud.com/oriuplift/uponly-701"

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>Uplifting Only 🎧 Mobile App</title>
    
    <!-- PWA Settings -->
    <link rel="manifest" href="manifest_mobile.json">
    <meta name="theme-color" content="#0b0f19">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="UpOnly App">
    <link rel="apple-touch-icon" href="./icon.svg">
    <link rel="icon" type="image/svg+xml" href="./icon.svg">

    <!-- Fonts & Icons -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <script src="https://w.soundcloud.com/player/api.js"></script>

    <style>
        :root {{
            --bg-primary: #080c14;
            --bg-secondary: #0f172a;
            --bg-card: #131d33;
            --bg-card-hover: #1c2a47;
            --border-color: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --text-sub: #64748b;
            --accent-orange: #ff5500;
            --accent-gradient: linear-gradient(135deg, #ff5500 0%, #ff8a3d 100%);
            --accent-glow: rgba(255, 85, 0, 0.25);
            --safe-bottom: env(safe-area-inset-bottom, 0px);
            --safe-top: env(safe-area-inset-top, 0px);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-tap-highlight-color: transparent;
        }}

        body {{
            font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
            padding-top: var(--safe-top);
            padding-bottom: calc(140px + var(--safe-bottom));
            user-select: none;
            -webkit-font-smoothing: antialiased;
        }}

        /* App Header */
        header.app-header {{
            position: sticky;
            top: 0;
            z-index: 100;
            background: rgba(8, 12, 20, 0.88);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            padding: 12px 16px 8px;
        }}

        .brand-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
        }}

        .brand-logo-wrap {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .brand-badge {{
            width: 34px;
            height: 34px;
            background: var(--accent-gradient);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.1rem;
            box-shadow: 0 4px 12px var(--accent-glow);
        }}

        .brand-text h1 {{
            font-size: 1.05rem;
            font-weight: 800;
            letter-spacing: -0.3px;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .brand-text p {{
            font-size: 0.72rem;
            color: var(--text-muted);
            font-weight: 500;
        }}

        .btn-surprise {{
            background: rgba(255, 85, 0, 0.12);
            color: #ff8a3d;
            border: 1px solid rgba(255, 85, 0, 0.3);
            border-radius: 20px;
            padding: 6px 12px;
            font-size: 0.75rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 5px;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .btn-surprise:active {{
            transform: scale(0.94);
            background: var(--accent-gradient);
            color: #fff;
        }}

        /* Search Bar & Chips */
        .search-wrap {{
            position: relative;
            display: flex;
            align-items: center;
            margin-bottom: 8px;
        }}

        .search-icon {{
            position: absolute;
            left: 12px;
            color: var(--text-muted);
            font-size: 0.9rem;
            pointer-events: none;
        }}

        .search-input {{
            width: 100%;
            background: #131d33;
            border: 1px solid #1e293b;
            border-radius: 12px;
            padding: 10px 36px 10px 36px;
            color: #fff;
            font-size: 0.88rem;
            font-family: inherit;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }}

        .search-input:focus {{
            border-color: var(--accent-orange);
            box-shadow: 0 0 0 3px rgba(255, 85, 0, 0.2);
            background: #16223b;
        }}

        .search-input::placeholder {{
            color: var(--text-sub);
        }}

        .btn-clear-search {{
            position: absolute;
            right: 10px;
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 1rem;
            cursor: pointer;
            display: none;
            padding: 4px;
        }}

        .chip-scroll {{
            display: flex;
            gap: 8px;
            overflow-x: auto;
            scrollbar-width: none;
            padding: 2px 0 4px;
        }}

        .chip-scroll::-webkit-scrollbar {{
            display: none;
        }}

        .filter-chip {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.08);
            color: var(--text-muted);
            font-size: 0.74rem;
            font-weight: 600;
            padding: 5px 12px;
            border-radius: 16px;
            white-space: nowrap;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .filter-chip.active {{
            background: var(--accent-orange);
            color: #fff;
            border-color: var(--accent-orange);
            box-shadow: 0 2px 8px var(--accent-glow);
        }}

        /* Main Content Views */
        main.app-main {{
            flex: 1;
            padding: 12px 14px;
            max-width: 720px;
            margin: 0 auto;
            width: 100%;
        }}

        .view-pane {{
            display: none;
        }}

        .view-pane.active {{
            display: block;
        }}

        /* Track Card Item */
        .track-list {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        .track-card {{
            background: var(--bg-card);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 14px;
            padding: 12px 14px;
            display: flex;
            align-items: center;
            gap: 12px;
            transition: transform 0.15s ease, background 0.15s ease, border-color 0.15s ease;
            position: relative;
            cursor: pointer;
        }}

        .track-card:active {{
            transform: scale(0.985);
            background: var(--bg-card-hover);
            border-color: rgba(255, 85, 0, 0.3);
        }}

        .track-card.is-playing {{
            border-color: var(--accent-orange);
            background: rgba(255, 85, 0, 0.07);
            box-shadow: 0 4px 16px rgba(255, 85, 0, 0.15);
        }}

        .track-num-badge {{
            width: 38px;
            height: 38px;
            background: #0f172a;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--text-muted);
            flex-shrink: 0;
            border: 1px solid rgba(255, 255, 255, 0.05);
            transition: all 0.2s;
        }}

        .track-card.is-playing .track-num-badge {{
            background: var(--accent-gradient);
            color: #fff;
            box-shadow: 0 2px 8px var(--accent-glow);
        }}

        .track-details {{
            flex: 1;
            min-width: 0;
        }}

        .track-title {{
            font-size: 0.9rem;
            font-weight: 700;
            color: #ffffff;
            line-height: 1.25;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 3px;
        }}

        .track-artist {{
            font-size: 0.78rem;
            font-weight: 600;
            color: #ff8a3d;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 4px;
        }}

        .track-meta-row {{
            display: flex;
            align-items: center;
            gap: 6px;
            flex-wrap: wrap;
        }}

        .badge-pill {{
            font-size: 0.68rem;
            font-weight: 600;
            padding: 2px 7px;
            border-radius: 6px;
            background: rgba(255, 255, 255, 0.06);
            color: var(--text-muted);
            white-space: nowrap;
        }}

        .badge-ep {{
            background: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.3);
        }}

        .badge-time {{
            background: rgba(255, 85, 0, 0.12);
            color: #ff8a3d;
            border: 1px solid rgba(255, 85, 0, 0.25);
        }}

        .badge-label {{
            background: rgba(255, 255, 255, 0.05);
            color: #cbd5e1;
            max-width: 110px;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .track-actions {{
            display: flex;
            align-items: center;
            gap: 6px;
            flex-shrink: 0;
        }}

        .btn-action-icon {{
            width: 32px;
            height: 32px;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.08);
            color: var(--text-muted);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
        }}

        .btn-action-icon:hover, .btn-action-icon:active {{
            background: rgba(255, 85, 0, 0.2);
            color: #ff8a3d;
            border-color: rgba(255, 85, 0, 0.4);
        }}

        .btn-action-icon.is-favorite {{
            color: #fbbf24;
            border-color: rgba(251, 191, 36, 0.4);
            background: rgba(251, 191, 36, 0.15);
        }}

        /* Loading / Sentinel */
        .infinite-sentinel {{
            text-align: center;
            padding: 24px 0;
            color: var(--text-sub);
            font-size: 0.8rem;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }}

        .spinner {{
            width: 18px;
            height: 18px;
            border: 2px solid rgba(255, 85, 0, 0.2);
            border-top-color: var(--accent-orange);
            border-radius: 50%;
            animation: spin 0.6s linear infinite;
        }}

        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}

        /* Episodes View */
        .episodes-grid {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}

        .episode-card {{
            background: var(--bg-card);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 14px;
            padding: 14px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            transition: background 0.2s, transform 0.2s;
        }}

        .episode-card:active {{
            transform: scale(0.99);
            background: var(--bg-card-hover);
        }}

        .ep-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .ep-card-title {{
            font-size: 0.95rem;
            font-weight: 700;
            color: #fff;
        }}

        .ep-card-meta {{
            display: flex;
            gap: 8px;
            align-items: center;
            font-size: 0.75rem;
            color: var(--text-muted);
        }}

        .ep-card-actions {{
            display: flex;
            gap: 8px;
        }}

        .btn-ep-action {{
            flex: 1;
            padding: 8px 12px;
            border-radius: 10px;
            font-size: 0.78rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            border: none;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .btn-ep-play {{
            background: var(--accent-gradient);
            color: #fff;
            box-shadow: 0 2px 8px var(--accent-glow);
        }}

        .btn-ep-copy {{
            background: rgba(255, 255, 255, 0.06);
            color: var(--text-main);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }}

        .btn-ep-view {{
            background: #1e293b;
            color: #94a3b8;
        }}

        /* Charts View */
        .charts-container {{
            display: flex;
            flex-direction: column;
            gap: 14px;
        }}

        .chart-toggle-row {{
            display: flex;
            background: #0f172a;
            border-radius: 12px;
            padding: 4px;
            border: 1px solid #1e293b;
        }}

        .chart-toggle-btn {{
            flex: 1;
            padding: 8px;
            border-radius: 9px;
            font-size: 0.82rem;
            font-weight: 700;
            border: none;
            background: none;
            color: var(--text-muted);
            cursor: pointer;
            transition: all 0.2s;
        }}

        .chart-toggle-btn.active {{
            background: var(--accent-orange);
            color: #fff;
            box-shadow: 0 2px 8px var(--accent-glow);
        }}

        .chart-row {{
            background: var(--bg-card);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 12px;
            padding: 12px 14px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            cursor: pointer;
            transition: transform 0.15s, background 0.15s;
        }}

        .chart-row:active {{
            transform: scale(0.985);
            background: var(--bg-card-hover);
        }}

        .chart-rank {{
            font-size: 0.85rem;
            font-weight: 800;
            color: var(--accent-orange);
            width: 30px;
        }}

        .chart-info {{
            flex: 1;
            min-width: 0;
        }}

        .chart-title {{
            font-size: 0.86rem;
            font-weight: 700;
            color: #fff;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .chart-subtitle {{
            font-size: 0.74rem;
            color: var(--text-muted);
        }}

        .chart-count {{
            background: rgba(255, 85, 0, 0.15);
            color: #ff8a3d;
            font-size: 0.74rem;
            font-weight: 700;
            padding: 4px 8px;
            border-radius: 8px;
            white-space: nowrap;
        }}

        /* Tracklist Modal / Bottom Sheet */
        .sheet-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.75);
            backdrop-filter: blur(8px);
            z-index: 1000;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.25s ease;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
        }}

        .sheet-overlay.active {{
            opacity: 1;
            pointer-events: auto;
        }}

        .bottom-sheet {{
            background: #0f172a;
            border-top: 1px solid #1e293b;
            border-radius: 20px 20px 0 0;
            max-height: 85vh;
            display: flex;
            flex-direction: column;
            transform: translateY(100%);
            transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            padding-bottom: calc(15px + var(--safe-bottom));
        }}

        .sheet-overlay.active .bottom-sheet {{
            transform: translateY(0);
        }}

        .sheet-handle {{
            width: 40px;
            height: 4px;
            background: #334155;
            border-radius: 4px;
            margin: 10px auto 6px;
        }}

        .sheet-header {{
            padding: 10px 18px 14px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .sheet-header h3 {{
            font-size: 1.05rem;
            font-weight: 800;
            color: #fff;
        }}

        .sheet-header p {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}

        .sheet-body {{
            flex: 1;
            overflow-y: auto;
            padding: 14px 18px;
            -webkit-overflow-scrolling: touch;
        }}

        .btn-sheet-close {{
            background: #1e293b;
            border: none;
            color: #fff;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            font-size: 1rem;
            cursor: pointer;
        }}

        /* Floating Mini Player & Dock */
        .player-dock {{
            position: fixed;
            bottom: calc(62px + var(--safe-bottom));
            left: 12px;
            right: 12px;
            max-width: 696px;
            margin: 0 auto;
            z-index: 200;
            background: rgba(19, 29, 51, 0.95);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 85, 0, 0.3);
            border-radius: 16px;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5), 0 0 15px rgba(255, 85, 0, 0.15);
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            overflow: hidden;
        }}

        .mini-player-bar {{
            padding: 10px 14px;
            display: flex;
            align-items: center;
            gap: 12px;
            cursor: pointer;
        }}

        .mini-pulse-icon {{
            width: 38px;
            height: 38px;
            background: var(--accent-gradient);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.1rem;
            color: #fff;
            flex-shrink: 0;
            box-shadow: 0 2px 8px var(--accent-glow);
        }}

        .mini-track-info {{
            flex: 1;
            min-width: 0;
        }}

        .mini-title {{
            font-size: 0.86rem;
            font-weight: 700;
            color: #fff;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .mini-artist {{
            font-size: 0.74rem;
            color: #ff8a3d;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .mini-controls {{
            display: flex;
            align-items: center;
            gap: 8px;
            flex-shrink: 0;
        }}

        .btn-mini-ctrl {{
            width: 34px;
            height: 34px;
            border-radius: 50%;
            background: #1e293b;
            border: 1px solid rgba(255, 255, 255, 0.08);
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.9rem;
            cursor: pointer;
            transition: transform 0.15s, background 0.15s;
        }}

        .btn-mini-ctrl:active {{
            transform: scale(0.92);
            background: var(--accent-orange);
        }}

        .player-expanded-body {{
            max-height: 0;
            opacity: 0;
            transition: max-height 0.35s ease, opacity 0.25s ease, padding 0.35s ease;
            padding: 0 12px;
        }}

        .player-dock.expanded .player-expanded-body {{
            max-height: 180px;
            opacity: 1;
            padding: 6px 12px 14px;
        }}

        .iframe-container {{
            border-radius: 12px;
            overflow: hidden;
            background: #080c14;
        }}

        /* Bottom App Navigation Bar */
        nav.app-navbar {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            z-index: 300;
            background: rgba(8, 12, 20, 0.94);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-top: 1px solid rgba(255, 255, 255, 0.06);
            display: flex;
            justify-content: space-around;
            align-items: center;
            padding: 6px 0 calc(6px + var(--safe-bottom));
        }}

        .nav-item {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 3px;
            color: var(--text-sub);
            text-decoration: none;
            background: none;
            border: none;
            cursor: pointer;
            padding: 4px 0;
            transition: color 0.2s ease, transform 0.15s ease;
        }}

        .nav-item:active {{
            transform: scale(0.92);
        }}

        .nav-item.active {{
            color: var(--accent-orange);
        }}

        .nav-icon {{
            font-size: 1.25rem;
            line-height: 1;
        }}

        .nav-label {{
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: -0.1px;
        }}

        /* Empty State */
        .empty-state {{
            text-align: center;
            padding: 48px 20px;
            color: var(--text-muted);
        }}

        .empty-icon {{
            font-size: 2.5rem;
            margin-bottom: 12px;
        }}

        .empty-state h4 {{
            color: #fff;
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 6px;
        }}

        .empty-state p {{
            font-size: 0.8rem;
            color: var(--text-sub);
            max-width: 280px;
            margin: 0 auto;
        }}

        /* Toast notification */
        .toast-notify {{
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%) translateY(-60px);
            background: #1e293b;
            color: #fff;
            border: 1px solid var(--accent-orange);
            border-radius: 20px;
            padding: 8px 18px;
            font-size: 0.8rem;
            font-weight: 700;
            z-index: 2000;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
            opacity: 0;
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            pointer-events: none;
        }}

        .toast-notify.show {{
            transform: translateX(-50%) translateY(0);
            opacity: 1;
        }}
    </style>
</head>
<body>

<!-- Toast Notification -->
<div id="appToast" class="toast-notify">📋 Tracklist copied!</div>

<!-- Header -->
<header class="app-header">
    <div class="brand-row">
        <div class="brand-logo-wrap">
            <div class="brand-badge">🎧</div>
            <div class="brand-text">
                <h1>Uplifting Only</h1>
                <p>{len(episodes)} Episodes • {len(tracks):,} Tracks</p>
            </div>
        </div>
        <button onclick="playSurpriseTrack()" class="btn-surprise" title="Play random track">
            <span>🎲</span> Surprise
        </button>
    </div>

    <!-- Search Input -->
    <div class="search-wrap">
        <span class="search-icon">🔍</span>
        <input type="text" id="globalSearch" class="search-input" placeholder="Search track, artist, label, ep #..." autocomplete="off">
        <button id="btnClearSearch" class="btn-clear-search" onclick="clearSearch()">✕</button>
    </div>

    <!-- Filter Chips -->
    <div class="chip-scroll">
        <button class="filter-chip active" onclick="applyFilter('all', this)">⚡ All Tracks</button>
        <button class="filter-chip" onclick="applyFilter('latest', this)">🆕 Latest Mixes</button>
        <button class="filter-chip" onclick="applyFilter('soundlift', this)">🔥 SoundLift</button>
        <button class="filter-chip" onclick="applyFilter('abora', this)">🏷️ Abora Label</button>
        <button class="filter-chip" onclick="applyFilter('favorites', this)">⭐ Favorites</button>
    </div>
</header>

<!-- Main Views -->
<main class="app-main">

    <!-- 1. Tracks View (Infinite Scroll) -->
    <div id="viewTracks" class="view-pane active">
        <div id="tracksList" class="track-list">
            <!-- Dynamically populated -->
        </div>
        <div id="tracksSentinel" class="infinite-sentinel">
            <div class="spinner"></div>
            <span>Loading tracks...</span>
        </div>
    </div>

    <!-- 2. Episodes View -->
    <div id="viewEpisodes" class="view-pane">
        <div id="episodesList" class="episodes-grid">
            <!-- Dynamically populated -->
        </div>
    </div>

    <!-- 3. Top Charts View -->
    <div id="viewCharts" class="view-pane">
        <div class="charts-container">
            <div class="chart-toggle-row">
                <button id="btnChartArtists" class="chart-toggle-btn active" onclick="switchChartMode('artists')">🔥 Top 50 Artists</button>
                <button id="btnChartTracks" class="chart-toggle-btn" onclick="switchChartMode('tracks')">🎵 Top 50 Tracks</button>
            </div>
            <div id="chartContentList" class="chart-list">
                <!-- Dynamically populated -->
            </div>
        </div>
    </div>

    <!-- 4. Favorites View -->
    <div id="viewFavorites" class="view-pane">
        <div id="favoritesList" class="track-list">
            <!-- Dynamically populated -->
        </div>
        <div id="favEmptyState" class="empty-state" style="display: none;">
            <div class="empty-icon">⭐</div>
            <h4>No Favorites Saved</h4>
            <p>Tap the star icon on any track to save it here for instant listening!</p>
        </div>
    </div>

</main>

<!-- Floating Mini Player Dock -->
<div id="playerDock" class="player-dock">
    <div class="mini-player-bar" onclick="togglePlayerExpand()">
        <div class="mini-pulse-icon">🎶</div>
        <div class="mini-track-info">
            <div id="miniTitle" class="mini-title">Select a track to play</div>
            <div id="miniArtist" class="mini-artist">Ori Uplifting • Uplifting Only</div>
        </div>
        <div class="mini-controls" onclick="event.stopPropagation()">
            <button id="btnMiniPlay" class="btn-mini-ctrl" onclick="togglePlayPause()" title="Play / Pause">▶</button>
            <button class="btn-mini-ctrl" onclick="playSurpriseTrack()" title="Random Track">🎲</button>
            <button id="btnMiniExpand" class="btn-mini-ctrl" onclick="togglePlayerExpand()" title="Toggle Waveform">▲</button>
        </div>
    </div>
    <div class="player-expanded-body">
        <div class="iframe-container">
            <iframe id="sc-player" width="100%" height="120" scrolling="no" frameborder="no" allow="autoplay"
                src="https://w.soundcloud.com/player/?url={default_sc_url}&color=%23ff5500&auto_play=false&hide_related=true&show_comments=false&show_user=false&show_reposts=false&show_teaser=false">
            </iframe>
        </div>
    </div>
</div>

<!-- Bottom Navigation Bar -->
<nav class="app-navbar">
    <button class="nav-item active" onclick="switchTab('tracks', this)">
        <span class="nav-icon">🎵</span>
        <span class="nav-label">Tracks</span>
    </button>
    <button class="nav-item" onclick="switchTab('episodes', this)">
        <span class="nav-icon">📻</span>
        <span class="nav-label">Episodes</span>
    </button>
    <button class="nav-item" onclick="switchTab('charts', this)">
        <span class="nav-icon">🏆</span>
        <span class="nav-label">Charts</span>
    </button>
    <button class="nav-item" onclick="switchTab('favorites', this)">
        <span class="nav-icon">⭐</span>
        <span class="nav-label">Saved</span>
    </button>
</nav>

<!-- Episode Tracklist Sheet -->
<div id="episodeSheet" class="sheet-overlay" onclick="closeEpisodeSheet(event)">
    <div class="bottom-sheet" onclick="event.stopPropagation()">
        <div class="sheet-handle"></div>
        <div class="sheet-header">
            <div>
                <h3 id="sheetEpTitle">Uplifting Only</h3>
                <p id="sheetEpMeta">Broadcast date</p>
            </div>
            <button class="btn-sheet-close" onclick="closeEpisodeSheetDirect()">✕</button>
        </div>
        <div class="p-2 d-flex gap-2" style="padding: 10px 18px 4px; display: flex; gap: 8px;">
            <button id="btnSheetCopy" class="btn-ep-action btn-ep-copy" style="flex: 1;">📋 Copy Tracklist</button>
            <button id="btnSheetPlayMix" class="btn-ep-action btn-ep-play" style="flex: 1;">▶ Play Episode</button>
        </div>
        <div id="sheetTrackList" class="sheet-body track-list">
            <!-- Dynamically populated -->
        </div>
    </div>
</div>

<!-- Application Engine -->
<script>
    // 1. DATASETS
    const RAW_TRACKS = {tracks_json};
    const RAW_EPISODES = {episodes_json};
    const TOP_ARTISTS = {top_artists_json};
    const TOP_TRACKS = {top_tracks_json};

    // Episode Map Lookup
    const EP_MAP = {{}};
    RAW_EPISODES.forEach(ep => {{ EP_MAP[ep.id] = ep; }});

    // 2. STATE MANAGEMENT
    let activeTab = 'tracks';
    let filteredTracks = [...RAW_TRACKS];
    let currentRenderIndex = 0;
    const CHUNK_SIZE = 40;
    let currentlyPlayingTrackId = null;
    let isPlayerPlaying = false;
    let favoritesSet = new Set(JSON.parse(localStorage.getItem('uponly_favs') || '[]'));
    let activeChartMode = 'artists';
    let currentSheetEpId = null;

    // SoundCloud Widget Reference
    const iframe = document.getElementById('sc-player');
    const widget = SC.Widget(iframe);

    // 3. INITIALIZATION
    document.addEventListener('DOMContentLoaded', () => {{
        renderTracksChunk();
        setupInfiniteScroll();
        setupSearchInput();
        renderEpisodesList();
        renderCharts();
        renderFavorites();
        
        // PWA Service Worker
        if ('serviceWorker' in navigator) {{
            navigator.serviceWorker.register('./sw.js').catch(e => console.log('SW Registration:', e));
        }}
    }});

    // 4. TAB NAVIGATION
    function switchTab(tabId, btn) {{
        activeTab = tabId;
        document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
        if (btn) btn.classList.add('active');

        document.querySelectorAll('.view-pane').forEach(p => p.classList.remove('active'));
        if (tabId === 'tracks') {{
            document.getElementById('viewTracks').classList.add('active');
        }} else if (tabId === 'episodes') {{
            document.getElementById('viewEpisodes').classList.add('active');
        }} else if (tabId === 'charts') {{
            document.getElementById('viewCharts').classList.add('active');
        }} else if (tabId === 'favorites') {{
            renderFavorites();
            document.getElementById('viewFavorites').classList.add('active');
        }}
        window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }}

    // 5. TRACK LIST VIRTUAL / INFINITE RENDERING
    function renderTracksChunk() {{
        const container = document.getElementById('tracksList');
        const nextIndex = Math.min(currentRenderIndex + CHUNK_SIZE, filteredTracks.length);
        const fragment = document.createDocumentFragment();

        for (let i = currentRenderIndex; i < nextIndex; i++) {{
            const t = filteredTracks[i];
            const card = createTrackCardElement(t);
            fragment.appendChild(card);
        }}

        container.appendChild(fragment);
        currentRenderIndex = nextIndex;

        const sentinel = document.getElementById('tracksSentinel');
        if (currentRenderIndex >= filteredTracks.length) {{
            sentinel.style.display = 'none';
        }} else {{
            sentinel.style.display = 'flex';
        }}
    }}

    function createTrackCardElement(t) {{
        // t structure: [t_id, ep_id, num, dur, artist, title, label, secs, sc_url]
        const [tId, epId, num, dur, artist, title, label, secs, scUrl] = t;
        const ep = EP_MAP[epId] || {{ name: `Ep ${{epId}}`, date: '' }};
        const epShortName = ep.name.replace(/Uplifting Only\\\\s*/i, 'UpOnly ');
        const isFav = favoritesSet.has(tId);
        const isPlaying = (currentlyPlayingTrackId === tId);

        const card = document.createElement('div');
        card.className = `track-card ${{isPlaying ? 'is-playing' : ''}}`;
        card.id = `trk-card-${{tId}}`;

        const timeStr = secs > 0 ? formatSecs(secs) : dur;

        card.innerHTML = `
            <div class="track-num-badge">${{isPlaying ? '▶' : '#' + num}}</div>
            <div class="track-details">
                <div class="track-title">${{escapeHtml(title)}}</div>
                <div class="track-artist">${{escapeHtml(artist)}}</div>
                <div class="track-meta-row">
                    <span class="badge-pill badge-ep">${{escapeHtml(epShortName)}}</span>
                    ${{secs > 0 ? `<span class="badge-pill badge-time">⏱ ${{timeStr}}</span>` : ''}}
                    <span class="badge-pill badge-label">${{escapeHtml(label)}}</span>
                </div>
            </div>
            <div class="track-actions" onclick="event.stopPropagation()">
                <button class="btn-action-icon ${{isFav ? 'is-favorite' : ''}}" onclick="toggleFavorite(${{tId}}, this)" title="Save to Favorites">⭐</button>
                <a href="${{scUrl || 'https://soundcloud.com/oriuplift'}}" target="_blank" class="btn-action-icon" title="Open in SoundCloud">☁️</a>
            </div>
        `;

        card.addEventListener('click', () => {{
            playTrack(t);
        }});

        return card;
    }}

    function setupInfiniteScroll() {{
        const sentinel = document.getElementById('tracksSentinel');
        const observer = new IntersectionObserver((entries) => {{
            if (entries[0].isIntersecting && activeTab === 'tracks') {{
                if (currentRenderIndex < filteredTracks.length) {{
                    renderTracksChunk();
                }}
            }}
        }}, {{ rootMargin: '400px' }});
        observer.observe(sentinel);
    }}

    // 6. INSTANT SEARCH & FILTERING (<5ms in memory)
    let searchDebounceTimer = null;
    function setupSearchInput() {{
        const input = document.getElementById('globalSearch');
        const clearBtn = document.getElementById('btnClearSearch');

        input.addEventListener('input', (e) => {{
            const val = e.target.value;
            clearBtn.style.display = val.length > 0 ? 'block' : 'none';
            clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(() => {{
                executeSearch(val);
            }}, 80);
        }});
    }}

    function executeSearch(query) {{
        const q = query.toLowerCase().trim();
        if (!q) {{
            filteredTracks = [...RAW_TRACKS];
        }} else {{
            const keywords = q.split(/\\\\s+/);
            filteredTracks = RAW_TRACKS.filter(t => {{
                // t: [t_id, ep_id, num, dur, artist, title, label, secs, sc_url]
                const ep = EP_MAP[t[1]];
                const epName = ep ? ep.name.toLowerCase() : '';
                const fullText = (t[4] + ' ' + t[5] + ' ' + t[6] + ' ' + epName).toLowerCase();
                return keywords.every(kw => fullText.includes(kw));
            }});
        }}

        // Reset scroll & re-render
        currentRenderIndex = 0;
        document.getElementById('tracksList').innerHTML = '';
        renderTracksChunk();

        if (activeTab !== 'tracks') {{
            switchTab('tracks', document.querySelector('.nav-item'));
        }}
    }}

    function clearSearch() {{
        const input = document.getElementById('globalSearch');
        input.value = '';
        document.getElementById('btnClearSearch').style.display = 'none';
        executeSearch('');
    }}

    function applyFilter(filterType, btn) {{
        document.querySelectorAll('.filter-chip').forEach(el => el.classList.remove('active'));
        if (btn) btn.classList.add('active');

        if (filterType === 'all') {{
            clearSearch();
        }} else if (filterType === 'latest') {{
            filteredTracks = RAW_TRACKS.filter(t => t[1] >= 650);
            currentRenderIndex = 0;
            document.getElementById('tracksList').innerHTML = '';
            renderTracksChunk();
            switchTab('tracks', document.querySelector('.nav-item'));
        }} else if (filterType === 'soundlift') {{
            document.getElementById('globalSearch').value = 'SoundLift';
            executeSearch('SoundLift');
        }} else if (filterType === 'abora') {{
            document.getElementById('globalSearch').value = 'Abora';
            executeSearch('Abora');
        }} else if (filterType === 'favorites') {{
            switchTab('favorites', document.querySelectorAll('.nav-item')[3]);
        }}
    }}

    // 7. AUDIO PLAYBACK & MINI PLAYER
    function playTrack(t) {{
        // t: [t_id, ep_id, num, dur, artist, title, label, secs, sc_url]
        const [tId, epId, num, dur, artist, title, label, secs, scUrl] = t;
        const ep = EP_MAP[epId] || {{ name: `Episode ${{epId}}` }};

        currentlyPlayingTrackId = tId;

        // Update card active classes
        document.querySelectorAll('.track-card').forEach(c => c.classList.remove('is-playing'));
        const activeCard = document.getElementById(`trk-card-${{tId}}`);
        if (activeCard) activeCard.classList.add('is-playing');

        // Update Mini Player UI
        document.getElementById('miniTitle').textContent = title;
        document.getElementById('miniArtist').textContent = `${{artist}} • ${{ep.name}}`;
        document.getElementById('btnMiniPlay').textContent = '⏸';
        isPlayerPlaying = true;

        // Load SoundCloud Track & Seek
        const targetUrl = scUrl || ep.url || 'https://soundcloud.com/oriuplift';
        widget.load(targetUrl, {{
            color: "#ff5500",
            auto_play: true,
            callback: function() {{
                setTimeout(() => {{
                    if (secs > 0) {{
                        widget.seekTo(secs * 1000);
                    }}
                    widget.play();
                }}, 1000);
            }}
        }});
    }}

    function playEpisodeMix(epId) {{
        const ep = EP_MAP[epId];
        if (!ep || !ep.url) return;

        document.getElementById('miniTitle').textContent = ep.name;
        document.getElementById('miniArtist').textContent = `Full Mix (${{ep.date}})`;
        document.getElementById('btnMiniPlay').textContent = '⏸';
        isPlayerPlaying = true;

        widget.load(ep.url, {{
            color: "#ff5500",
            auto_play: true,
            callback: function() {{
                widget.play();
            }}
        }});
    }}

    function togglePlayPause() {{
        if (!isPlayerPlaying) {{
            widget.play();
            document.getElementById('btnMiniPlay').textContent = '⏸';
            isPlayerPlaying = true;
        }} else {{
            widget.pause();
            document.getElementById('btnMiniPlay').textContent = '▶';
            isPlayerPlaying = false;
        }}
    }}

    function togglePlayerExpand() {{
        const dock = document.getElementById('playerDock');
        dock.classList.toggle('expanded');
        document.getElementById('btnMiniExpand').textContent = dock.classList.contains('expanded') ? '▼' : '▲';
    }}

    function playSurpriseTrack() {{
        const pool = filteredTracks.length ? filteredTracks : RAW_TRACKS;
        const randomTrack = pool[Math.floor(Math.random() * pool.length)];
        playTrack(randomTrack);
        showToast(`🎲 Playing: ${{randomTrack[5]}}`);
    }}

    // 8. FAVORITES SYSTEM (localStorage)
    function toggleFavorite(trackId, btn) {{
        if (favoritesSet.has(trackId)) {{
            favoritesSet.delete(trackId);
            if (btn) btn.classList.remove('is-favorite');
            showToast('Removed from favorites');
        }} else {{
            favoritesSet.add(trackId);
            if (btn) btn.classList.add('is-favorite');
            showToast('⭐ Saved to favorites!');
        }}
        localStorage.setItem('uponly_favs', JSON.stringify(Array.from(favoritesSet)));
        if (activeTab === 'favorites') renderFavorites();
    }}

    function renderFavorites() {{
        const container = document.getElementById('favoritesList');
        const emptyState = document.getElementById('favEmptyState');
        container.innerHTML = '';

        const favTracks = RAW_TRACKS.filter(t => favoritesSet.has(t[0]));
        if (favTracks.length === 0) {{
            emptyState.style.display = 'block';
            return;
        }}
        emptyState.style.display = 'none';

        const fragment = document.createDocumentFragment();
        favTracks.forEach(t => {{
            fragment.appendChild(createTrackCardElement(t));
        }});
        container.appendChild(fragment);
    }}

    // 9. EPISODES VIEW & TRACKLIST SHEET
    function renderEpisodesList() {{
        const container = document.getElementById('episodesList');
        const fragment = document.createDocumentFragment();

        RAW_EPISODES.forEach(ep => {{
            const card = document.createElement('div');
            card.className = 'episode-card';
            card.innerHTML = `
                <div class="ep-card-header">
                    <div class="ep-card-title">${{escapeHtml(ep.name)}}</div>
                    <div class="badge-pill badge-ep">${{ep.count}} tracks</div>
                </div>
                <div class="ep-card-meta">
                    <span>📅 ${{escapeHtml(ep.date)}}</span>
                </div>
                <div class="ep-card-actions">
                    <button class="btn-ep-action btn-ep-play" onclick="playEpisodeMix(${{ep.id}})">▶ Play Mix</button>
                    <button class="btn-ep-action btn-ep-view" onclick="openEpisodeSheet(${{ep.id}})">📋 Tracklist</button>
                    <button class="btn-ep-action btn-ep-copy" onclick="copyEpisodeTracklist(${{ep.id}}, this)">📋 Copy</button>
                </div>
            `;
            fragment.appendChild(card);
        }});

        container.appendChild(fragment);
    }}

    function openEpisodeSheet(epId) {{
        currentSheetEpId = epId;
        const ep = EP_MAP[epId];
        if (!ep) return;

        document.getElementById('sheetEpTitle').textContent = ep.name;
        document.getElementById('sheetEpMeta').textContent = `Air Date: ${{ep.date}} • ${{ep.count}} Tracks`;

        const epTracks = RAW_TRACKS.filter(t => t[1] === epId);
        const container = document.getElementById('sheetTrackList');
        container.innerHTML = '';

        const fragment = document.createDocumentFragment();
        epTracks.forEach(t => {{
            fragment.appendChild(createTrackCardElement(t));
        }});
        container.appendChild(fragment);

        document.getElementById('btnSheetCopy').onclick = () => copyEpisodeTracklist(epId, document.getElementById('btnSheetCopy'));
        document.getElementById('btnSheetPlayMix').onclick = () => playEpisodeMix(epId);

        document.getElementById('episodeSheet').classList.add('active');
        document.body.style.overflow = 'hidden';
    }}

    function closeEpisodeSheet(e) {{
        document.getElementById('episodeSheet').classList.remove('active');
        document.body.style.overflow = '';
    }}

    function closeEpisodeSheetDirect() {{
        document.getElementById('episodeSheet').classList.remove('active');
        document.body.style.overflow = '';
    }}

    function copyEpisodeTracklist(epId, btn) {{
        const ep = EP_MAP[epId];
        const epTracks = RAW_TRACKS.filter(t => t[1] === epId);
        const lines = [ep.name + " (" + ep.date + ")", "---------------------------------"];
        epTracks.forEach(t => {{
            lines.push(`${{t[2]}}. ${{t[4]}} - ${{t[5]}} [${{t[6]}}]`);
        }});
        const fullText = lines.join('\\\\n');

        navigator.clipboard.writeText(fullText).then(() => {{
            showToast(`📋 Copied ${{ep.name}} tracklist!`);
            if (btn) {{
                const orig = btn.innerHTML;
                btn.innerHTML = '✅ Copied!';
                setTimeout(() => {{ btn.innerHTML = orig; }}, 1500);
            }}
        }}).catch(() => {{
            showToast('Unable to copy tracklist');
        }});
    }}

    // 10. CHARTS VIEW
    function switchChartMode(mode) {{
        activeChartMode = mode;
        document.getElementById('btnChartArtists').classList.toggle('active', mode === 'artists');
        document.getElementById('btnChartTracks').classList.toggle('active', mode === 'tracks');
        renderCharts();
    }}

    function renderCharts() {{
        const container = document.getElementById('chartContentList');
        container.innerHTML = '';
        const fragment = document.createDocumentFragment();

        if (activeChartMode === 'artists') {{
            TOP_ARTISTS.forEach(([artist, count], idx) => {{
                const row = document.createElement('div');
                row.className = 'chart-row';
                row.innerHTML = `
                    <div class="chart-rank">#${{idx + 1}}</div>
                    <div class="chart-info">
                        <div class="chart-title">${{escapeHtml(artist)}}</div>
                        <div class="chart-subtitle">Producer / Artist</div>
                    </div>
                    <div class="chart-count">${{count}} plays</div>
                `;
                row.addEventListener('click', () => {{
                    document.getElementById('globalSearch').value = artist;
                    executeSearch(artist);
                }});
                fragment.appendChild(row);
            }});
        }} else {{
            TOP_TRACKS.forEach(([artist, title, count], idx) => {{
                const row = document.createElement('div');
                row.className = 'chart-row';
                row.innerHTML = `
                    <div class="chart-rank">#${{idx + 1}}</div>
                    <div class="chart-info">
                        <div class="chart-title">${{escapeHtml(title)}}</div>
                        <div class="chart-subtitle">${{escapeHtml(artist)}}</div>
                    </div>
                    <div class="chart-count">${{count}} plays</div>
                `;
                row.addEventListener('click', () => {{
                    document.getElementById('globalSearch').value = `${{artist}} ${{title}}`;
                    executeSearch(`${{artist}} ${{title}}`);
                }});
                fragment.appendChild(row);
            }});
        }}

        container.appendChild(fragment);
    }}

    // 11. UTILITIES
    function formatSecs(secs) {{
        const h = Math.floor(secs / 3600);
        const m = Math.floor((secs % 3600) / 60);
        const s = secs % 60;
        if (h > 0) return `${{h}}:${{m.toString().padStart(2, '0')}}:${{s.toString().padStart(2, '0')}}`;
        return `${{m}}:${{s.toString().padStart(2, '0')}}`;
    }}

    function escapeHtml(str) {{
        if (!str) return '';
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }}

    function showToast(msg) {{
        const toast = document.getElementById('appToast');
        toast.textContent = msg;
        toast.classList.add('show');
        setTimeout(() => {{ toast.classList.remove('show'); }}, 2000);
    }}
</script>

</body>
</html>
"""

    print(f"Writing mobile app bundle to: {OUTPUT_HTML}")
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_template)

    print(f"SUCCESS: Uplifting Only Mobile App compiled to {OUTPUT_HTML} (Size: {os.path.getsize(OUTPUT_HTML) / 1024 / 1024:.2f} MB)")

if __name__ == "__main__":
    build_mobile_app()
