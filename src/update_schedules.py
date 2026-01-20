import json
import os
import datetime
import sys

# Ensure src is in path to import scrapers
sys.path.append(os.path.join(os.path.dirname(__file__)))

from scrapers.incarail import IncaRailScraper
from scrapers.perurail import PeruRailScraper

DATA_FILE = "data/schedules.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_data(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def main():
    data = load_data()
    today = datetime.datetime.now().isoformat()

    print("Starting IncaRail scrape...")
    try:
        inca_scraper = IncaRailScraper()
        # Scrape next 4 weeks to cover a good range
        inca_results = inca_scraper.scrape(weeks=4)
    except Exception as e:
        print(f"IncaRail scrape failed: {e}")
        inca_results = {}

    print("Starting PeruRail scrape...")
    try:
        peru_scraper = PeruRailScraper()
        peru_results = peru_scraper.scrape()
    except Exception as e:
        print(f"PeruRail scrape failed: {e}")
        peru_results = {}

    entry = {
        "scraped_at": today,
        "incarail": inca_results,
        "perurail": peru_results
    }

    if "history" not in data:
        data["history"] = []

    data["history"].append(entry)

    save_data(data)
    print(f"Data saved to {DATA_FILE}")

if __name__ == "__main__":
    main()
