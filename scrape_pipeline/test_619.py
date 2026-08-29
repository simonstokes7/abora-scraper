import re
import requests

# Target only Episode 619 for this dry run
URL = "https://soundcloud.com/oriuplift/uponly-619"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def dry_run_extraction():
    print(f"Connecting to SoundCloud endpoint: {URL}...")
    try:
        response = requests.get(URL, headers=HEADERS, timeout=8)
        if response.status_code != 200:
            print(f"Connection failed with HTTP Status Code: {response.status_code}")
            return
        
        html_content = response.text
        
        # Look for the structural track patterns inside the description text box
        track_matches = re.findall(r"(\d+)[\.\s\-]+\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?[\s:]+([^-]+)-\s*([^\[\n\r]+)(?:\[(.*?)\])?", html_content)
        
        if not track_matches:
            print("❌ No tracks detected. SoundCloud might be obfuscating or lazy-loading the text frame.")
            # Print a snippet of the HTML description block for debugging if it failed
            meta_desc = re.search(r'<meta property="og:description" content="(.*?)"', html_content)
            if meta_desc:
                print("\nFound meta description summary:")
                print(meta_desc.group(1)[:500])
            return

        print(f"\n✅ Success! Detected {len(track_matches)} tracks inside the description text:")
        print("-" * 80)
        
        # Display the first 5 parsed tracks to verify column placement
        for match in track_matches[:5]:
            tr_num = match[0].strip()
            s_time = match[1].strip()
            artist = match[2].strip()
            title = match[3].strip()
            label = match[4].strip() if match[4] else "Unknown Label"
            
            # Clean up known subtitle tags
            title = re.sub(r"\s*\(FAN FAVORITE.*?\)\s*", "", title, flags=re.IGNORECASE)
            
            print(f"Track #{tr_num} | Start: {s_time} | Artist: {artist} | Title: {title} | Label: {label}")
            
        print("-" * 80)
        print(f"...and {len(track_matches) - 5} more tracks found.")
        
    except Exception as e:
        print(f"Error executing test run: {e}")

if __name__ == "__main__":
    dry_run_extraction()