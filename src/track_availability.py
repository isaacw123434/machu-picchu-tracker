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

    New Logic:
    - Run if elapsed time >= 14 minutes.
    - This handles the 15-minute interval requirement while allowing for startup latency.
    """
    if last_run_time is None:
        print("No last run time found (first run or file missing). Running.")
        return True

    elapsed_minutes = (current_time - last_run_time).total_seconds() / 60

    print(f"Time check - Current: {current_time}, Last: {last_run_time}, Elapsed: {elapsed_minutes:.2f} min")

    if elapsed_minutes < 0:
        print(f"Warning: Last run time is in the future. Clock skew or bad data? Skipping.")
        return False

    # Simple check: has it been roughly 15 minutes?
    if elapsed_minutes >= 14:
        print(f"Running: {elapsed_minutes:.1f} minutes since last run (Threshold: 14m).")
        return True

    print(f"Skipping: Only {elapsed_minutes:.1f} minutes since last run (Threshold: 14m).")
    return False

def get_last_run_time():
    if not os.path.exists(DATA_FILE):
        return None

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            # Read all lines is fine for this file size
            lines = f.readlines()
            if len(lines) < 2: # Header only or empty
                return None

            # Get the last non-empty line
            last_line = ""
            for line in reversed(lines):
                if line.strip():
                    last_line = line.strip()
                    break

            if not last_line or last_line.startswith("scraped_at"):
                return None

            # CSV format: scraped_at,target_date,...
            # 2026-01-19 00:16:55
            timestamp_str = last_line.split(',')[0]
            # Parse as Peru time (since that's what is in the CSV)
            return datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("America/Lima"))
    except Exception as e:
        print(f"Error reading last run time: {e}")
        return None

def run():
    # Compare with current Peru time
    current_time = datetime.datetime.now(ZoneInfo("America/Lima"))
    last_run = get_last_run_time()

    if not should_run(last_run, current_time):
        print("Scraper decided not to run at this time.")
        return

    print(f"Starting scrape at {current_time}")
    
    scraped_data = []
    
    with sync_playwright() as p:
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            timezone_id="America/Lima",
            locale="es-PE",
            user_agent=user_agent
        )
        page = context.new_page()

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            print(f"\n--- Attempt {attempt} of {max_attempts} ---")
            scraped_data = [] # Reset for this attempt
            target_date = None

            try:
                print(f"Navigating to {URL}...")

                # Wait for the specific availability response
                # We use a try/except block for expect_response to handle timeouts gracefully within the loop
                try:
                    with page.expect_response(
                        lambda r: "disponibilidad-actual" in r.url and r.status == 200,
                        timeout=30000 # 30 seconds timeout for the network request
                    ) as response_info:
                        page.goto(URL, wait_until="domcontentloaded", timeout=60000)

                    response = response_info.value
                    print("Intercepted availability response")

                    # Try to extract target date from the request payload
                    try:
                        req_json = response.request.post_data_json
                        if req_json and 'fecha' in req_json:
                            target_date = req_json['fecha']
                            print(f"Detected target date: {target_date}")
                    except Exception as e:
                        print(f"Error parsing request payload: {e}")

                    # Parse the response data
                    try:
                        data = response.json()
                        if isinstance(data, list):
                            # Use current time as scrape time
                            scrape_time = datetime.datetime.now(ZoneInfo("America/Lima")).strftime("%Y-%m-%d %H:%M:%S")
                            
                            for item in data:
                                # Calculate sold
                                capacity = item.get('ncupo', 0)
                                available = item.get('ncupoActual', 0)
                                sold = capacity - available

                                row = {
                                    "scraped_at": scrape_time,
                                    "target_date": target_date if target_date else "Unknown",
                                    "route_name": item.get('ruta'),
                                    "capacity": capacity,
                                    "available": available,
                                    "sold": sold
                                }
                                scraped_data.append(row)

                            print(f"Parsed {len(scraped_data)} rows from response.")
                    except Exception as e:
                        print(f"Error parsing response JSON: {e}")

                except Exception as e:
                    print(f"Network request timeout or error: {e}")

                # If we got data, try to verify/backfill date from UI if missing
                if scraped_data:
                    # Wait a bit for UI to settle to read the visible date
                    page.wait_for_timeout(2000)

                    try:
                        element = page.get_by_text("Disponibilidad para el día")
                        if element.count() > 0:
                            parent_text = element.first.evaluate("el => el.parentElement.innerText")
                            date_match = re.search(r"(\d{2})/(\d{2})/(\d{4})", parent_text)
                            if date_match:
                                day, month, year = date_match.groups()
                                visible_date = f"{year}-{month}-{day}"
                                print(f"Visible date on page: {visible_date}")

                                if target_date and target_date != visible_date:
                                    print(f"WARNING: Mismatch between intercepted date ({target_date}) and visible date ({visible_date})")
                                elif not target_date:
                                    print(f"Intercepted date missing. Using visible date: {visible_date}")
                                    target_date = visible_date
                                    # Backfill scraped data
                                    for row in scraped_data:
                                        row["target_date"] = visible_date
                        else:
                            print("'Disponibilidad para el día' text not found.")
                    except Exception as e:
                        print(f"Error scraping visible date: {e}")

                    # If successful, break the retry loop
                    print("Scrape successful.")
                    break
                else:
                    print("Response received but no data extracted.")

            except Exception as e:
                print(f"Attempt {attempt} failed with unexpected error: {e}")

            # If not the last attempt, wait before retrying
            if attempt < max_attempts:
                wait_time = 10
                print(f"Waiting {wait_time}s before next attempt...")
                time.sleep(wait_time)
        
        browser.close()

    if not scraped_data:
        print("No data scraped after all attempts.")
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
