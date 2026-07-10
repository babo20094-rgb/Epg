from datetime import datetime, timedelta
import requests

# ==========================================================
# Standardtexte
# ==========================================================

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


# ==========================================================
# Automatische Beschreibung
# ==========================================================

def standard_beschreibung(land, sender):

    if land == "DE":
        texte = DE_TEXTE

    elif land in ["BA", "RS", "HR", "ME", "CG", "MNE", "MNG", "MO", "MK", "SI"]:
        texte = EXYU_TEXTE

    elif land in ["UK", "US", "CA", "AU", "SO"]:
        texte = EN_TEXTE

    else:
        texte = EN_TEXTE

    nummer = sum(ord(c) for c in sender) % len(texte)

    return texte[nummer].format(sender=sender)
    
def sender_anzeigename(name):
    AUSNAHMEN = {
        "HD", "UHD", "FHD", "SD", "HEVC", "4K", "8K",
        "TV", "RTL", "ORF", "SRF", "HRT", "RTS",
        "RTRS", "BHT", "CNN", "BBC", "SKY",
        "HBO", "AMC", "AXN", "MTV"
    }

    worte = []

    for wort in name.split():
        if wort.upper() in AUSNAHMEN:
            worte.append(wort.upper())
        else:
            worte.append(wort.capitalize())

    return " ".join(worte)
def sender_oder_titel(name):
    worte = name.split()

    if all(
        wort.isupper() or
        wort.isdigit() or
        wort.upper() in AUSNAHMEN
        for wort in worte
    ):
        return sender_anzeigename(name)

    return sender_anzeigename(name)


# ==========================================================
# XML starten
# ==========================================================

xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'

sender_daten = []


# ==========================================================
# sender.txt lesen
#
# Format:
#
# DE|RTL|
# DE|SAT.1||
# DE|RTL||https://...
# BA|HAYAT|Eigene Beschreibung|
#
# ==========================================================

with open("sender.txt", "r", encoding="utf-8") as f:

    for zeile in f:

        zeile = zeile.strip()

        if not zeile:
            continue

        teile = [x.strip() for x in zeile.split("|")]

        while len(teile) < 4:
            teile.append("")

        land = teile[0]
        sender = teile[1]

        beschreibung = teile[2]
        logo = teile[3]

        if beschreibung == "":
            beschreibung = standard_beschreibung(land, sender)

        kanal = f"{land}|{sender}"

        sender_daten.append({
            "kanal": kanal,
            "sender": sender,
            "beschreibung": beschreibung,
            "logo": logo
        })

        xml += f"""
<channel id="{kanal}">
    <display-name>{sender_anzeigename(sender)}</display-name>
"""

        if logo:
            xml += f'    <icon src="{logo}"/>\n'

        xml += "</channel>\n"
        # ==========================================================
# DYN PPV CHANNELS
# ==========================================================

dyn_logo = "https://www.dslweb.de/public/resources/images/anbieter/dyn/dyn-teaser.jpg"

for i in range(1, 21):

    kanal = f"DE|DYN PPV {i} HD"

    xml += f"""
<channel id="{kanal}">
    <display-name>DYN PPV {i} HD</display-name>
    <icon src="{dyn_logo}"/>
</channel>
"""


# ==========================================================
# STANDARD-EPG
# ==========================================================

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

    for daten in sender_daten:

        xml += f"""
<programme
    start="{start_str}"
    stop="{ende_str}"
    channel="{daten['kanal']}">

<title>{sender_anzeigename(daten['sender'])}</title>

<desc>{daten['beschreibung']}</desc>

</programme>
"""
# ==========================================================
# DYN LIVE EVENTS
# ==========================================================

try:

    response = requests.get(
        "https://streaming.contentdesk.sport/api/public/live-productions",
        timeout=30
    )

    if response.status_code == 200:

        daten = response.json()

        kanal_nummer = 1

        for event in daten:

            titel = event.get("title", "Dyn Sport")

            beschreibung = event.get("description", titel)

            start = event.get("scheduledAt")
            ende = event.get("scheduledEnd")

            if not start or not ende:
                continue

            startzeit = datetime.fromisoformat(
                start.replace("Z", "+00:00")
            ).strftime("%Y%m%d%H%M%S +0000")

            endzeit = datetime.fromisoformat(
                ende.replace("Z", "+00:00")
            ).strftime("%Y%m%d%H%M%S +0000")

            kanal = f"DE|DYN PPV {kanal_nummer} HD"

            xml += f"""
<programme
    start="{startzeit}"
    stop="{endzeit}"
    channel="{kanal}">

<title>{titel}</title>

<desc>{beschreibung}</desc>

</programme>
"""

            kanal_nummer += 1

            if kanal_nummer > 20:
                kanal_nummer = 1

except Exception as e:

    print("DYN Fehler:", e)


# ==========================================================
# DYN LEERZEITEN
# ==========================================================

jetzt = datetime.utcnow().replace(
    hour=0,
    minute=0,
    second=0,
    microsecond=0
)

for i in range(1, 21):

    kanal = f"DE|DYN PPV {i} HD"

    for stunde in range(24 * 3):

        start = jetzt + timedelta(hours=stunde)
        ende = start + timedelta(hours=1)

        start_str = start.strftime("%Y%m%d%H%M%S +0000")
        ende_str = ende.strftime("%Y%m%d%H%M%S +0000")

        xml += f"""
<programme
    start="{start_str}"
    stop="{ende_str}"
    channel="{kanal}">

<title>Im Moment keine Live Events, bleib dran</title>

<desc>Im Moment keine Live Events, bleib dran.</desc>

</programme>
"""
# ==========================================================
# XML ABSCHLIESSEN
# ==========================================================

xml += "\n</tv>"

with open("Epg_365_Tage.xml", "w", encoding="utf-8") as f:
    f.write(xml)

print(f"EPG erfolgreich erstellt ({len(sender_daten)} Sender).")
