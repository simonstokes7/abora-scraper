import os
import webbrowser
import pandas as pd
import re
from sqlalchemy import create_engine

DB_PATH = r"C:\Data_Projects\abora-scraper\uplifting_only.db"
HTML_OUTPUT = "music_dashboard.html"

def launch_interface():
    engine = create_engine(f"sqlite:///{DB_PATH}")
    
    query = """
        SELECT 
            e.episode_id AS [EpisodeID],
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
        JOIN episodes e ON t.episode_id = e.episode_id
        ORDER BY e.episode_id DESC, CAST(t.track_number AS INTEGER) ASC;
    """
    
    print("Pulling live music data cache...")
    df = pd.read_sql(query, con=engine)

    # Dynamic KPI calculations for the header
    total_tracks = len(df)
    total_mixes = df['Episode'].nunique()

    # Heavy Rotation Tracker - Top 100 Artists
    top_artists = (df[df['Artist'].str.strip().str.lower() != '']
                   ['Artist'].value_counts().head(100))
    
    artist_leaderboard_html = ""
    for rank, (artist, count) in enumerate(top_artists.items(), 1):
        escaped_artist = artist.replace("'", "\\'")
        artist_leaderboard_html += f"""
        <div onclick="filterByArtist('{escaped_artist}')" class="d-flex justify-content-between align-items-center mb-1 leaderboard-row" title="Click to filter tracks by this artist">
            <span><strong>#{rank}</strong> {artist}</span>
            <span class="badge bg-light text-dark rounded-pill border count-badge">{count} plays</span>
        </div>"""

    def make_button(row):
        url = row['BaseURL']
        seconds = row['TotalSeconds']
        time_str = row['Start Time']
        episode_name = str(row['Episode'])
        
        if not url: 
            return '<span class="text-muted">No Link</span>'
        
        # Detect if this is one of our known anomalous special rows from the health scan
        is_breaking_special = bool(re.search(r'uponly-\d{4,}', url))
        
        if is_breaking_special:
            # Extract the actual 2 or 3-digit show number directly from the episode text name string
            ep_num_match = re.search(r'(?:Uplifting Only|Uuponly)\s*(\d{2,3})\b', episode_name, re.IGNORECASE)
            
            if ep_num_match:
                # Strip leading zeros cleanly (e.g., '048' becomes '48') to match SoundCloud's live slug format
                ep_num = str(int(ep_num_match.group(1)))
                clean_url = f"https://soundcloud.com/oriuplift/uponly-{ep_num}"
            else:
                # Safe generic fallback if text string matching fails
                clean_url = url
            
            if time_str != '--:--':
                mins = seconds // 60
                secs = seconds % 60
                # Revert to verified working hash pattern (#t=) with browser frame execution
                time_url = f"{clean_url}#t={mins}m{secs}s"
                return f'<a href="{time_url}" target="_blank" onclick="var w=window.open(\'{time_url}\', \'_blank\'); setTimeout(function(){{ if(w) w.location.hash=\'#t={mins}m{secs}s\'; }}, 1500); return false;" class="btn btn-sm btn-orange">🌐 Drop at {time_str} ↗</a>'
            return f'<a href="{clean_url}" target="_blank" class="btn btn-sm btn-outline-secondary">🌐 Open Mix ↗</a>'
            
        # NATIVE API ROUTE: Working items stream directly into the footer deck widget
        if time_str == '--:--':
            return f'<button onclick="loadTrack(\'{url}\', 0)" class="btn btn-sm btn-outline-secondary">▶ Play Mix</button>'
        return f'<button onclick="loadTrack(\'{url}\', {seconds})" class="btn btn-sm btn-orange">▶ Drop at {time_str}</button>'

    df['Listen'] = df.apply(make_button, axis=1)
    
    def format_episode_cell(row):
        ep_name = str(row['Episode'])
        return f'{ep_name} <button onclick="copyTracklist(this, \'{ep_name.replace("'", "\\'")}\')" class="btn btn-link btn-copy p-0 ms-2" title="Copy Tracklist">📋 Copy</button>'
        
    df['Episode'] = df.apply(format_episode_cell, axis=1)
    
    df_display = df.drop(columns=['EpisodeID', 'TotalSeconds', 'BaseURL'])
    
    styling = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Uplifting Only Vault Console (__MIXES__ Mixes / __TRACKS__ Tracks)</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <link rel="icon" href="https://fav.farm/🎧">
    <script src="https://w.soundcloud.com/player/api.js"></script>
    <style>
        body { padding: 15px; padding-bottom: 180px; font-family: system-ui, sans-serif; background-color: #f4f6f9; }
        .vault-card { background: white; border-radius: 12px; padding: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
        th { 
            background-color: #1e293b !important; 
            color: white !important; 
            position: sticky; 
            top: 0; 
            z-index: 10; 
            text-align: center !important; 
            vertical-align: middle;
        }
        .btn-orange { background-color: #ff5500; color: white; font-weight: 500; border: none; text-decoration: none; display: inline-block; }
        .btn-orange:hover { background-color: #e04b00; color: white; }
        .audio-deck {
            position: fixed; bottom: 0; left: 0; right: 0;
            height: 140px; background: #1e293b; box-shadow: 0 -4px 20px rgba(0,0,0,0.2);
            padding: 10px 30px; z-index: 1000; display: flex; align-items: center; justify-content: center;
        }
        .deck-container { width: 100%; max-width: 1200px; }
        .badge-metrics { font-size: 1.1rem; vertical-align: middle; margin-left: 10px; background-color: #475569; color: white; }
        .btn-copy { font-size: 0.8rem; text-decoration: none; color: #64748b; }
        .btn-copy:hover { color: #ff5500; }
        
        .leaderboard-panel { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 12px; }
        .scrollable-leaderboard { height: 110px; overflow-y: auto; padding-right: 4px; }
        
        .leaderboard-row { cursor: pointer; padding: 1px 4px; border-radius: 4px; transition: background 0.1s ease; font-size: 0.78rem; line-height: 1.05; }
        .leaderboard-row:hover { background-color: #ffe5d9; color: #ff5500 !important; }
        .leaderboard-row:hover .count-badge { background-color: #ff5500 !important; color: white !important; }
        .count-badge { font-size: 0.70rem !important; padding: 0.1em 0.4em !important; }
        
        .console-row { margin-bottom: 0px !important; }
        table { margin-top: 5px !important; }
        
        .scrollable-leaderboard::-webkit-scrollbar { width: 5px; }
        .scrollable-leaderboard::-webkit-scrollbar-track { background: #f1f5f9; }
        .scrollable-leaderboard::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
        .scrollable-leaderboard::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
    </style>
</head>
<body>
<div class="container-fluid vault-card">
    
    <div class="row g-2 console-row">
        <div class="col-md-7 d-flex flex-column justify-content-between py-1">
            <div>
                <h2 class="m-0 p-0" style="line-height: 1.1;">Uplifting Only Master Archive 
                    <span class="badge badge-metrics rounded-pill">__MIXES__ Mixes</span>
                    <span class="badge badge-metrics rounded-pill">__TRACKS__ Tracks</span>
                </h2>
                <p class="text-muted mt-1 mb-0" style="font-size: 0.9rem;">Instant playback engine workspace.</p>
            </div>
            
            <div class="d-flex gap-2 mt-3 mb-1">
                <input type="text" id="searchBox" class="form-control" placeholder="🔍 Filter by artist, title, or label instantly...">
                <button onclick="playRandomTrack()" class="btn btn-dark text-nowrap">🎲 Surprise Me</button>
            </div>
        </div>
        
        <div class="col-md-5">
            <div class="leaderboard-panel">
                <h6 class="text-uppercase text-muted fw-bold mb-1" style="font-size: 0.70rem; letter-spacing: 0.05em;">🔥 Heavy Rotation (Top 100 Artists)</h6>
                <div class="scrollable-leaderboard">
                    __LEADERBOARD__
                </div>
            </div>
        </div>
    </div>
"""

    styling = styling.replace("__MIXES__", str(total_mixes)).replace("__TRACKS__", str(total_tracks)).replace("__LEADERBOARD__", artist_leaderboard_html)

    js_controls = """</div>
<div class="audio-deck">
    <div class="deck-container">
        <iframe id="sc-player" width="100%" height="120" scrolling="no" frameborder="no" allow="autoplay" 
            src="https://w.soundcloud.com/player/?url=https%3A//api.soundcloud.com/tracks/49931110&color=%23ff5500&auto_play=false&hide_related=true&show_comments=false&show_user=false&show_reposts=false&show_teaser=false">
        </iframe>
    </div>
</div>
<script>
    var iframe = document.getElementById('sc-player');
    var widget = SC.Widget(iframe);
    var currentUrl = "";

    function loadTrack(url, seconds) {
        var targetMs = seconds * 1000;
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

    function filterByArtist(artistName) {
        var searchInput = document.getElementById('searchBox');
        searchInput.value = artistName;
        
        let value = artistName.toLowerCase().trim();
        let rows = document.querySelectorAll('table tbody tr');
        window.requestAnimationFrame(() => {
            for (let i = 0; i < rows.length; i++) {
                let text = rows[i].textContent.toLowerCase();
                rows[i].style.display = text.includes(value) ? '' : 'none';
            }
        });
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
            if (cells.length >= 6) {
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

        let fullText = lines.join("\\n");
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
        let value = this.value.toLowerCase().trim();
        let rows = document.querySelectorAll('table tbody tr');
        window.requestAnimationFrame(() => {
            for (let i = 0; i < rows.length; i++) {
                let text = rows[i].textContent.toLowerCase();
                rows[i].style.display = text.includes(value) ? '' : 'none';
            }
        });
    });
</script>
</body>
</html>"""

    with open(HTML_OUTPUT, "w", encoding="utf-8") as f:
        f.write(styling + df_display.to_html(escape=False, index=False, classes="table table-striped table-hover align-middle") + js_controls)
    
    webbrowser.open(f"file:///{os.path.abspath(HTML_OUTPUT)}")
    print("Dashboard opened successfully.")

if __name__ == "__main__":
    launch_interface()