# Download the live database asset from GitHub Pages to a temporary file
Invoke-WebRequest -Uri "https://simonstokes7.github.io/abora-scraper/uplifting_only.db" -OutFile "live_test.db"

# Query the live file to see what link it contains
python -c "import sqlite3; conn=sqlite3.connect('live_test.db'); c=conn.cursor(); c.execute('SELECT track_link FROM tracks WHERE episode_id=\"465\" LIMIT 1'); print('Link currently hosted on GitHub Pages:', c.fetchone()); conn.close()"

# Clean up the test file
Remove-Item live_test.db