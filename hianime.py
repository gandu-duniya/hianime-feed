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
#1
# Load previously sent item identifiers to prevent duplicates
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
        relative_link = title_elem.get("href", "")
        site_url = f"https://hianime.at{relative_link}" if relative_link.startswith("/") else relative_link
        
        # Unique identifier for the item
        item_id = item.get("data-id") or relative_link
        
        if item_id in sent_ids:
            continue

        eps_elem = item.select_one(".tick-eps")
        latest_ep = eps_elem.get_text(strip=True) if eps_elem else "N/A"

        # Send webhook notification
        requests.post(WEBHOOK, json={
            "content": f"**HiAnime Release** | {title}, Episode {latest_ep}\n{site_url}"
        }, timeout=30)
        
        new_sent_ids.add(item_id)
        time.sleep(0.5)
    except Exception as err:
        print(f"Error parsing item: {err}")

# Save state back to file (keeping the last 100 sent IDs to avoid infinite file growth)
all_ids = list(sent_ids.union(new_sent_ids))[-100:]
open(STATE_FILE, "w", encoding="utf-8").write("\n".join(all_ids))
