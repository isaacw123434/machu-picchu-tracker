# Machu Picchu Ticket Tracker

This repository tracks the availability of Machu Picchu tickets every 30 minutes.

## How it works

- A Python script (`track_availability.py`) uses [Playwright](https://playwright.dev/) to visit the [official ticket website](https://tuboleto.cultura.pe/disponibilidad/llaqta_machupicchu).
- It intercepts the network request that fetches the availability data.
- It extracts the number of available tickets for each route (including "Ruta 2-A: Clásico Diseñada") and saves it to a CSV file.
- A GitHub Action workflow runs this script every 30 minutes and commits the updated data to the repository.

## Data

The data is stored in `data/availability_log.csv`. The columns are:

- `scraped_at`: Timestamp of when the data was collected.
- `target_date`: The date for which the tickets are being checked (usually the next available date shown by default on the website).
- `route_name`: Name of the route (e.g., "Ruta 2-A: Clásico Diseñada").
- `capacity`: Total capacity for that route.
- `available`: Number of tickets currently available.
- `sold`: Number of tickets sold (Capacity - Available).

## Running Locally

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. Run the script:
   ```bash
   python track_availability.py
   ```

3. Check `data/availability_log.csv` for the results.

## Analysis

You can analyze the CSV file to understand:
- At what time tickets sell out.
- Differences between high and low season (by tracking over time).
- Specific availability for Ruta 2-A.
