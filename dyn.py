import requests

DYN_API = "https://streaming.contentdesk.sport/api/public/live-productions"


def get_dyn_events():
    try:
        response = requests.get(DYN_API, timeout=30)

        print("DYN HTTP:", response.status_code)

        if response.status_code != 200:
            return []

        daten = response.json()

        print("DYN Events:", len(daten))

        return daten

    except Exception as e:
        print("DYN Fehler:", e)
        return []