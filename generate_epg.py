from datetime import datetime, timedelta
import requests
import gzip
import xml.etree.ElementTree as ET
import os

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
    },
    "UNTERHALTUNG": {
        "keywords": [
            "RTL", "VOX", "PRO7", "PROSIEBEN", "SAT.1",
            "SAT1", "KABEL", "PINK", "PRVA", "B92",
            "HAYAT", "OBN", "NOVA", "KANAL", "TV"
        ],

        "DE": "{sender} bietet abwechslungsreiche Unterhaltung mit Shows, Serien, Filmen und spannenden Sendungen für die ganze Familie.",

        "EXYU": "{sender} donosi zabavne emisije, serije, filmove i raznovrstan program za cijelu porodicu.",

        "EN": "{sender} offers a wide range of entertainment including TV shows, series, movies and family programming."
    },

    "COMEDY": {
        "keywords": [
            "COMEDY", "HUMOR"
        ],

        "DE": "{sender} zeigt Comedy, Satire, Sitcoms und beste Unterhaltung rund um die Uhr.",

        "EXYU": "{sender} prikazuje humoristične emisije, komedije, sitkome i zabavni sadržaj tokom cijelog dana.",

        "EN": "{sender} features comedy shows, sitcoms, stand-up performances and entertainment."
    },

    "RELIGION": {
        "keywords": [
            "EWTN", "KTV", "LIFE", "DUH", "ISLAM",
            "HRAM", "SVET", "HUDA"
        ],

        "DE": "{sender} sendet religiöse Programme, Gottesdienste, Dokumentationen und inspirierende Inhalte.",

        "EXYU": "{sender} emituje vjerske emisije, bogosluženja, dokumentarce i duhovni sadržaj.",

        "EN": "{sender} broadcasts religious programming, services, documentaries and inspirational content."
    },

    "REISEN": {
        "keywords": [
            "TRAVEL", "TOUR", "TOURISM", "VACATION"
        ],

        "DE": "{sender} zeigt Reiseberichte, Urlaubsziele, Kulturen und faszinierende Orte aus aller Welt.",

        "EXYU": "{sender} prikazuje putovanja, turističke destinacije, kulture i zanimljiva mjesta širom svijeta.",

        "EN": "{sender} features travel destinations, cultures, holidays and fascinating places around the world."
    },

    "KOCHEN": {
        "keywords": [
            "FOOD", "KITCHEN", "COOK", "CUISINE"
        ],

        "DE": "{sender} bietet Kochsendungen, Rezepte, kulinarische Tipps und internationale Spezialitäten.",

        "EXYU": "{sender} donosi kulinarske emisije, recepte, savjete za kuhanje i specijalitete iz cijelog svijeta.",

        "EN": "{sender} offers cooking shows, recipes, culinary tips and international cuisine."
    },

    "NATUR": {
        "keywords": [
            "NATURE", "WILD", "ANIMAL", "SAFARI",
            "PLANET", "EARTH"
        ],

        "DE": "{sender} zeigt faszinierende Dokumentationen über Tiere, Natur und die Umwelt.",

        "EXYU": "{sender} prikazuje dokumentarne emisije o životinjama, prirodi i svijetu koji nas okružuje.",

        "EN": "{sender} features fascinating documentaries about wildlife, nature and the environment."
    },
    "SPORT": {
        "keywords": [
            "SPORT", "SPORTS", "ESPN", "EUROSPORT",
            "DAZN", "SKY SPORT", "ARENA", "NBA",
            "NFL", "NHL", "MLB", "TENNIS",
            "GOLF", "RACING", "FORMULA", "F1",
            "MOTOGP", "BOX", "FIGHT", "UFC"
        ],

        "DE": "{sender} bietet Live-Sport, Fußball, Motorsport, Tennis und viele weitere Sportereignisse aus aller Welt.",

        "EXYU": "{sender} donosi sportske prijenose uživo, fudbal, tenis, motosport i druge vrhunske sportske događaje.",

        "EN": "{sender} features live sports including football, tennis, motorsports and many major sporting events worldwide."
    },
    "FILM": {
        "keywords": [
            "CINEMA", "FILM", "MOVIE", "HOLLYWOOD",
            "HBO", "CINEMAX", "SKY CINEMA", "FOX",
            "WARNER", "PARAMOUNT", "UNIVERSAL",
            "SONY", "STAR", "AXN", "AMC",
            "SYFY", "TNT", "THRILLER"
        ],

        "DE": "{sender} zeigt Spielfilme, Blockbuster, Filmklassiker und spannende Serien rund um die Uhr.",

        "EXYU": "{sender} prikazuje filmske hitove, klasike i popularne serije tokom cijelog dana.",

        "EN": "{sender} features blockbuster movies, classic films and popular TV series throughout the day."
    },
    "KINDER": {
        "keywords": [
            "KIDS", "KID", "JR", "JUNIOR",
            "DISNEY", "CARTOON", "NICKELODEON",
            "NICK", "BOOMERANG", "BABY",
            "TOON", "CBEEBIES", "MINIMAX",
            "TINY", "POPCORN", "GULLI"
        ],

        "DE": "{sender} bietet Zeichentrick, Kinderfilme, Lernprogramme und familienfreundliche Unterhaltung für Groß und Klein.",

        "EXYU": "{sender} prikazuje crtane filmove, dječije emisije, edukativni sadržaj i zabavu za cijelu porodicu.",

        "EN": "{sender} features cartoons, children's shows, educational programs and family entertainment throughout the day."
    },
    "NEWS": {
        "keywords": [
            "NEWS", "CNN", "BBC", "SKY NEWS",
            "AL JAZEERA", "N24", "NTV", "WELT",
            "EURONEWS", "FRANCE 24", "BLOOMBERG",
            "DW", "CNBC", "FOX NEWS", "MSNBC",
            "RTRS", "RTS", "HRT", "BHT", "N1"
        ],

        "DE": "{sender} informiert rund um die Uhr über aktuelle Nachrichten, Politik, Wirtschaft und Ereignisse aus aller Welt.",

        "EXYU": "{sender} donosi najnovije vijesti, politiku, ekonomiju i aktuelna dešavanja iz cijelog svijeta.",

        "EN": "{sender} delivers breaking news, politics, business updates and major events from around the world."
    },
    "MUSIK": {
        "keywords": [
            "MUSIC", "MUSIK", "MTV", "VH1",
            "DELUXE", "CLUB", "HITS", "MEZZO",
            "TRACE", "4MUSIC", "CMC", "DM SAT",
            "FOLK", "BALKAN MUSIC", "NRJ", "KISS",
            "DANCE", "ROCK", "POP", "JAZZ"
        ],

        "DE": "{sender} präsentiert Musikvideos, Live-Konzerte, Charts und die größten Hits aus verschiedenen Musikrichtungen.",

        "EXYU": "{sender} prikazuje muzičke spotove, koncerte uživo, top liste i najveće hitove iz različitih žanrova.",

        "EN": "{sender} features music videos, live concerts, chart hits and the best songs from a variety of genres."
    },
    "UNTERHALTUNG": {
        "keywords": [
            "RTL", "VOX", "SAT", "PRO7", "PRO SIEBEN",
            "KABEL", "NOVA", "PINK", "HAPPY",
            "HAYAT", "OBN", "FACE", "ATV",
            "KANAL", "TV", "FOX", "ABC",
            "CBS", "NBC", "SHOW", "PLUS"
        ],

        "DE": "{sender} bietet ein abwechslungsreiches Programm mit Unterhaltung, Shows, Serien, Reality-TV und beliebten TV-Formaten für die ganze Familie.",

        "EXYU": "{sender} donosi raznovrstan program sa zabavnim emisijama, serijama, reality sadržajem i popularnim TV formatima za cijelu porodicu.",

        "EN": "{sender} features a wide range of entertainment including TV shows, series, reality programs and popular formats for the whole family."
    },
    "LIFESTYLE": {
        "keywords": [
            "LIFESTYLE", "STYLE", "FASHION", "HOME",
            "LIVING", "HGTV", "TLC", "BEAUTY",
            "DESIGN", "WOMAN", "LADY"
        ],

        "DE": "{sender} zeigt Sendungen rund um Wohnen, Mode, Lifestyle, Schönheit und inspirierende Ideen für den Alltag.",

        "EXYU": "{sender} donosi emisije o modi, uređenju doma, ljepoti, životnom stilu i korisnim savjetima za svakodnevni život.",

        "EN": "{sender} features programs about fashion, home improvement, beauty, lifestyle and everyday inspiration."
    },

    "KOCHEN": {
        "keywords": [
            "FOOD", "KITCHEN", "COOK", "CUISINE",
            "CHEF", "GUSTO"
        ],

        "DE": "{sender} präsentiert Kochsendungen, Rezepte, kulinarische Inspirationen und Spezialitäten aus aller Welt.",

        "EXYU": "{sender} prikazuje kulinarske emisije, recepte, savjete za kuhanje i specijalitete iz cijelog svijeta.",

        "EN": "{sender} offers cooking shows, recipes, culinary tips and delicious dishes from around the world."
    },

    "REISEN": {
        "keywords": [
            "TRAVEL", "TOUR", "TOURISM", "VACATION",
            "EXPLORE"
        ],

        "DE": "{sender} nimmt Sie mit auf spannende Reisen zu faszinierenden Orten, Kulturen und Urlaubszielen weltweit.",

        "EXYU": "{sender} vodi vas na zanimljiva putovanja kroz različite zemlje, kulture i turističke destinacije širom svijeta.",

        "EN": "{sender} takes you on exciting journeys to amazing destinations, cultures and travel experiences worldwide."
    },

    "COMEDY": {
        "keywords": [
            "COMEDY", "HUMOR", "FUNNY", "LAUGH"
        ],

        "DE": "{sender} bietet Comedy, Humor, Sitcoms und beste Unterhaltung für gute Laune den ganzen Tag.",

        "EXYU": "{sender} prikazuje humoristične emisije, sitkome i zabavni sadržaj koji će vas nasmijati tokom cijelog dana.",

        "EN": "{sender} features comedy shows, sitcoms and entertaining programs guaranteed to make you laugh."
    },

    "RELIGION": {
        "keywords": [
            "EWTN", "KTV", "LIFE", "GOD", "ISLAM",
            "QURAN", "BIBLE", "CHURCH", "SVET"
        ],

        "DE": "{sender} sendet religiöse Inhalte, Gottesdienste, Dokumentationen und inspirierende Programme.",

        "EXYU": "{sender} emituje vjerske emisije, bogosluženja, dokumentarne sadržaje i inspirativne programe.",

        "EN": "{sender} broadcasts religious services, documentaries and inspirational programming."
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
def lade_xmltv(dateiname):
    if not os.path.exists(dateiname):
        return None

    try:
        if dateiname.endswith(".gz"):
            with gzip.open(dateiname, "rb") as f:
                return ET.parse(f).getroot()
        else:
            return ET.parse(dateiname).getroot()

    except Exception as e:
        print("XMLTV Fehler:", e)
        return None


# ==========================================================
# XML starten
# ==========================================================

xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'

sender_daten = []
logos = {}
# ==========================================================
# XMLTV Quellen
# ==========================================================

XMLTV_QUELLEN = [
    "xmltv/de.xml.gz",
    "xmltv/uk.xml.gz",
    "xmltv/us.xml.gz",
    "xmltv/exyu.xml.gz"
]

xmltv_root = None

for quelle in XMLTV_QUELLEN:

    root = lade_xmltv(quelle)

    if root is not None:
        print(f"XMLTV geladen: {quelle}")
        xmltv_root = root
        break
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

<title lang="de">{sender_anzeigename(daten['sender'])}</title>

<sub-title lang="de">{daten['beschreibung']}</sub-title>

<desc lang="de">{daten['beschreibung']}</desc>

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
