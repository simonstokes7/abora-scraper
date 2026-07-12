import os
import webbrowser
import pandas as pd
import re
import urllib.parse
from datetime import datetime
from sqlalchemy import create_engine

# Engine Versioning Metadata Tracker
SCRIPT_VERSION = "1.1.9"
BUILD_TIME = datetime.now().strftime("%b. %d, %Y @ %I:%M %p")

DB_PATH = r"C:\Data_Projects\abora-scraper\uplifting_only.db"
HTML_OUTPUT = "music_dashboard.html"

def launch_interface():
    engine = create_engine(f"sqlite:///{DB_PATH}")
    
    query = """
        SELECT 
            e.episode_name AS [Episode], 
            e.air_date AS [Air Date],
            t.track_number AS [Track #], 
            COALESCE(t.start_time, '--:--') AS [Start Time],
            t.artist AS [Artist], 
            t.track_title AS [Track Title], 
            t.label AS [Record Label],
            CASE 
                WHEN t.start_time IS NOT NULL AND e.soundcloud_url IS NOT NULL THEN
                    CASE 
                        WHEN length(t.start_time) - length(replace(t.start_time, ':', '')) = 2 THEN
                            (CAST(substr(t.start_time, 1, instr(t.start_time, ':') - 1) AS INTEGER) * 3600) +
                            (CAST(substr(t.start_time, instr(t.start_time, ':') + 1, 2) AS INTEGER) * 60) +
                            CAST(substr(t.start_time, length(t.start_time) - 1) AS INTEGER)
                        ELSE 
                            (CAST(substr(t.start_time, 1, instr(t.start_time, ':') - 1) AS INTEGER) * 60) +
                            CAST(substr(t.start_time, instr(t.start_time, ':') + 1) AS INTEGER)
                    END
                ELSE 0
            END AS [TotalSeconds],
            e.soundcloud_url AS [BaseURL]
        FROM tracks t
        JOIN episodes e ON t.episode_id = e.episode_id;
    """
    
    print("Pulling live music data cache...")
    df = pd.read_sql(query, con=engine)

    total_tracks = len(df)
    total_mixes = df['Episode'].nunique()

    # 1. Top 50 Heavy Rotation Artists
    top_artists = (df[df['Artist'].str.strip().str.lower() != '']
                   ['Artist'].value_counts().head(50))
    
    artist_leaderboard_html = ""
    for rank, (artist, count) in enumerate(top_artists.items(), 1):
        escaped_artist = artist.replace("'", "\\'")
        artist_leaderboard_html += f"""
        <div onclick="filterBySearch('{escaped_artist}')" class="d-flex justify-content-between align-items-center mb-1 leaderboard-row" title="Click to filter tracks by this artist">
            <span><strong>#{rank}</strong> {artist}</span>
            <span class="badge bg-light text-dark rounded-pill border count-badge">{count} plays</span>
        </div>"""

    # 2. Top 50 Heavy Rotation Unique Tracks (Artist + Title Combination)
    valid_tracks = df[(df['Artist'].str.strip() != '') & (df['Track Title'].str.strip() != '')].copy()
    valid_tracks['Full Track'] = valid_tracks['Artist'].str.strip() + " - " + valid_tracks['Track Title'].str.strip()
    top_tracks = valid_tracks['Full Track'].value_counts().head(50)
    
    track_leaderboard_html = ""
    for rank, (full_track_name, count) in enumerate(top_tracks.items(), 1):
        escaped_track = full_track_name.replace("'", "\\'")
        track_leaderboard_html += f"""
        <div onclick="filterBySearch('{escaped_track}')" class="d-flex justify-content-between align-items-center mb-1 leaderboard-row" title="Click to filter by this specific track">
            <span class="text-truncate me-2"><strong>#{rank}</strong> {full_track_name}</span>
            <span class="badge bg-light text-dark rounded-pill border count-badge flex-shrink-0">{count} plays</span>
        </div>"""

    def make_button(row):
        url = row['BaseURL']
        seconds = row['TotalSeconds']
        time_str = row['Start Time']
        episode_name = str(row['Episode'])
        
        if not url: 
            return '<span class="text-muted">No Link</span>'
        
        is_breaking_special = bool(re.search(r'uponly-\d{4,}', url))
        
        if is_breaking_special:
            ep_num_match = re.search(r'(?:Uplifting Only|Uuponly)\s*(\d{1,3})\b', episode_name, re.IGNORECASE)
            
            if ep_num_match:
                raw_num = int(ep_num_match.group(1))
                clean_url = f"https://soundcloud.com/oriuplift/uponly-{raw_num:03d}"
            else:
                clean_url = url
                
            if time_str != '--:--':
                mins = seconds // 60
                secs = seconds % 60
                time_url = f"{clean_url}#t={mins}m{secs}s"
                return f'<a href="{time_url}" target="_blank" onclick="var w=window.open(\'{time_url}\', \'_blank\'); setTimeout(function(){{ if(w) w.location.hash=\'#t={mins}m{secs}s\'; }}, 1500); return false;" class="btn btn-sm btn-orange d-inline-flex align-items-center justify-content-center gap-1">🌐 Drop at {time_str}</a>'
            return f'<a href="{clean_url}" target="_blank" class="btn btn-sm btn-outline-secondary d-inline-flex align-items-center justify-content-center gap-1">🌐 Open Mix</a>'
            
        if time_str == '--:--':
            return f'<button onclick="loadTrack(\'{url}\', 0)" class="btn btn-sm btn-outline-secondary">▶ Play Mix</button>'
        return f'<button onclick="loadTrack(\'{url}\', {seconds})" class="btn btn-sm btn-orange">▶ Drop at {time_str}</button>'

    df['Listen'] = df.apply(make_button, axis=1)
    
    # Extract track metadata metrics inside Python
    def extract_episode_number(text_val):
        digits = re.findall(r'\d+', str(text_val))
        return int(digits[0]) if digits else 0

    df['SortEpisodeID'] = df['Episode'].apply(extract_episode_number)
    df['Track_Num_Numeric'] = pd.to_numeric(df['Track #'], errors='coerce').fillna(999).astype(int)
    
    df = df.sort_values(by=['SortEpisodeID', 'Track_Num_Numeric'], ascending=[False, True])
    
    default_player_url = "https://api.soundcloud.com/playlists/67635705"
    if not df.empty:
        top_row_url = df.iloc[0]['BaseURL']
        episode_name = str(df.iloc[0]['Episode'])
        
        if top_row_url:
            if '/tracks/' in top_row_url and 'api.soundcloud.com' not in top_row_url:
                track_offset = top_row_url.find('/tracks/')
                target_raw = 'https://api.soundcloud.com' + top_row_url[track_offset:]
            elif bool(re.search(r'uponly-\d{4,}', top_row_url)):
                ep_num_match = re.search(r'(?:Uplifting Only|Uuponly)\s*(\d{1,3})\b', episode_name, re.IGNORECASE)
                if ep_num_match:
                    raw_num = int(ep_num_match.group(1))
                    target_raw = f"https://soundcloud.com/oriuplift/uponly-{raw_num:03d}"
                else:
                    target_raw = top_row_url
            else:
                target_raw = top_row_url
                
            default_player_url = urllib.parse.quote(target_raw, safe='')

    def format_episode_cell(row):
        ep_name = str(row['Episode'])
        return f'<div class="episode-title-cell text-truncate" title="{ep_name}">{ep_name}</div><button onclick="copyTracklist(this, \'{ep_name.replace("'", "\\'")}\')" class="btn btn-link btn-copy p-0 ms-2" title="Copy Tracklist">📋 Copy</button>'
        
    df['Episode'] = df.apply(format_episode_cell, axis=1)
    
    df_display = df.drop(columns=['SortEpisodeID', 'TotalSeconds', 'BaseURL', 'Track_Num_Numeric'])
    
    styling = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Uplifting Only Vault Console (__MIXES__ Mixes / __TRACKS__ Tracks)</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <link rel="icon" href="https://fav.farm/🎧">
    <script src="https://w.soundcloud.com/player/api.js"></script>
    <style>
        body { padding: 15px; padding-bottom: 210px; font-family: system-ui, sans-serif; background-color: #f4f6f9; }
        .vault-card { background: white; border-radius: 12px; padding: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
        
        /* HARDCODED FIXED COLUMN WIDTH CONTROLS */
        table { margin-top: 5px !important; table-layout: fixed !important; width: 100% !important; }
        th, td { vertical-align: middle !important; padding: 6px 8px !important; font-size: 0.88rem; }
        
        th { background-color: #1e293b !important; color: white !important; position: sticky; top: 0; z-index: 10; }
        
        /* Explicit spacing definitions for utility cells */
        .col-ep { width: 30% !important; }
        .col-date { width: 9% !important; text-align: center !important; }
        .col-num { width: 5% !important; text-align: center !important; }
        .col-time { width: 6% !important; text-align: center !important; }
        .col-artist { width: 18% !important; }
        .col-title { width: 18% !important; }
        .col-label { width: 11% !important; }
        .col-listen { width: 11% !important; text-align: center !important; }
        
        .episode-container-cell { display: flex; align-items: center; justify-content: space-between; overflow: hidden; }
        .episode-title-cell { font-weight: 500; text-overflow: ellipsis; white-space: nowrap; overflow: hidden; flex-grow: 1; }
        .cell-truncated { text-overflow: ellipsis; white-space: nowrap; overflow: hidden; }
        
        .btn-orange { background-color: #ff5500; color: white; font-weight: 500; border: none; text-decoration: none; display: inline-block; width: 100%; text-align: center; }
        .btn-orange:hover { background-color: #e04b00; color: white; }
        .btn-outline-secondary { width: 100%; text-align: center; }
        
        .audio-deck {
            position: fixed; bottom: 0; left: 0; right: 0;
            height: 175px; background: #1e293b; box-shadow: 0 -4px 20px rgba(0,0,0,0.2);
            padding: 10px 30px; z-index: 1000; display: flex; flex-direction: column; align-items: center; justify-content: center;
        }
        .deck-container { width: 100%; max-width: 1200px; }
        .meta-footer { color: #94a3b8; font-size: 0.75rem; margin-top: 6px; width: 100%; max-width: 1200px; display: flex; justify-content: space-between; border-top: 1px solid #334155; padding-top: 4px; }
        .btn-copy { font-size: 0.8rem; text-decoration: none; color: #64748b; flex-shrink: 0; }
        .btn-copy:hover { color: #ff5500; }
        
        .leaderboard-panel { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 12px; height: 140px; }
        .scrollable-leaderboard { height: 100px; overflow-y: auto; padding-right: 4px; }
        
        .leaderboard-row { cursor: pointer; padding: 1px 4px; border-radius: 4px; transition: background 0.1s ease; font-size: 0.78rem; line-height: 1.05; }
        .leaderboard-row:hover { background-color: #ffe5d9; color: #ff5500 !important; }
        .leaderboard-row:hover .count-badge { background-color: #ff5500 !important; color: white !important; }
        .count-badge { font-size: 0.70rem !important; padding: 0.1em 0.4em !important; }
        .console-row { margin-bottom: 0px !important; }
        
        .scrollable-leaderboard::-webkit-scrollbar { width: 5px; }
        .scrollable-leaderboard::-webkit-scrollbar-track { background: #f1f5f9; }
        .scrollable-leaderboard::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
        .scrollable-leaderboard::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
    </style>
</head>
<body>
<div class="container-fluid vault-card">
    
    <div class="row g-2 console-row">
        <div class="col-md-5 d-flex flex-column justify-content-between py-1">
            <div>
                <h2 class="m-0 p-0" style="line-height: 1.1; font-size: 1.6rem;">Uplifting Only Vault Console</h2>
                <div class="mt-2">
                    <span class="badge bg-secondary rounded-pill">__MIXES__ Mixes</span>
                    <span class="badge bg-secondary rounded-pill">__TRACKS__ Tracks</span>
                </div>
            </div>
            
            <div class="d-flex gap-2 mt-auto pt-2">
                <input type="text" id="searchBox" class="form-control" placeholder="🔍 Filter instantly...">
                <button onclick="playRandomTrack()" class="btn btn-dark text-nowrap">🎲 Surprise Me</button>
            </div>
        </div>
        
        <div class="col-md-7">
            <div class="row g-2">
                <div class="col-6">
                    <div class="leaderboard-panel">
                        <h6 class="text-uppercase text-muted fw-bold mb-1" style="font-size: 0.70rem; letter-spacing: 0.05em;">🔥 Top Artists (50)</h6>
                        <div class="scrollable-leaderboard">
                            __ARTISTS__
                        </div>
                    </div>
                </div>
                <div class="col-6">
                    <div class="leaderboard-panel">
                        <h6 class="text-uppercase text-muted fw-bold mb-1" style="font-size: 0.70rem; letter-spacing: 0.05em;">🎵 Top Tracks (50)</h6>
                        <div class="scrollable-leaderboard">
                            __TRACKS_LIST__
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
"""

    styling = (styling.replace("__MIXES__", str(total_mixes))
                      .replace("__TRACKS__", str(total_tracks))
                      .replace("__ARTISTS__", artist_leaderboard_html)
                      .replace("__TRACKS_LIST__", track_leaderboard_html))

    js_controls = """</div>
<div class="audio-deck">
    <div class="deck-container">
        <iframe id="sc-player" width="100%" height="120" scrolling="no" frameborder="no" allow="autoplay" 
            src="https://w.soundcloud.com/player/?url=__DEFAULT_URL__&color=%23ff5500&auto_play=false&hide_related=true&show_comments=false&show_user=false&show_reposts=false&show_teaser=false">
        </iframe>
    </div>
    <div class="meta-footer">
        <span>Console Status: Operational</span>
        <span>Version: Build v__VERSION__</span>
        <span>Generated: __BUILD_TIME__</span>
    </div>
</div>
<script>
    var iframe = document.getElementById('sc-player');
    var widget = SC.Widget(iframe);
    var currentUrl = decodeURIComponent("__DEFAULT_URL__");

    // STRUCTURE METRIC ALIGNMENT LAYOUT FOR ENGINE COMPILATION
    document.addEventListener("DOMContentLoaded", function() {
        let table = document.querySelector("table");
        if (!table) return;
        
        // Inject structured column widths layout
        let colgroup = document.createElement('colgroup');
        colgroup.innerHTML = `
            <col class="col-ep">
            <col class="col-date">
            <col class="col-num">
            <col class="col-time">
            <col class="col-artist">
            <col class="col-title">
            <col class="col-label">
            <col class="col-listen">
        `;
        table.insertBefore(colgroup, table.firstChild);
        
        // Apply responsive text handling boundaries to table cells
        let headers = table.querySelectorAll("thead th");
        let classNames = ["col-ep", "col-date", "col-num", "col-time", "col-artist", "col-title", "col-label", "col-listen"];
        headers.forEach((th, idx) => { if(classNames[idx]) th.className = classNames[idx]; });

        let rows = table.querySelectorAll("tbody tr");
        rows.forEach(row => {
            if(row.cells.length >= 8) {
                row.cells[0].className = "episode-container-cell"; 
                row.cells[1].className = "col-date cell-truncated"; 
                row.cells[2].className = "col-num cell-truncated";  
                row.cells[3].className = "col-time cell-truncated"; 
                row.cells[4].className = "col-artist cell-truncated"; 
                row.cells[5].className = "col-title cell-truncated";  
                row.cells[6].className = "col-label cell-truncated";  
                row.cells[7].className = "col-listen";
                
                // Mount hover descriptions for cut strings
                row.cells[4].setAttribute("title", row.cells[4].textContent.trim());
                row.cells[5].setAttribute("title", row.cells[5].textContent.trim());
                row.cells[6].setAttribute("title", row.cells[6].textContent.trim());
            }
        });
    });

    function loadTrack(url, seconds) {
        var targetMs = seconds * 1000;
        
        if (url.includes('/tracks/') && !url.includes('api.soundcloud.com')) {
            url = 'https://api.soundcloud.com' + url.substring(url.indexOf('/tracks/'));
        }

        if (currentUrl !== url) {
            currentUrl = url;
            widget.load(url, {
                color: "#ff5500", auto_play: true, hide_related: true, show_comments: false,
                show_user: false, show_reposts: false, show_teaser: false,
                callback: function() {
                    setTimeout(function() { widget.seekTo(targetMs); widget.play(); }, 1200);
                }
            });
        } else {
            widget.seekTo(targetMs);
            widget.play();
        }
    }

    function filterRows(value) {
        let rows = document.querySelectorAll('table tbody tr');
        let parts = value.split(' - ');
        
        window.requestAnimationFrame(() => {
            for (let i = 0; i < rows.length; i++) {
                let cells = rows[i].getElementsByTagName('td');
                if (cells.length >= 8) {
                    if (parts.length === 2) {
                        let rowArtist = cells[4].textContent.toLowerCase().trim();
                        let rowTitle = cells[5].textContent.toLowerCase().trim();
                        
                        let targetArtist = parts[0].toLowerCase().trim();
                        let targetTitle = parts[1].toLowerCase().trim();
                        
                        let artistMatch = targetArtist.length <= 3 ? 
                            new RegExp('\\\\b' + targetArtist.replace(/[-\/\\\\^$*+?.()|[\\]{}]/g, '\\\\$&') + '\\\\b', 'i').test(rowArtist) : 
                            rowArtist.includes(targetArtist);
                            
                        let titleMatch = targetTitle.length <= 3 ? 
                            new RegExp('\\\\b' + targetTitle.replace(/[-\/\\\\^$*+?.()|[\\]{}]/g, '\\\\$&') + '\\\\b', 'i').test(rowTitle) : 
                            rowTitle.includes(targetTitle);
                        
                        rows[i].style.display = (artistMatch && titleMatch) ? '' : 'none';
                    } else {
                        let sanitizedValue = value.replace(/[-\/\\\\^$*+?.()|[\\]{}]/g, '\\$&');
                        let regexPattern = value.length <= 3 ? new RegExp('\\\\b' + sanitizedValue + '\\\\b', 'i') : new RegExp(sanitizedValue, 'i');
                        
                        let searchableText = (
                            cells[0].textContent + " " +  
                            cells[4].textContent + " " +  
                            cells[5].textContent + " " +  
                            cells[6].textContent          
                        );
                        
                        rows[i].style.display = regexPattern.test(searchableText) ? '' : 'none';
                    }
                }
            }
        });
    }

    function filterBySearch(searchString) {
        var searchInput = document.getElementById('searchBox');
        searchInput.value = searchString;
        filterRows(searchString.trim());
    }

    function playRandomTrack() {
        let rows = Array.from(document.querySelectorAll('table tbody tr')).filter(r => r.style.display !== 'none');
        if (rows.length === 0) return;
        
        let randomRow = rows[Math.floor(Math.random() * rows.length)];
        let targetButton = randomRow.querySelector('button.btn-orange, a.btn-orange');
        
        if (targetButton) {
            let originalBg = randomRow.style.backgroundColor;
            randomRow.style.backgroundColor = '#ffe5d9';
            setTimeout(() => { randomRow.style.backgroundColor = originalBg; }, 1500);
            
            targetButton.click();
        }
    }

    function copyTracklist(btnElement, targetEpisode) {
        let rows = Array.from(document.querySelectorAll('table tbody tr'));
        let lines = [ "=== " + targetEpisode + " Tracklist ===" ];
        
        rows.forEach(row => {
            let cells = row.getElementsByTagName('td');
            if (cells.length >= 7) {
                let cellEpText = cells[0].textContent || "";
                if (cellEpText.includes(targetEpisode)) {
                    let trackNum = cells[2].textContent.trim();
                    let artist = cells[4].textContent.trim();
                    let title = cells[5].textContent.trim();
                    let label = cells[6].textContent.trim();
                    
                    let line = trackNum + ". " + artist + " - " + title;
                    if (label && label !== "--" && label !== "") { line += " [" + label + "]"; }
                    lines.push(line);
                }
            }
        });

        if (lines.length <= 1) {
            alert("No tracks found for this episode layout.");
            return;
        }

        let fullText = lines.join("\\\\n");
        navigator.clipboard.writeText(fullText).then(() => {
            let originalText = btnElement.innerHTML;
            btnElement.innerHTML = "✅ Copied!";
            btnElement.style.color = "#22c55e";
            setTimeout(() => {
                btnElement.innerHTML = originalText;
                btnElement.style.color = "";
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy playlist: ', err);
        });
    }

    document.getElementById('searchBox').addEventListener('input', function() {
        filterRows(this.value.trim());
    });
</script>
</body>
</html>"""

    js_controls = (js_controls.replace("__VERSION__", SCRIPT_VERSION)
                              .replace("__BUILD_TIME__", BUILD_TIME)
                              .replace("__DEFAULT_URL__", default_player_url))

    # FIXED SEPARATION METRIC: Re-added explicit columns list formatting parameters to match layout index mapping perfectly
    with open(HTML_OUTPUT, "w", encoding="utf-8") as f:
        f.write(styling + df_display.to_html(escape=False, index=False, classes="table table-striped table-hover align-middle") + js_controls)
    
    webbrowser.open(f"file:///{os.path.abspath(HTML_OUTPUT)}")
    print(f"Dashboard Build v{SCRIPT_VERSION} deployed successfully.")

if __name__ == "__main__":
    launch_interface()