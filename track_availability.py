import json
import csv
import os
import datetime
import time
from playwright.sync_api import sync_playwright

DATA_FILE = "data/availability_log.csv"
URL = "https://tuboleto.cultura.pe/disponibilidad/llaqta_machupicchu"

def run():
    print(f"Starting scrape at {datetime.datetime.now()}")
    
    scraped_data = []
    
    # We use a mutable container to store the date because of closure scope
    context_data = {"target_date": None}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
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
                        scrape_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
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
        
        browser.close()

    if not scraped_data:
        print("No data scraped.")
        return

    # Write to CSV
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
