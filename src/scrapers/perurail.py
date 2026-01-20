import requests
from bs4 import BeautifulSoup
import re

class PeruRailScraper:
    def __init__(self):
        self.url = "https://www.perurail.com/train-schedules-and-frequencies/"

    def scrape(self):
        headers = {'User-Agent': 'Mozilla/5.0'}
        try:
            response = requests.get(self.url, headers=headers, timeout=30)
            if response.status_code != 200:
                print(f"Failed to fetch PeruRail: {response.status_code}")
                return {}
        except Exception as e:
            print(f"Error fetching PeruRail: {e}")
            return {}

        soup = BeautifulSoup(response.content, 'html.parser')
        results = {}

        # Define the blocks we want
        blocks = ["Jan - Apr", "May - Dec"]

        # Find all tab links
        links = soup.select("a.elementkit-nav-link")

        for block_name in blocks:
            target_id = None
            for link in links:
                text = link.get_text()
                # Normalize text
                if "CUSCO > MACHU PICCHU" in text.upper() and block_name in text:
                    target_id = link.get('href')
                    break

            if target_id and target_id.startswith("#"):
                content_id = target_id[1:]
                content_div = soup.find(id=content_id)
                if content_div:
                    trains = self._parse_content(content_div)
                    results[block_name] = trains
                else:
                    print(f"Content div {content_id} not found for {block_name}")
            else:
                print(f"Tab for {block_name} not found")

        return results

    def _parse_content(self, div):
        trains = []
        text_widgets = div.select(".elementor-widget-text-editor")
        full_text = []
        for w in text_widgets:
            # elementor adds <p> often
            t = w.get_text(separator="\n", strip=True)
            if t:
                full_text.append(t)

        joined_text = "\n".join(full_text)
        # Split by "Trains:" but sometimes it might be "Trains" or similar.
        # Also handle "Edit Content" which seems to appear in dump.

        parts = re.split(r'Trains:?', joined_text)

        for part in parts:
            if not part.strip(): continue
            if "Edit Content" in part: continue # Skip administrative text

            lines = [l.strip() for l in part.split('\n') if l.strip()]

            if not lines: continue

            # Find times HH:MM
            times = []
            for i, line in enumerate(lines):
                # Search for time pattern in line
                found = re.findall(r'(\d{2}:\d{2})', line)
                if found:
                    for t in found:
                        times.append((i, t))

            if len(times) >= 2:
                name = lines[0]
                # Filter out garbage names like "Regular Service" if it appears first
                if name in ["Regular Service", "Bimodal Service"]:
                     # look backwards or forwards?
                     # Actually, split splits *after* "Trains:", so lines[0] should be the name.
                     pass

                departure = times[0][1]
                arrival = times[-1][1]

                is_bimodal = "Bimodal" in part

                trains.append({
                    "name": name,
                    "departure": departure,
                    "arrival": arrival,
                    "is_bimodal": is_bimodal
                })

        return trains
