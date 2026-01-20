from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import time
import datetime
import json

class IncaRailScraper:
    def __init__(self):
        self.base_url = "https://zonasegura.incarail.com/itinerario/buscar?language=en"

    def scrape(self, weeks=2):
        results = {}
        dates = self._get_dates(weeks)
        routes = ["Ollantaytambo - Machu Picchu", "Cusco - Machu Picchu"]

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            for date_str in dates:
                print(f"Scraping IncaRail for {date_str}...")
                week_str = self._get_week_str(date_str)
                if week_str not in results:
                    results[week_str] = {
                        "date": date_str,
                        "trains": []
                    }

                for route in routes:
                    print(f"  Route: {route}")
                    trains = self._scrape_date_route(page, date_str, route)
                    # Add route info to trains
                    for t in trains:
                        t["route"] = route
                    results[week_str]["trains"].extend(trains)

            browser.close()
        return results

    def _get_dates(self, weeks):
        dates = []
        today = datetime.date.today()
        # Find next monday
        days_ahead = 0 - today.weekday()
        if days_ahead <= 0: # Target Monday already happened this week
            days_ahead += 7
        next_monday = today + datetime.timedelta(days=days_ahead)

        for i in range(weeks):
            d = next_monday + datetime.timedelta(weeks=i)
            dates.append(d.strftime("%Y-%m-%d"))

        return dates

    def _get_week_str(self, date_str):
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        year, week, _ = d.isocalendar()
        return f"{year}-W{week:02d}"

    def _scrape_date_route(self, page, date_str, route_name):
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        date_visible = d.strftime("%m/%d/%Y")
        date_hidden = d.strftime("%d/%m/%Y")

        try:
            page.goto(self.base_url, timeout=60000)
            page.wait_for_timeout(3000)

            # 1. Select One Way
            try:
                page.locator("label:has-text('One way')").click(timeout=2000)
            except:
                page.click("#soloIda")

            # 2. Select Route
            try:
                page.click(".contenedor-estacion")
                page.wait_for_timeout(500)
                # Click the specific route
                page.click(f"text={route_name}")
            except Exception as e:
                print(f"Error selecting route {route_name}: {e}")
                return []

            # 3. Set Date
            js_script = f"""
            () => {{
                let el = document.querySelector('.input-fec-viaje-ida');
                if (el) {{
                    el.removeAttribute('readonly');
                    el.value = '{date_visible}';
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
                let hidden = document.querySelector('input[name="fecViajeIda"]');
                if (hidden) {{
                    hidden.value = '{date_hidden}';
                    let hiddenRet = document.querySelector('input[name="fecViajeRegreso"]');
                    if (hiddenRet) hiddenRet.value = '{date_hidden}';

                    hidden.dispatchEvent(new Event('input'));
                    hidden.dispatchEvent(new Event('change'));
                }}
            }}
            """
            page.evaluate(js_script)

            # 4. Search
            page.click("#botonBuscar")

            # Wait for results
            try:
                page.wait_for_selector(".contenedor-cabecera", timeout=30000)
            except:
                print(f"Timeout waiting for results (selector .contenedor-cabecera) or no trains found for {route_name}.")
                return []

            # Parse results
            content = page.content()
            return self._parse_html(content)

        except Exception as e:
            print(f"Error scraping {date_str} {route_name}: {e}")
            return []

    def _parse_html(self, html):
        soup = BeautifulSoup(html, "html.parser")
        trains = []

        # Remove modals
        for modal in soup.find_all(id=re.compile("modal")):
            modal.decompose()

        cards = soup.select(".card-itinerario")
        if not cards:
            cards = soup.select(".contenedor-cabecera")

        for card in cards:
            try:
                name_el = card.select_one(".nom-servicio")
                if not name_el: continue
                name = name_el.get_text(strip=True)

                dep_el = card.select_one(".contenedor-detalle-horario.salida .des-hora")
                departure = dep_el.get_text(strip=True) if dep_el else "N/A"

                arr_el = card.select_one(".contenedor-detalle-horario.llegada .des-hora")
                arrival = arr_el.get_text(strip=True) if arr_el else "N/A"

                price_el = card.select_one(".precio")
                price = price_el.get_text(strip=True) if price_el else "N/A"

                trains.append({
                    "name": name,
                    "departure": departure,
                    "arrival": arrival,
                    "price": price
                })
            except Exception as e:
                print(f"Error parsing card: {e}")
                continue

        return trains

if __name__ == "__main__":
    scraper = IncaRailScraper()
    print(json.dumps(scraper.scrape(weeks=2), indent=2))
