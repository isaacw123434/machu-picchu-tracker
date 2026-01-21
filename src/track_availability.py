import json
import csv
import os
import datetime
import time
import re
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

DATA_FILE = "data/availability_log.csv"
URL = "https://tuboleto.cultura.pe/disponibilidad/llaqta_machupicchu"

def should_run(last_run_time, current_time):
    """
    Decides whether to run the scraper based on the last run time.

    Rules:
    1. Target minutes: 55, 10, 25, 40 (every 15 mins, starting at 5 to the hour).
    2. Run if it has been more than 16 minutes since last run (Missed schedule recovery).
    3. Run if current minute is a target minute AND it has been more than 10 minutes since last run (Standard schedule).
    """
    if last_run_time is None:
        return True

    elapsed_minutes = (current_time - last_run_time).total_seconds() / 60

    # Redundancy/Recovery check: If we haven't run in > 15 mins, run immediately.
    if elapsed_minutes > 15:
        print(f"Recovery run: {elapsed_minutes:.1f} minutes since last run.")
        return True

    # Standard schedule check
    target_minutes = [55, 10, 25, 40]
    if current_time.minute in target_minutes:
        # Ensure we don't run twice for the same slot (e.g. if script takes < 1 min and cron fires again? Unlikely with 5 min cron but safe)
        # Also ensures we don't run if we just did a recovery run 2 mins ago.
        if elapsed_minutes > 10:
             print(f"Scheduled run: It is minute {current_time.minute} and {elapsed_minutes:.1f} mins since last run.")
             return True
        else:
             print(f"Skipping: It is minute {current_time.minute} but ran recently ({elapsed_minutes:.1f} mins ago).")
             return False

    print(f"Skipping: Minute {current_time.minute} is not a target and ran recently ({elapsed_minutes:.1f} mins ago).")
    return False

def get_last_run_time():
    if not os.path.exists(DATA_FILE):
        return None

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            # Read just the last non-empty line efficiently-ish?
            # For small files, reading lines is fine.
            lines = f.readlines()
            if len(lines) < 2: # Header only or empty
                return None

            last_line = lines[-1].strip()
            if not last_line:
                return None

            # CSV format: scraped_at,target_date,...
            # 2026-01-19 00:16:55
            timestamp_str = last_line.split(',')[0]
            return datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"Error reading last run time: {e}")
        return None

def run():
    # Use Lima time for consistency with CSV log
    current_time = datetime.datetime.now(ZoneInfo("America/Lima")).replace(tzinfo=None)
    last_run = get_last_run_time()

    if not should_run(last_run, current_time):
        print("Scraper decided not to run at this time.")
        return

    print(f"Starting scrape at {current_time}")
    
    scraped_data = []
    
    # We use a mutable container to store the date because of closure scope
    context_data = {"target_date": None}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(timezone_id="America/Lima", locale="es-PE")
        page = context.new_page()
        
        def handle_request(request):
            if "disponibilidad-actual" in request.url and request.method == "POST":
                try:
                    post_data = request.post_data_json
                    if post_data and 'fecha' in post_data:
                        context_data["target_date"] = post_data['fecha']
                        print(f"Detected target date: {context_data['target_date']}")
                except Exception as e:
                    print(f"Error parsing request payload: {e}")

        def handle_response(response):
            if "disponibilidad-actual" in response.url and response.status == 200:
                print("Intercepted availability response")
                try:
                    data = response.json()
                    if isinstance(data, list):
                        # We assume the request handle happened before response handle
                        # Use current time as scrape time
                        scrape_time = datetime.datetime.now(ZoneInfo("America/Lima")).strftime("%Y-%m-%d %H:%M:%S")
                        
                        for item in data:
                            # Calculate sold
                            capacity = item.get('ncupo', 0)
                            available = item.get('ncupoActual', 0)
                            sold = capacity - available
                            
                            row = {
                                "scraped_at": scrape_time,
                                "target_date": context_data["target_date"] if context_data["target_date"] else "Unknown",
                                "route_name": item.get('ruta'),
                                "capacity": capacity,
                                "available": available,
                                "sold": sold
                            }
                            scraped_data.append(row)
                except Exception as e:
                    print(f"Error parsing response: {e}")

        page.on("request", handle_request)
        page.on("response", handle_response)

        print(f"Navigating to {URL}...")
        page.goto(URL)
        
        # Wait for a bit to ensure requests are fired and processed
        print("Waiting for network activity...")
        page.wait_for_timeout(10000) 

        # Scrape visible date from DOM for verification
        try:
            element = page.get_by_text("Disponibilidad para el día")
            if element.count() > 0:
                parent_text = element.first.evaluate("el => el.parentElement.innerText")
                date_match = re.search(r"(\d{2})/(\d{2})/(\d{4})", parent_text)
                if date_match:
                    day, month, year = date_match.groups()
                    visible_date = f"{year}-{month}-{day}"
                    print(f"Visible date on page: {visible_date}")

                    if context_data["target_date"] and context_data["target_date"] != visible_date:
                        print(f"WARNING: Mismatch between intercepted date ({context_data['target_date']}) and visible date ({visible_date})")
                    elif not context_data["target_date"]:
                         print(f"Intercepted date missing. Using visible date: {visible_date}")
                         context_data["target_date"] = visible_date
                         # Backfill scraped data if needed
                         for row in scraped_data:
                             if row["target_date"] == "Unknown":
                                 row["target_date"] = visible_date
                else:
                    print("Could not find date pattern in text.")
            else:
                print("'Disponibilidad para el día' text not found.")
        except Exception as e:
            print(f"Error scraping visible date: {e}")
        
        browser.close()

    if not scraped_data:
        print("No data scraped.")
        return

    # Write to CSV
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    file_exists = os.path.isfile(DATA_FILE)
    fieldnames = ["scraped_at", "target_date", "route_name", "capacity", "available", "sold"]
    
    with open(DATA_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        
        for row in scraped_data:
            writer.writerow(row)
            
    print(f"Saved {len(scraped_data)} rows to {DATA_FILE}")

if __name__ == "__main__":
    run()
