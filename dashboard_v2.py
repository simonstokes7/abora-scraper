# dashboard_v2.py
"""
Ultra Light Dashboard Renderer for Abora Recordings
Reads entirely pre-computed tables directly out of the database workspace.
"""
import os
import webbrowser
import pandas as pd
import urllib.parse
from datetime import datetime
from sqlalchemy import create_engine

SCRIPT_VERSION = "4.0.6"
BUILD_TIME = datetime.now().strftime("%b. %d, %Y @ %I:%M %p")
DB_PATH = r"C:\Data_Projects\abora-scraper\uplifting_vault_v2.db"
HTML_OUTPUT = "index.html"

def launch_interface_v2():
    engine = create_engine(f"sqlite:///{DB_PATH}")
    
    print("Pulling pre-computed dashboard datasets...")
    df_tracks = pd.read_sql("""
        SELECT 
            e.episode_name AS [Episode], 
            e.air_date AS [Air Date],
            t.track_number AS [Track #], 
            t.duration AS [Duration],
            t.artist AS [Artist], 
            t.track_title AS [Track Title], 
            t.label AS [Record Label],
            t.listen_button AS [Listen],
            e.soundcloud_url AS [BaseURL]
        FROM tracks t
        JOIN episodes e ON t.episode_id = e.episode_id
        ORDER BY t.episode_id DESC, t.track_number ASC;
    """, con=engine)
    
    df_meta = pd.read_sql("SELECT type, html_content FROM leaderboards;", con=engine)
    
    if df_tracks.empty or df_meta.empty:
        print("Error: The database lacks pre-computed data. Please run import_spreadsheet.py.")
        return

    total_tracks = len(df_tracks)
    total_mixes = df_tracks['Episode'].nunique()
    default_url = urllib.parse.quote(df_tracks.iloc[0]['BaseURL'] if df_tracks.iloc[0]['BaseURL'] else 'https://api.soundcloud.com/playlists/67635705')

    artist_leaderboard_html = df_meta[df_meta['type'] == 'artists']['html_content'].values[0]
    track_leaderboard_html = df_meta[df_meta['type'] == 'tracks']['html_content'].values[0]

    df_tracks['Episode'] = df_tracks['Episode'].apply(lambda e: f'<div class="episode-container-inner"><div class="episode-title-cell text-truncate" title="{e}">{e}</div><button onclick="copyTracklist(this, \'{e.replace("'", "\\'")}\')" class="btn btn-link btn-copy-icon p-0 ms-2">📋</button></div>')
    
    table_html = df_tracks[['Episode', 'Air Date', 'Track #', 'Duration', 'Artist', 'Track Title', 'Record Label', 'Listen']].to_html(escape=False, index=False, classes="table align-middle")

    layout = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Uplifting Only Vault Console v__VERSION__</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <script src="https://w.soundcloud.com/player/api.js"></script>
    <style>
        body { padding: 15px; padding-bottom: 210px; font-family: system-ui, sans-serif; background-color: #f4f6f9; }
        .vault-card { background: white; border-radius: 12px; padding: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
        table { margin-top: 5px !important; table-layout: fixed !important; width: 100% !important; border-collapse: separate !important; border-spacing: 0 !important; }
        th, td { vertical-align: middle !important; padding: 10px 12px !important; font-size: 0.88rem; border-bottom: 1px solid #e2e8f0 !important; }
        th { background-color: #1e293b !important; color: white !important; position: sticky; top: 0; z-index: 10; text-align: center !important; }
        tbody tr:nth-of-type(even) { background-color: #ffffff !important; }
        tbody tr:nth-of-type(odd) { background-color: #f1f5f9 !important; }
        tbody tr:hover { background-color: #ffedd5 !important; }
        .col-ep { width: 22% !important; } .col-date { width: 9% !important; text-align: center !important; }
        .col-num { width: 5% !important; text-align: center !important; } .col-time { width: 6% !important; text-align: center !important; }
        .col-artist { width: 18% !important; } .col-title { width: 18% !important; }
        .col-label { width: 9% !important; } .col-listen { width: 13% !important; text-align: center !important; }
        .episode-container-inner { display: flex; align-items: center; justify-content: space-between; overflow: hidden; width: 100%; }
        .episode-title-cell { font-weight: 600; text-overflow: ellipsis; white-space: nowrap; overflow: hidden; max-width: 82%; }
        .cell-truncated { text-overflow: ellipsis; white-space: nowrap; overflow: hidden; }
        .btn-copy-icon { font-size: 0.95rem; text-decoration: none; color: #64748b; border: none; background: none; }
        .btn-copy-icon:hover { color: #ff5500; }
        .btn-orange { background-color: #ff5500; color: white; border: none; width: 100%; }
        .btn-orange:hover { background-color: #e04b00; color: white; }
        .btn-outline-secondary { width: 100%; background-color: #ffffff; }
        .audio-deck { position: fixed; bottom: 0; left: 0; right: 0; height: 175px; background: #1e293b; padding: 10px 30px; z-index: 1000; display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .deck-container { width: 100%; max-width: 1200px; }
        .meta-footer { color: #94a3b8; font-size: 0.75rem; margin-top: 6px; width: 100%; max-width: 1200px; display: flex; justify-content: space-between; border-top: 1px solid #334155; padding-top: 4px; }
        .leaderboard-panel { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 12px; height: 140px; }
        .scrollable-leaderboard { height: 100px; overflow-y: auto; }
        .leaderboard-row { cursor: pointer; font-size: 0.78rem; }
        .leaderboard-row:hover { color: #ff5500 !important; }
    </style>
</head>
<body>
<div class="container-fluid vault-card">
    <div class="row g-2">
        <div class="col-md-5 d-flex flex-column justify-content-between py-1">
            <div>
                <h2>Uplifting Only Vault Console <span class="text-muted" style="font-size: 1rem;">v__VERSION__</span></h2>
                <div class="mt-2">
                    <span class="badge bg-dark">__MIXES__ Mixes</span>
                    <span class="badge bg-secondary">__TRACKS__ Tracks</span>
                </div>
            </div>
            <div class="d-flex gap-2 pt-2">
                <input type="text" id="searchBox" class="form-control" placeholder="🔍 Filter instantly...">
                <button onclick="playRandomTrack()" class="btn btn-dark text-nowrap" style="white-space: nowrap;">🎲 Surprise Me</button>
            </div>
        </div>
        <div class="col-md-7">
            <div class="row g-2">
                <div class="col-6"><div class="leaderboard-panel"><h6>🔥 Top Artists</h6><div class="scrollable-leaderboard">__ARTISTS__</div></div></div>
                <div class="col-6"><div class="leaderboard-panel"><h6>🎵 Top Tracks</h6><div class="scrollable-leaderboard">__TRACKS_LIST__</div></div></div>
            </div>
        </div>
    </div>
    __TABLE_HTML__
</div>
<div class="audio-deck">
    <div class="deck-container">
        <iframe id="sc-player" width="100%" height="120" scrolling="no" frameborder="no" allow="autoplay" 
            src="https://w.soundcloud.com/player/?url=__DEFAULT_URL__&color=%23ff5500&auto_play=false&hide_related=true&show_comments=false&show_user=false&show_reposts=false&show_teaser=false">
        </iframe>
    </div>
    <div class="meta-footer"><span>Status: Operational</span><span>Build: __BUILD_TIME__</span></div>
</div>
<script>
    var iframe = document.getElementById('sc-player'), widget = SC.Widget(iframe);
    document.addEventListener("DOMContentLoaded", function() {
        let table = document.querySelector("table"); if (!table) return;
        let colgroup = document.createElement('colgroup');
        colgroup.innerHTML = '<col class="col-ep"><col class="col-date"><col class="col-num"><col class="col-time"><col class="col-artist"><col class="col-title"><col class="col-label"><col class="col-listen">';
        table.insertBefore(colgroup, table.firstChild);
        table.querySelectorAll("thead th").forEach((th, i) => th.className = ["col-ep", "col-date", "col-num", "col-time", "col-artist", "col-title", "col-label", "col-listen"][i]);
        table.querySelectorAll("tbody tr").forEach(row => {
            ["col-ep", "col-date cell-truncated", "col-num cell-truncated", "col-time cell-truncated", "col-artist cell-truncated", "col-title cell-truncated", "col-label cell-truncated", "col-listen"].forEach((c, idx) => row.cells[idx].className = c);
        });
    });
    function loadTrack(url, secs) {
        widget.load(url, { color: "#ff5500", auto_play: true, callback: function() { setTimeout(function() { widget.seekTo(secs * 1000); widget.play(); }, 1200); } });
    }
    function filterRows(val) {
        let q = val.toLowerCase().trim(), rows = document.querySelectorAll('table tbody tr');
        rows.forEach(r => {
            if (!q) { r.style.display = ''; return; }
            if (q.includes(' - ')) {
                let parts = q.split(' - '), aQ = parts[0].trim(), tQ = parts[1].trim();
                let rA = r.cells[4] ? r.cells[4].textContent.toLowerCase().trim() : '';
                let rT = r.cells[5] ? r.cells[5].textContent.toLowerCase().trim() : '';
                r.style.display = (rA.includes(aQ) && rT.includes(tQ)) ? '' : 'none';
            } else {
                r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none';
            }
        });
    }
    function filterBySearch(s) { document.getElementById('searchBox').value = s; filterRows(s); }
    
    function copyTracklist(btn, epName) {
        let rows = Array.from(document.querySelectorAll('table tbody tr'));
        let textLines = [epName, "-------------------------"];
        rows.forEach(r => {
            let cells = r.cells;
            if (cells[0].textContent.trim() === epName) {
                let trackNum = cells[2].textContent.trim();
                let artist = cells[4].textContent.trim();
                let title = cells[5].textContent.trim();
                let label = cells[6].textContent.trim();
                textLines.push(trackNum + ". " + artist + " - " + title + " [" + label + "]");
            }
        });
        let fullText = textLines.join('\\n');
        navigator.clipboard.writeText(fullText).then(() => {
            let orig = btn.textContent;
            btn.textContent = "✅";
            setTimeout(() => { btn.textContent = orig; }, 1500);
        });
    }

    function playRandomTrack() {
        let r = Array.from(document.querySelectorAll('table tbody tr')).filter(row => row.style.display !== 'none');
        if (r.length) r[Math.floor(Math.random() * r.length)].cells[7].querySelector('a, button').click();
    }
    document.getElementById('searchBox').addEventListener('input', function() { filterRows(this.value); });
</script>
</body>
</html>"""

    layout = (layout.replace("__VERSION__", SCRIPT_VERSION)
                    .replace("__MIXES__", str(total_mixes))
                    .replace("__TRACKS__", str(total_tracks))
                    .replace("__ARTISTS__", artist_leaderboard_html)
                    .replace("__TRACKS_LIST__", track_leaderboard_html)
                    .replace("__TABLE_HTML__", table_html)
                    .replace("__DEFAULT_URL__", default_url)
                    .replace("__BUILD_TIME__", BUILD_TIME))

    with open(HTML_OUTPUT, "w", encoding="utf-8") as f:
        f.write(layout)
    
    webbrowser.open(HTML_OUTPUT)
    print(f"Dashboard generated perfectly at target location: {HTML_OUTPUT}")

if __name__ == "__main__":
    launch_interface_v2()