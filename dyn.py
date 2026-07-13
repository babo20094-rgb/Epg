import requests
from bs4 import BeautifulSoup
import re

DYN_API = "https://streaming.contentdesk.sport/api/public/live-productions"


def get_dyn_events():
    try:
        response = requests.get(DYN_API, timeout=30)

        print("DYN HTTP:", response.status_code)

        if response.status_code == 200:

    daten = response.json()
    print(daten)

    print("DYN HTTP:", response.status_code)
    print("DYN Events:", len(daten))

    kanal_nummer = 1

        return daten

    except Exception as e:
        print("DYN Fehler:", e)
        return []