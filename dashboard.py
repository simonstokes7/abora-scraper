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

    def make_button(row):
        url = row['BaseURL']
        seconds = row['TotalSeconds']
        time_str = row['Start Time']
        
        if not url: 
            return '<span class="text-muted">No Link</span>'
        
        # Dynamic Anomaly Detection: Flag any track that uses the alternative slug pattern
        is_anomalous_slug = "/uponly-" in url
        
        if is_anomalous_slug:
            if time_str != '--:--':
                mins = seconds // 60
                secs = seconds % 60
                # Dynamically append the verified timeline hash onto the specific database URL discovered
                time_url = f"{url}#t={mins}m{secs}s"
                return f'<a href="{time_url}" target="_blank" class="btn btn-sm btn-orange">🌐 Drop at {time_str} ↗</a>'
            return f'<a href="{url}" target="_blank" class="btn btn-sm btn-outline-secondary">🌐 Open Mix ↗</a>'
            
        # Standard player widget loading logic for all standard structural URLs
        if time_str == '--:--':
            return f'<button onclick="loadTrack(\'{url}\', 0)" class="btn btn-sm btn-outline-secondary">▶ Play Mix</button>'
        return f'<button onclick="loadTrack(\'{url}\', {seconds})" class="btn btn-sm btn-orange">▶ Drop at {time_str}</button>'

    df['Listen'] = df.apply(make_button, axis=1)
    
    df_display = df.drop(columns=['EpisodeID', 'TotalSeconds', 'BaseURL'])
    
    styling = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Uplifting Only Vault Console (__MIXES__ Mixes / __TRACKS__ Tracks)</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <script src="https://fav.farm/🎧"></script>
    <script src="https://w.soundcloud.com/player/api.js"></script>
    <style>
        body { padding: 30px; padding-bottom: 180px; font-family: system-ui, sans-serif; background-color: #f4f6f9; }
        .vault-card { background: white; border-radius: 12px; padding: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
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
        #searchBox { max-width: 400px; margin-bottom: 20px; font-size: 1.1rem; }
        .audio-deck {
            position: fixed; bottom: 0; left: 0; right: 0;
            height: 140px; background: #1e293b; box-shadow: 0 -4px 20px rgba(0,0,0,0.2);
            padding: 10px 30px; z-index: 1000; display: flex; align-items: center; justify-content: center;
        }
        .deck-container { width: 100%; max-width: 1200px; }
        .badge-metrics { font-size: 1.1rem; vertical-align: middle; margin-left: 10px; background-color: #475569; color: white; }
    </style>
</head>
<body>
<div class="container-fluid vault-card">
    <div class="d-flex align-items-center justify-content-between mb-1">
        <h2 class="mb-0">Uplifting Only Master Archive 
            <span class="badge badge-metrics rounded-pill">__MIXES__ Mixes</span>
            <span class="badge badge-metrics rounded-pill">__TRACKS__ Tracks</span>
        </h2>
    </div>
    <p class="text-muted mb-4">Instant playback engine workspace.</p>
    <input type="text" id="searchBox" class="form-control" placeholder="🔍 Filter by artist, title, or label instantly...">"""

    styling = styling.replace("__MIXES__", str(total_mixes)).replace("__TRACKS__", str(total_tracks))

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