from datetime import datetime, timedelta
import requests

# ==========================================================
# Standardtexte
# ==========================================================

# ==========================================================
# Automatische Beschreibungen nach Kategorie
# ==========================================================

KATEGORIEN = {

    "SPORT": {
        "keywords": [
            "SPORT", "ARENA", "EUROSPORT", "ESPN",
            "DAZN", "SPORTKLUB", "SPORT KLUB",
            "SKY SPORT", "NBA", "FIGHT"
        ],

        "DE": "{sender} zeigt Live-Sport, Fußball, Basketball, Tennis, Motorsport und viele weitere Sportereignisse.",

        "EXYU": "{sender} donosi prijenose sportskih događaja uživo, fudbal, košarku, tenis i mnoge druge sportove.",

        "EN": "{sender} brings you live sports, football, basketball, tennis, motorsports and many other sporting events."
    },


    "MUSIK": {
        "keywords": [
            "MUSIC", "MTV", "VH1", "DM SAT",
            "MELODY", "JUKEBOX", "HIT",
            "MUSIC BOX", "CLUB"
        ],

        "DE": "{sender} bietet Musikvideos, Konzerte, Charts und Unterhaltung rund um die Uhr.",

        "EXYU": "{sender} emituje muzičke spotove, koncerte, zabavne emisije i najveće hitove tokom cijelog dana.",

        "EN": "{sender} features music videos, concerts, chart hits and entertainment throughout the day."
    },


    "FILM": {
        "keywords": [
            "FILM", "MOVIE", "ACTION",
            "CINEMA", "FILMBOX", "HBO",
            "CINEMAX", "HOLLYWOOD"
        ],

        "DE": "{sender} zeigt Spielfilme, Serien, Blockbuster und Unterhaltung für die ganze Familie.",

        "EXYU": "{sender} prikazuje filmove, serije, akcione hitove i vrhunsku zabavu za cijelu porodicu.",

        "EN": "{sender} offers blockbuster movies, TV series and entertainment for the whole family."
    },


    "NEWS": {
        "keywords": [
            "NEWS", "N1", "CNN", "BBC",
            "INFO", "AL JAZEERA",
            "EURONEWS"
        ],

        "DE": "{sender} berichtet über aktuelle Nachrichten, Politik, Wirtschaft und internationale Ereignisse.",

        "EXYU": "{sender} donosi najnovije vijesti, informacije, političke i društvene događaje iz zemlje i svijeta.",

        "EN": "{sender} delivers the latest news, politics, business and world events around the clock."
    },


    "KINDER": {
        "keywords": [
            "DISNEY", "NICK", "NICK JR",
            "CARTOON", "BOOMERANG",
            "MINI", "KIDS"
        ],

        "DE": "{sender} bietet Zeichentrickfilme, Serien und Unterhaltung für Kinder und die ganze Familie.",

        "EXYU": "{sender} nudi crtane filmove, serije i zabavni sadržaj za djecu i cijelu porodicu.",

        "EN": "{sender} offers cartoons, children's series and family entertainment throughout the day."
    },


    "DOKU": {
        "keywords": [
            "DISCOVERY",
            "NAT GEO",
            "NATIONAL",
            "HISTORY",
            "ANIMAL",
            "PLANET",
            "DOC"
        ],

        "DE": "{sender} zeigt Dokumentationen über Natur, Wissenschaft, Geschichte und spannende Entdeckungen.",

        "EXYU": "{sender} prikazuje dokumentarne emisije, prirodu, nauku, istoriju i zanimljivosti iz cijelog svijeta.",

        "EN": "{sender} features documentaries about nature, science, history and fascinating discoveries."
    }
}


DE_STANDARD = [
    "Willkommen beim Programm von {sender}. Freuen Sie sich auf abwechslungsreiche Unterhaltung während des ganzen Tages."
]

EXYU_STANDARD = [
    "Dobro došli u program {sender}. Očekuje vas raznovrstan sadržaj tokom cijelog dana."
]

EN_STANDARD = [
    "Welcome to {sender}. Enjoy a wide variety of entertainment throughout the day."
]


# ==========================================================
# Automatische Beschreibung
# ==========================================================

def standard_beschreibung(land, sender):

    if land == "DE":
        sprache = "DE"

    elif land in ["BA", "RS", "HR", "ME", "CG", "MNE", "MNG", "MO", "MK", "SI"]:
        sprache = "EXYU"

    else:
        sprache = "EN"

    sender_upper = sender.upper()

    for daten in KATEGORIEN.values():

        for keyword in daten["keywords"]:

            if keyword in sender_upper:
                return daten[sprache].format(sender=sender)

    if sprache == "DE":
        texte = DE_STANDARD

    elif sprache == "EXYU":
        texte = EXYU_STANDARD

    else:
        texte = EN_STANDARD

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
logos = {}

try:
    with open("logos.txt", "r", encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.strip()

            if not zeile or zeile.startswith("#"):
                continue

            teile = [x.strip() for x in zeile.split("|", 2)]

            if len(teile) == 3:
                kanal = f"{teile[0]}|{teile[1]}"
                logos[kanal] = teile[2]

except FileNotFoundError:
    pass


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
        kanal = f"{land}|{sender}"

        if kanal in logos:
              logo = logos[kanal]

        if beschreibung == "":
            beschreibung = standard_beschreibung(land, sender)

           

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
