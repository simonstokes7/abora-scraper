# Abora Scraper & Music Dashboard 🎧

An automated ETL data pipeline and interactive presentation dashboard designed to track, enrich, and navigate the extensive broadcast catalog of Ori Uplifting's **Uplifting Only** trance shows. 

This toolkit extracts historical show tracklists, structure-maps them into a local data warehouse, enriches missing media links using external platforms, and deploys a clean web interface for seamless navigation.

---

## 🏗️ Data Architecture & Pipeline Flow

The repository is structured into a multi-stage ingestion, transformation, and storage pipeline:

1. **Extraction (`scraper.py`)**: Pulls raw tracklists and broadcast dates from target show notes.
2. **Data Warehouse Setup (`build_vault.py`)**: Establishes local relational structures inside an SQLite database using robust conflict management (`INSERT OR IGNORE`) to handle high-frequency runs without duplication.
3. **Metadata Enrichment (`repair_via_soundcloud.py`)**: Scans records missing media assignments, executes paced API/OEmbed resolution passes to locate streaming URLs, and filters out compilation placeholders or generic base URLs.
4. **Presentation (`music_dashboard.html` / `index.html`)**: A lightweight frontend interface utilizing structural lookups to allow instant timestamp tracking and specific audio scrubbing.

---

## 📊 Database Schema Details

The pipeline writes to a highly optimized local SQLite database (`uplifting_only.db`) containing the following core execution schema:

### `tracks` Table
| Column Name | Data Type | Role |
| :--- | :--- | :--- |
| `track_id` | TEXT | PRIMARY KEY — Unique alphanumeric record hash |
| `episode_id` | TEXT / INT | Relational link to parent broadcast episode |
| `track_number` | INTEGER | Playback sequence order index |
| `start_time` | TEXT | Absolute timestamp position within the mix |
| `artist` | TEXT | Parsed performer/producer metadata |
| `track_title` | TEXT | Parsed name of the track asset |
| `label` | TEXT | Music label management entity |
| `raw_line` | TEXT | Unmodified source string for data safety audits |
| `track_link` | TEXT | Verified SoundCloud streaming URL or compilation tag |

---

## 🚀 Local Execution & Deployment

### Prerequisites
Ensure your virtual environment is active and required libraries are provisioned:
```bash
# Activate your local virtual environment
.\venv\Scripts\Activate.ps1

# Install core dependencies
pip install requests
