from datetime import datetime, timedelta
import requests
import xml.etree.ElementTree as ET
import re

xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'

sender_daten = []

# --------------------------------------------------
# TVPROFIL
# --------------------------------------------------

def tvprofil_id(sender):

    name = sender.upper()

    entfernen = [
        "BA|",
        "DE|",
        "HD",
        "FHD",
        "UHD",
        "VIP",
        "RAW"
    ]

    for e in entfernen:
        name = name.replace(e, "")

    name = name.strip()

    bekannte = {
        "HERCEG TV": "herceg-tv.ba",
        "HAYAT": "hayat-tv.ba",
        "BN2 TV": "bn-tv.ba",
        "AL JAZEERA BALKANS": "al-jazeera-balkans.ba",
        "RTV SLON": "rtv-slon.ba",
        "RTV USK": "rtv-usk.ba"
    }

    if name in bekannte:
        return bekannte[name]

    name = re.sub(r"\s+", "-", name)
    

    if not name.endswith(".ba"):
        name += ".ba"

    return name
    print("SUCHE:", tvprofil_id("DE|SKY GO FILME 1 FHD"))
    print("SUCHE:", tvprofil_id("DE|SKY GO FILME 10 FHD"))

# --------------------------------------------------
# sender.txt einlesen
# --------------------------------------------------

with open("sender.txt", "r", encoding="utf-8") as f:
    sender_liste = [zeile.strip() for zeile in f if zeile.strip()]

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

# --------------------------------------------------
# DYN PPV 1-20
# --------------------------------------------------

dyn_logo = "https://www.dslweb.de/public/resources/images/anbieter/dyn/dyn-teaser.jpg"

for i in range(1, 21):

    kanal = f"DE| DYN PPV {i} HD"

    xml += f"""
    <channel id="{kanal}">
        <display-name>{kanal}</display-name>
        <icon src="{dyn_logo}"/>
    </channel>
"""

# --------------------------------------------------
# Standard-EPG für normale Sender
# --------------------------------------------------

starttag = datetime.utcnow().replace(
    hour=0,
    minute=0,
    second=0,
    microsecond=0
)

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

# --------------------------------------------------
# DYN LIVE EVENTS
# --------------------------------------------------

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
    print("Dyn Fehler:", e)

# --------------------------------------------------
# Leerzeiten füllen
# --------------------------------------------------

jetzt = datetime.utcnow()

for i in range(1, 21):

    kanal = f"DE| DYN PPV {i} HD"

    for stunde in range(24 * 30):

        start_dummy = jetzt + timedelta(hours=stunde)
        ende_dummy = start_dummy + timedelta(hours=1)

        start_str = start_dummy.strftime("%Y%m%d%H%M%S +0000")
        ende_str = ende_dummy.strftime("%Y%m%d%H%M%S +0000")

        xml += f"""
    <programme start="{start_str}" stop="{ende_str}" channel="{kanal}">
        <title>Im Moment keine Live Events, bleib dran</title>
        <desc>Im Moment keine Live Events, bleib dran</desc>
    </programme>
"""
# --------------------------------------------------
# TVPROFIL IMPORT
# --------------------------------------------------

# --------------------------------------------------
# TVPROFIL XMLTV IMPORT
# --------------------------------------------------

# --------------------------------------------------
# TVPROFIL XMLTV IMPORT
# --------------------------------------------------

print("Lade TVProfil XMLTV...")

try:
    response = requests.get(
        "https://tvprofil.net/xmltv/data/epg_tvprofil.net.xml",
        timeout=120
    )

    if response.status_code == 200:
        root = ET.fromstring(response.content)

        programme = root.findall("programme")
        tvprofil_channels = {}

        # TVProfil-Sender sammeln
        for channel in root.findall("channel"):
            cid = channel.get("id")
            display = ""

            dn = channel.find("display-name")
            if dn is not None and dn.text:
                display = dn.text.lower()

            tvprofil_channels[cid] = display

        # Debug-Datei erzeugen
        with open("tvprofil_channels.txt", "w", encoding="utf-8") as f:
            for cid, name in sorted(tvprofil_channels.items()):
                f.write(f"{cid}|{name}\n")

        print("TVProfil Sender exportiert:", len(tvprofil_channels))
        print("TVProfil Programme geladen:", len(programme))

        for eintrag in programme:
    channel = eintrag.get("channel", "").lower()

    for kanal, beschreibung in sender_daten.items():
        print("MEIN SENDER:", kanal, "->", tvprofil_id(kanal))

        sender = tvprofil_id(kanal)

        if sender and sender.replace(".ba", "") in channel:
            eintrag.set("channel", kanal)
            break

    xml += ET.tostring(
        eintrag,
        encoding="unicode"
    )    
except Exception as e:
    print("TVProfil Fehler:", e)        
print("EPG-Datei erfolgreich erstellt.")
    
