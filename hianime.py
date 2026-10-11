import os
import sys
import time
import requests
from bs4 import BeautifulSoup

WEBHOOK = os.environ["ANIME_WEBHOOK"]
STATE_FILE = "hianime_sent.txt"
TARGET_URL = "https://hianime.at/recently-updated"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def load_sent_ids():
    if not os.path.exists(STATE_FILE):
        return set()
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

sent_ids = load_sent_ids()

try:
    r = requests.get(TARGET_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
except requests.exceptions.RequestException as e:
    print(f"Error fetching page: {e}")
    sys.exit(1)

soup = BeautifulSoup(r.text, "html.parser")
anime_items = soup.select(".flw-item")

if not anime_items:
    print("No items found or structure changed.")
    sys.exit(0)

new_sent_ids = set()

# Process from oldest to newest in the scraped batch
for item in reversed(anime_items):
    try:
        title_elem = item.select_one(".film-name a")
        if not title_elem:
            continue
            
        title = title_elem.get_text(strip=True)
        
        # Base link is usually the overview page (e.g., /anime-name-123)
        overview_link = title_elem.get("href", "")
        
        # Check if an episode exists
        eps_elem = item.select_one(".tick-eps")
        latest_ep = eps_elem.get_text(strip=True) if eps_elem else ""

        # Determine if it has an actual episode released
        has_episodes = latest_ep and latest_ep != "0" and "coming" not in latest_ep.lower()

        if has_episodes:
            # Construct the watch/episode link format
            watch_link = overview_link if "/watch/" in overview_link else overview_link.replace("/", "/watch/", 1)
            site_url = f"https://hianime.at{watch_link}" if watch_link.startswith("/") else watch_link
            
            # Unique ID tracking for specific episode releases
            item_id = f"{overview_link}-ep-{latest_ep}"
            message = f"🎬 **New Episode Release**\n**{title}** - Episode {latest_ep}\n{site_url}"
        else:
            # Fallback to overview page if no episodes are out yet
            site_url = f"https://hianime.at{overview_link}" if overview_link.startswith("/") else overview_link
            
            # Unique ID tracking for the overview/announcement
            item_id = f"{overview_link}-overview"
            message = f"📢 **New Anime Added (Overview)**\n**{title}**\n{site_url}"

        if item_id in sent_ids:
            continue

        # Send webhook notification
        requests.post(WEBHOOK, json={"content": message}, timeout=30)
        
        new_sent_ids.add(item_id)
        time.sleep(0.5)
    except Exception as err:
        print(f"Error parsing item: {err}")

# Save state back to file (keeping the last 150 sent IDs)
all_ids = list(sent_ids.union(new_sent_ids))[-150:]
open(STATE_FILE, "w", encoding="utf-8").write("\n".join(all_ids))
