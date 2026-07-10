from datetime import datetime, timedelta
import requests
# --------------------------------------------------
# Standardbeschreibungen
# --------------------------------------------------

DE_TEXTE = [
    "Willkommen beim Programm von {sender}. Freuen Sie sich auf ein abwechslungsreiches Programm mit Filmen, Serien, Dokumentationen, Nachrichten und Unterhaltung rund um die Uhr.",

    "{sender} bietet Ihnen täglich ein vielfältiges Programm mit spannenden Filmen, beliebten Serien, informativen Dokumentationen und bester Unterhaltung.",

    "Genießen Sie das Programm von {sender} mit abwechslungsreichen Sendungen, aktuellen Informationen, Filmen, Serien und vielen weiteren interessanten Inhalten."
]

EXYU_TEXTE = [
    "Dobro došli u program {sender}. Očekuje vas raznovrstan sadržaj sa filmovima, serijama, dokumentarcima, zabavnim emisijama i drugim zanimljivim programima tokom cijelog dana.",

    "{sender} donosi bogat izbor filmova, serija, sportskih događaja, dokumentaraca i zabavnih emisija za sve generacije.",

    "Uživajte u programu {sender} uz kvalitetne filmove, serije, informativne emisije, dokumentarce i raznovrsnu zabavu."
]

EN_TEXTE = [
    "Welcome to {sender}. Enjoy a wide selection of movies, series, documentaries, news and entertainment throughout the day.",

    "{sender} brings you a diverse schedule featuring movies, TV shows, documentaries, live events and quality entertainment.",

    "Enjoy the programming on {sender} with a great mix of entertainment, films, series, documentaries and much more."
]
def standard_beschreibung(land, sender):

    if land == "DE":
        texte = DE_TEXTE

    elif land in ["BA", "RS", "HR", "ME", "MK"]:
        texte = EXYU_TEXTE

    elif land in ["UK", "US", "CA", "AU", "SO"]:
        texte = EN_TEXTE

    else:
        texte = EN_TEXTE

    nummer = sum(ord(c) for c in sender) % len(texte)

    return texte[nummer].format(sender=sender)
xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'

sender_daten = []

# ----------------------------------------------------
# Sender aus sender.txt einlesen
# Format:
# DE|WILDER PLANET|Wilder Planet Dokumentationen|
# BA|HAYAT PLUS|Hayat Plus Programm|
# US|CNN|CNN News|
# ----------------------------------------------------

sender_daten = []

with open("sender.txt", "r", encoding="utf-8") as f:
    sender_liste = [zeile.strip() for zeile in f if zeile.strip()]

for zeile in sender_liste:

    teile = [x.strip() for x in zeile.split("|")]

    # mindestens Land | Sender | Beschreibung
    if len(teile) < 3:
        continue

    land = teile[0]
    sendername = teile[1]
    beschreibung = teile[2]

    logo = ""
    if len(teile) >= 4:
        logo = teile[3]

    # universelle Kanal-ID
    kanal = f"{land}|{sendername}"

    # für spätere Programme merken
    sender_daten.append((kanal, sendername))

    # Channel erzeugen
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

for stunde in range(0, 24 * 7, 4):

    start = starttag + timedelta(hours=stunde)
    ende = start + timedelta(hours=4)

    start_str = start.strftime("%Y%m%d%H%M%S +0000")
    ende_str = ende.strftime("%Y%m%d%H%M%S +0000")

for kanal, beschreibung in sender_daten:

    land = kanal.split("|", 1)[0]
    sender = kanal.split("|", 1)[1]

    titel = sender
    beschreibung = standard_beschreibung(land, sender)

    xml += f"""
    <programme start="{start_str}" stop="{ende_str}" channel="{kanal}">
        <title>{titel}</title>
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

jetzt = datetime.utcnow().replace(
             hour=0,
             minute=0,
             second=0,
             microsecond=0
)       

for i in range(1, 21):

    kanal = f"DE| DYN PPV {i} HD"

    for stunde in range(24 * 3):

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

        xml += f"""
<programme start="{start_str}"
           stop="{ende_str}"
           channel="{kanal}">
    <title>{beschreibung}</title>
    <desc>{beschreibung}</desc>
</programme>
"""
xml += "\n</tv>"

with open("Epg_365_Tage.xml", "w", encoding="utf-8") as f:
    f.write(xml)

print("EPG-Datei erfolgreich erstellt.")
    
