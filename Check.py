import re

file_path = r"C:\Data_Projects\abora-scraper\Tracklists with Times.md"
found = 0

with open(file_path, "r", encoding="utf-8") as f:
    for line in f:
        # Look for any time stamp pattern like 00:00 or [00:00] or 1:23:45
        if re.search(r"\b\d{1,2}:\d{2}(:\d{2})?\b", line):
            print(line.strip())
            found += 1
            if found >= 10:
                break

if found == 0:
    print("Diagnostic: Scanned the entire file. Zero timestamps found.")