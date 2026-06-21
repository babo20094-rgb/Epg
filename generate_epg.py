from datetime import datetime, timedelta
import requests

xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'

sender_daten = []

# sender.txt einlesen
with open("sender.txt", "r", encoding="utf-8") as f:
    sender_liste = [zeile.strip() for zeile in f if zeile.strip()]

# Normale Sender anlegen
for zeile in sender_liste:

    teile = [x.strip() for x in zeile.split("|")]

    if len(teile) < 3:
        continue

    land = teile[0]
    sendername = teile[1]
    beschreibung = teile[2]

    logo = ""
    if len(teile) >= 4:
        logo = teile[3]

    kanal = f"{land}|{sendername}"

    sender_daten.append((kanal, beschreibung))

    xml += f"""
    <channel id="{kanal}">
        <display-name>{sendername}</display-name>
        <icon src="{logo}"/>
    </channel>
"""

# 20 Dyn-Kanäle hinzufügen
for i in range(1, 21):
    xml += f"""
    <channel id="DE| DYN PPV {i} HD">
        <display-name>DE| DYN PPV {i} HD</display-name>
    </channel>
"""

# Dummy-EPG für alle normalen Sender
starttag = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

for tag in range(365):

    start = starttag + timedelta(days=tag)
    ende = start + timedelta(days=1)

    start_str = start.strftime("%Y%m%d%H%M%S +0000")
    ende_str = ende.strftime("%Y%m%d%H%M%S +0000")

    for kanal, beschreibung in sender_daten:

        xml += f"""
    <programme start="{start_str}" stop="{ende_str}" channel="{kanal}">
        <title>{beschreibung}</title>
        <desc>{beschreibung}</desc>
    </programme>
"""

# Dyn Sport abrufen
try:

    response = requests.get(
        "https://streaming.contentdesk.sport/api/public/live-productions",
        timeout=30
    )

    if response.status_code == 200:

        daten = response.json()

        kanal_nummer = 1

        for eintrag in daten:

            titel = eintrag.get("title", "Dyn Sport")

            start = eintrag.get("scheduledAt")
            ende = eintrag.get("scheduledEnd")

            if not start or not ende:
                continue

            startzeit = datetime.fromisoformat(
                start.replace("Z", "+00:00")
            ).strftime("%Y%m%d%H%M%S +0000")

            endzeit = datetime.fromisoformat(
                ende.replace("Z", "+00:00")
            ).strftime("%Y%m%d%H%M%S +0000")

            kanal = f"DE| DYN PPV {kanal_nummer} HD"

            beschreibung = eintrag.get("description", titel)

            xml += f"""
    <programme start="{startzeit}" stop="{endzeit}" channel="{kanal}">
        <title>{titel}</title>
        <desc>{beschreibung}</desc>
    </programme>
"""

            kanal_nummer += 1

            if kanal_nummer > 20:
                kanal_nummer = 1

except Exception as e:
    print("Dyn Sport Fehler:", e)

xml += "\n</tv>"

with open("Epg_365_Tage.xml", "w", encoding="utf-8") as f:
    f.write(xml)

print("EPG-Datei erfolgreich erstellt.")
