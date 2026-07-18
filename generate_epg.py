from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape
import requests

# ==========================================================
# Automatische Beschreibungen nach Kategorie
# ==========================================================

KATEGORIEN = {

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

    "NATUR": {
        "keywords": [
            "NATURE", "WILD", "ANIMAL", "SAFARI",
            "PLANET", "EARTH"
        ],

        "DE": "{sender} zeigt faszinierende Dokumentationen über Tiere, Natur und die Umwelt.",

        "EXYU": "{sender} prikazuje dokumentarne emisije o životinjama, prirodi i svijetu koji nas okružuje.",

        "EN": "{sender} features fascinating documentaries about wildlife, nature and the environment."
    },

    "DOKU": {
        "keywords": [
            "DISCOVERY", "NAT GEO", "NATIONAL",
            "HISTORY", "ANIMAL", "PLANET", "DOC"
        ],

        "DE": "{sender} zeigt Dokumentationen über Natur, Wissenschaft, Geschichte und spannende Entdeckungen.",

        "EXYU": "{sender} prikazuje dokumentarne emisije, prirodu, nauku, istoriju i zanimljivosti iz cijelog svijeta.",

        "EN": "{sender} features documentaries about nature, science, history and fascinating discoveries."
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
    worte = [wort.capitalize() for wort in name.split()]
    return " ".join(worte)


# ==========================================================
# XML starten (Teile werden gesammelt und am Ende gejoint,
# statt bei jedem Schritt einen neuen String zu bauen)
# ==========================================================

xml_teile = ['<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n']

sender_daten = []

# ==========================================================
# sender.txt lesen
#
# Format (bis zu 4 Spalten, alles nach Sender ist optional):
#
# Land|Sender
# Land|Sender|Beschreibung
# Land|Sender|Beschreibung|Logo-URL
#
# Wird kein Logo angegeben, wird KEIN <icon>-Tag erzeugt -
# der Player/die Playlist behält dann ihr eigenes Logo.
# ==========================================================

try:
    with open("sender.txt", "r", encoding="utf-8") as f:
        zeilen = f.readlines()
except FileNotFoundError:
    raise SystemExit("Fehler: sender.txt wurde nicht gefunden.")

for zeile in zeilen:

    zeile = zeile.strip()

    if not zeile or zeile.startswith("#"):
        continue

    teile = [x.strip() for x in zeile.split("|")]

    while len(teile) < 4:
        teile.append("")

    land = teile[0]
    sender = teile[1]
    beschreibung = teile[2]
    logo = teile[3]
    kanal = f"{land}|{sender}"

    # So wie er in der Playlist als tvg-name steht (z.B. "DE| RTL"),
    # unverändert übernommen - das ist entscheidend für die
    # automatische Sender-Zuordnung in TiviMate.
    playlist_name = f"{land}| {sender}"

    if beschreibung == "":
        beschreibung = standard_beschreibung(land, sender)

    sender_daten.append({
        "kanal": kanal,
        "sender": sender,
        "beschreibung": beschreibung,
        "logo": logo
    })

    xml_teile.append(
        f' <channel id="{escape(kanal)}"> <display-name>{escape(playlist_name)}</display-name> '
    )

    # Icon wird NUR erzeugt, wenn in sender.txt explizit ein Logo angegeben ist
    if logo:
        xml_teile.append(f' <icon src="{escape(logo)}"/>\n')

    xml_teile.append("</channel>\n")

# ==========================================================
# DYN PPV CHANNELS
# ==========================================================

dyn_logo = "https://www.dslweb.de/public/resources/images/anbieter/dyn/dyn-teaser.jpg"

for i in range(1, 21):
    kanal = f"DE| DYN PPV {i} HD"
    xml_teile.append(
        f' <channel id="{escape(kanal)}"> <display-name>DYN PPV {i} HD</display-name> <icon src="{dyn_logo}"/> </channel> '
    )

# ==========================================================
# STANDARD-EPG (4-Stunden-Blöcke für 7 Tage, als Platzhalter)
# ==========================================================

starttag = datetime.now(timezone.utc).replace(
    hour=0, minute=0, second=0, microsecond=0
)

for stunde in range(0, 24 * 7, 4):

    start = starttag + timedelta(hours=stunde)
    ende = start + timedelta(hours=4)

    start_str = start.strftime("%Y%m%d%H%M%S +0000")
    ende_str = ende.strftime("%Y%m%d%H%M%S +0000")

    for daten in sender_daten:
        beschr = escape(daten["beschreibung"])
        xml_teile.append(
            f' <programme start="{start_str}" stop="{ende_str}" channel="{escape(daten["kanal"])}">'
            f' <title lang="de">{escape(sender_anzeigename(daten["sender"]))}</title>'
            f' <sub-title lang="de">{beschr}</sub-title>'
            f' <desc lang="de">{beschr}</desc> </programme> '
        )

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

        if len(daten) == 0:
            print("Keine DYN Live-Events - Standardtext wird erstellt")
        else:
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

                kanal = f"DE| DYN PPV {kanal_nummer} HD"

                xml_teile.append(
                    f' <programme start="{startzeit}" stop="{endzeit}" channel="{escape(kanal)}">'
                    f' <title>{escape(titel)}</title> <desc>{escape(beschreibung)}</desc> </programme> '
                )

                kanal_nummer += 1
                if kanal_nummer > 20:
                    kanal_nummer = 1

except Exception as e:
    print("DYN Fehler:", e)

# ==========================================================
# DYN LEERZEITEN
# ==========================================================

jetzt = datetime.now(timezone.utc).replace(
    hour=0, minute=0, second=0, microsecond=0
)

for i in range(1, 21):
    kanal = f"DE| DYN PPV {i} HD"

    for stunde in range(24 * 3):
        start = jetzt + timedelta(hours=stunde)
        ende = start + timedelta(hours=1)

        start_str = start.strftime("%Y%m%d%H%M%S +0000")
        ende_str = ende.strftime("%Y%m%d%H%M%S +0000")

        xml_teile.append(
            f' <programme start="{start_str}" stop="{ende_str}" channel="{escape(kanal)}">'
            f' <title>Im Moment keine Live Events, bleib dran</title>'
            f' <desc>Im Moment keine Live Events, bleib dran.</desc> </programme> '
        )

# ==========================================================
# XML ABSCHLIESSEN
# ==========================================================

xml_teile.append("\n</tv>")

with open("Epg_365_Tage.xml", "w", encoding="utf-8") as f:
    f.write("".join(xml_teile))

print(f"EPG erfolgreich erstellt ({len(sender_daten)} Sender).")
