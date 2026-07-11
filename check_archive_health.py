import sqlite3
import requests
from concurrent.futures import ThreadPoolExecutor

DB_PATH = r"C:\Data_Projects\abora-scraper\uplifting_only.db"

def verify_link(row):
    episode_id, episode_name, url = row
    
    # Check 1: Flag empty or missing URL data fields in the database
    if not url:
        return {"id": episode_id, "name": episode_name, "status": "❌ MISSING URL LINK", "url": "N/A"}
    
    # Check 2: Verify the endpoint exists live on the server
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        # Follow redirects cleanly to get the final target destination status code
        response = requests.head(url, headers=headers, allow_redirects=True, timeout=5)
        
        # If the target page returns a 404, it means the asset has been completely scrubbed
        if response.status_code == 404:
            return {"id": episode_id, "name": episode_name, "status": "❌ DEAD LINK (404)", "url": url}
            
    except requests.RequestException:
        return {"id": episode_id, "name": episode_name, "status": "⚠️ Connection Timeout/Failed", "url": url}
        
    return None

def run_diagnostic():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT episode_id, episode_name, soundcloud_url FROM episodes ORDER BY episode_id DESC")
    episodes = cursor.fetchall()
    conn.close()
    
    print(f"🤖 Scanning {len(episodes)} vault links specifically for dead pages or missing paths...")
    print("Running server response verifications in parallel. Standing by...\n")
    
    issues_found = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(verify_link, episodes)
        for res in results:
            if res:
                issues_found.append(res)
                
    if not issues_found:
        print("✨ Success! Every single archive link responded cleanly. The vault pathing is 100% healthy.")
    else:
        print(f"🚨 Scan Complete. Found {len(issues_found)} critical database link issues:\n")
        print(f"{'ID':<6} | {'Episode Name':<50} | {'Status/Issue':<25}")
        print("-" * 90)
        for issue in issues_found:
            print(f"{issue['id']:<6} | {str(issue['name'])[:48]:<50} | {issue['status']:<25}")
            if issue['url'] != 'N/A':
                print(f"       🔗 Target: {issue['url']}")

if __name__ == "__main__":
    run_diagnostic()