import re
import requests
import urllib.parse
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker

NEW_DB_PATH = r"C:\Data_Projects\abora-scraper\uplifting_vault_v2.db"
Base = declarative_base()

class Episode(Base):
    __tablename__ = 'episodes'
    episode_id = Column(Integer, primary_key=True)  # Pure numeric identifier (e.g., 700)
    episode_name = Column(String)                   # Display title
    air_date = Column(String)                       # ISO Format: YYYY-MM-DD
    soundcloud_url = Column(String)                 # Sanity fallback URL

class Track(Base):
    __tablename__ = 'tracks'
    track_id = Column(Integer, primary_key=True, autoincrement=True)
    episode_id = Column(Integer, ForeignKey('episodes.episode_id'))
    track_number = Column(Integer)
    start_seconds = Column(Integer)                 # Pre-calculated integer seconds (e.g., 269)
    artist = Column(String)
    track_title = Column(String)
    label = Column(String)
    sc_resolved_id = Column(String)                 # Pure numeric asset ID from oEmbed

def get_sc_track_id(url):
    """Hits the public oEmbed API to extract the pure track/playlist numeric identifier."""
    if not url:
        return "playlists/67635705" # Default fallback playlist ID
    try:
        encoded_url = urllib.parse.quote(url, safe='')
        api_url = f"https://soundcloud.com/oembed?url={encoded_url}&format=json"
        response = requests.get(api_url, timeout=5).json()
        html_iframe = response.get('html', '')
        # Regex out the numeric tracking token inside the embed source
        match = re.search(r'url=https%3A//api.soundcloud.com/(tracks|playlists)/(\d+)', html_iframe)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
    except Exception:
        pass
    return "playlists/67635705"

# NOTE: Your scraper scraping engine loop would parse variables, clean them, and save them like this:
# session.add(Episode(episode_id=700, episode_name="Uplifting Only 700 Special", air_date="2026-07-09", ...))