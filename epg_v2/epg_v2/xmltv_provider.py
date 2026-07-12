import gzip
import requests
import xml.etree.ElementTree as ET


class XMLTVProvider:

    def __init__(self):
        self.sources = []

    def add_source(self, name, url):
        self.sources.append({
            "name": name,
            "url": url
        })

    def download(self):

        daten = []

        for quelle in self.sources:

            print(f"Lade {quelle['name']}...")

            try:

                response = requests.get(
                    quelle["url"],
                    timeout=60
                )

                response.raise_for_status()

                content = response.content

                if quelle["url"].endswith(".gz"):
                    content = gzip.decompress(content)

                xml = ET.fromstring(content)

                daten.append({
                    "name": quelle["name"],
                    "xml": xml
                })

                print(f"✓ {quelle['name']} geladen")

            except Exception as e:

                print(f"✗ Fehler bei {quelle['name']}: {e}")

        return daten