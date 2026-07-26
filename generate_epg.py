from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape
import re
import requests
import xml.etree.ElementTree as ET

# ==========================================================
# Automatische Beschreibungen nach Kategorie
# ==========================================================

KATEGORIEN = {

    "REALITY": {
        "label": {"DE": "Reality-TV", "EXYU": "Rijaliti", "EN": "Reality TV"},
        "keywords": [
            "REALITY", "BIG BROTHER", "TEMPTATION",
            "LOVE ISLAND", "PAROVI", "ZADRUGA",
            "FARMA", "SURVIVOR"
        ],
        "DE": [
            "{sender} zeigt Reality-TV, Alltagsdramen und packende Geschichten echter Menschen rund um die Uhr.",
            "{sender} begleitet echte Menschen in emotionalen Reality-Formaten und überraschenden Wendungen."
        ],
        "EXYU": [
            "{sender} prikazuje rijaliti sadržaj, svakodnevne drame i priče stvarnih ljudi tokom cijelog dana.",
            "{sender} donosi najgledanije rijaliti formate sa neočekivanim obrtima i pravim emocijama."
        ],
        "EN": [
            "{sender} features reality TV, everyday drama and gripping stories of real people around the clock.",
            "{sender} follows real people through emotional reality formats full of unexpected twists."
        ]
    },

    "NEWS": {
        "label": {"DE": "Nachrichten", "EXYU": "Vijesti", "EN": "News"},
        "keywords": [
            "NEWS", "CNN", "BBC", "SKY NEWS",
            "AL JAZEERA", "N24", "NTV", "WELT",
            "EURONEWS", "FRANCE 24", "BLOOMBERG",
            "DW", "CNBC", "FOX NEWS", "MSNBC",
            "RTRS", "RTS", "HRT", "BHT", "N1",
            "VIJESTI", "DNEVNIK"
        ],
        "DE": [
            "{sender} informiert rund um die Uhr über aktuelle Nachrichten, Politik, Wirtschaft und Ereignisse aus aller Welt.",
            "{sender} bringt aktuelle Berichterstattung, Hintergründe und Analysen zum Weltgeschehen."
        ],
        "EXYU": [
            "{sender} donosi najnovije vijesti, politiku, ekonomiju i aktuelna dešavanja iz cijelog svijeta.",
            "{sender} prati aktuelna zbivanja, politiku i društvo uz detaljne analize i izvještaje."
        ],
        "EN": [
            "{sender} delivers breaking news, politics, business updates and major events from around the world.",
            "{sender} provides in-depth coverage, analysis and the latest headlines from across the globe."
        ]
    },

    "KINDER": {
        "label": {"DE": "Kinder", "EXYU": "Dječiji program", "EN": "Kids"},
        "keywords": [
            "KIDS", "KID", "JR", "JUNIOR",
            "DISNEY", "CARTOON", "NICKELODEON",
            "NICK", "BOOMERANG", "BABY",
            "TOON", "CBEEBIES", "MINIMAX",
            "TINY", "POPCORN", "GULLI",
            "DJECA", "CRTANI"
        ],
        "DE": [
            "{sender} bietet Zeichentrick, Kinderfilme, Lernprogramme und familienfreundliche Unterhaltung für Groß und Klein.",
            "{sender} zeigt beliebte Kinderserien, Zeichentrick und pädagogisch wertvolle Sendungen den ganzen Tag."
        ],
        "EXYU": [
            "{sender} prikazuje crtane filmove, dječije emisije, edukativni sadržaj i zabavu za cijelu porodicu.",
            "{sender} donosi omiljene crtane serije i edukativni program za najmlađe tokom cijelog dana."
        ],
        "EN": [
            "{sender} features cartoons, children's shows, educational programs and family entertainment throughout the day.",
            "{sender} offers popular kids' series, animation and educational content all day long."
        ]
    },

    "GAMING": {
        "label": {"DE": "Gaming", "EXYU": "Gaming", "EN": "Gaming"},
        "keywords": [
            "GAMING", "ESPORTS", "E-SPORTS", "GAME",
            "IGRE", "TWITCH", "GAMER"
        ],
        "DE": [
            "{sender} zeigt Gaming-Inhalte, eSports-Turniere und spannende Let's-Plays rund um die Uhr.",
            "{sender} bringt die besten eSports-Events, Gaming-News und Highlights der Szene."
        ],
        "EXYU": [
            "{sender} prikazuje gaming sadržaj, eSports turnire i najzanimljivije igre uživo.",
            "{sender} donosi najbolje eSports događaje i vijesti iz svijeta video igara."
        ],
        "EN": [
            "{sender} features gaming content, eSports tournaments and exciting live gameplay around the clock.",
            "{sender} brings the best eSports events, gaming news and highlights from the scene."
        ]
    },

    "RADIO": {
        "label": {"DE": "Radio", "EXYU": "Radio", "EN": "Radio"},
        "keywords": [
            "RADIO", "HÖRFUNK", "FM"
        ],
        "DE": [
            "{sender} bietet Radioprogramm mit Musik, Nachrichten und Unterhaltung rund um die Uhr.",
            "{sender} begleitet Sie mit Musik, Talk und aktuellen Themen durch den Tag."
        ],
        "EXYU": [
            "{sender} donosi radijski program sa muzikom, vijestima i zabavom tokom cijelog dana.",
            "{sender} prati vas uz muziku, razgovore i aktuelne teme tokom cijelog dana."
        ],
        "EN": [
            "{sender} offers radio programming with music, news and entertainment around the clock.",
            "{sender} keeps you company with music, talk and current topics throughout the day."
        ]
    },

    "SHOPPING": {
        "label": {"DE": "Shopping", "EXYU": "Kupovina", "EN": "Shopping"},
        "keywords": [
            "SHOP", "SHOPPING", "QVC", "HSE", "KUPOVINA"
        ],
        "DE": [
            "{sender} präsentiert Produkte, Angebote und Shopping-Sendungen rund um die Uhr.",
            "{sender} zeigt aktuelle Angebote und Produktvorstellungen im Dauerprogramm."
        ],
        "EXYU": [
            "{sender} prikazuje proizvode, ponude i emisije o kupovini tokom cijelog dana.",
            "{sender} donosi aktuelne ponude i predstavljanje proizvoda tokom cijelog dana."
        ],
        "EN": [
            "{sender} showcases products, deals and shopping programs around the clock.",
            "{sender} features the latest offers and product presentations throughout the day."
        ]
    },

    "WISSEN": {
        "label": {"DE": "Wissen & Bildung", "EXYU": "Znanje i edukacija", "EN": "Science & Education"},
        "keywords": [
            "SCIENCE", "EDUCATION", "ZNANJE", "NAUKA",
            "BILDUNG", "LEARN", "DISCOVERY SCIENCE"
        ],
        "DE": [
            "{sender} zeigt Wissenssendungen, Bildungsformate und spannende Erkenntnisse aus Wissenschaft und Technik.",
            "{sender} bringt Bildung und Wissenschaft anschaulich näher, mit Experimenten und Erklärungen."
        ],
        "EXYU": [
            "{sender} prikazuje edukativne emisije i zanimljivosti iz svijeta nauke i tehnologije.",
            "{sender} donosi naučne teme i edukativni sadržaj na razumljiv i zanimljiv način."
        ],
        "EN": [
            "{sender} features educational programs and fascinating insights from science and technology.",
            "{sender} brings science and learning to life through experiments and clear explanations."
        ]
    },

    "NATUR": {
        "label": {"DE": "Natur", "EXYU": "Priroda", "EN": "Nature"},
        "keywords": [
            "NATURE", "WILD", "ANIMAL", "SAFARI",
            "PLANET", "EARTH", "PRIRODA", "ZIVOTINJE"
        ],
        "DE": [
            "{sender} zeigt faszinierende Dokumentationen über Tiere, Natur und die Umwelt.",
            "{sender} nimmt Sie mit in die Tierwelt und zeigt beeindruckende Naturschauspiele."
        ],
        "EXYU": [
            "{sender} prikazuje dokumentarne emisije o životinjama, prirodi i svijetu koji nas okružuje.",
            "{sender} vodi vas u svijet životinja i prikazuje čuda prirode iz cijelog svijeta."
        ],
        "EN": [
            "{sender} features fascinating documentaries about wildlife, nature and the environment.",
            "{sender} takes you into the animal kingdom and showcases breathtaking natural wonders."
        ]
    },

    "DOKU": {
        "label": {"DE": "Dokumentation", "EXYU": "Dokumentarni program", "EN": "Documentary"},
        "keywords": [
            "DISCOVERY", "NAT GEO", "NATIONAL",
            "HISTORY", "DOC", "DOKUMENTARNI"
        ],
        "DE": [
            "{sender} zeigt Dokumentationen über Natur, Wissenschaft, Geschichte und spannende Entdeckungen.",
            "{sender} präsentiert packende Dokus zu Geschichte, Kultur und aktuellen Themen."
        ],
        "EXYU": [
            "{sender} prikazuje dokumentarne emisije, prirodu, nauku, istoriju i zanimljivosti iz cijelog svijeta.",
            "{sender} donosi zanimljive dokumentarne priče o istoriji, kulturi i savremenim temama."
        ],
        "EN": [
            "{sender} features documentaries about nature, science, history and fascinating discoveries.",
            "{sender} presents gripping documentaries covering history, culture and current affairs."
        ]
    },

    "AUTO": {
        "label": {"DE": "Auto & Motor", "EXYU": "Auto i motor", "EN": "Auto & Motor"},
        "keywords": [
            "AUTO", "MOTOR", "MOTORVISION", "AUTOMOBIL", "GARAZA"
        ],
        "DE": [
            "{sender} zeigt alles rund um Autos, Motorsport und Fahrzeugtechnik.",
            "{sender} präsentiert Fahrzeugtests, Motorsport-Highlights und Neuheiten aus der Autowelt."
        ],
        "EXYU": [
            "{sender} prikazuje sve o automobilima, motosportu i tehnici vozila.",
            "{sender} donosi testove vozila, motosport i novosti iz svijeta automobila."
        ],
        "EN": [
            "{sender} covers everything about cars, motorsports and vehicle technology.",
            "{sender} features vehicle reviews, motorsport highlights and the latest automotive news."
        ]
    },

    "REISEN": {
        "label": {"DE": "Reisen", "EXYU": "Putovanja", "EN": "Travel"},
        "keywords": [
            "TRAVEL", "TOUR", "TOURISM", "VACATION",
            "EXPLORE", "PUTOVANJA"
        ],
        "DE": [
            "{sender} nimmt Sie mit auf spannende Reisen zu faszinierenden Orten, Kulturen und Urlaubszielen weltweit.",
            "{sender} zeigt Reiseziele, fremde Kulturen und Urlaubsinspirationen aus aller Welt."
        ],
        "EXYU": [
            "{sender} vodi vas na zanimljiva putovanja kroz različite zemlje, kulture i turističke destinacije širom svijeta.",
            "{sender} prikazuje putničke destinacije, kulture i inspiracije za odmor iz cijelog svijeta."
        ],
        "EN": [
            "{sender} takes you on exciting journeys to amazing destinations, cultures and travel experiences worldwide.",
            "{sender} showcases travel destinations, cultures and vacation inspiration from around the globe."
        ]
    },

    "KOCHEN": {
        "label": {"DE": "Kochen", "EXYU": "Kuhinja", "EN": "Food & Cooking"},
        "keywords": [
            "FOOD", "KITCHEN", "COOK", "CUISINE",
            "CHEF", "GUSTO", "KUHINJA", "RECEPTI"
        ],
        "DE": [
            "{sender} präsentiert Kochsendungen, Rezepte, kulinarische Inspirationen und Spezialitäten aus aller Welt.",
            "{sender} zeigt Kochshows, Zubereitungstipps und kulinarische Highlights rund um den Globus."
        ],
        "EXYU": [
            "{sender} prikazuje kulinarske emisije, recepte, savjete za kuhanje i specijalitete iz cijelog svijeta.",
            "{sender} donosi kulinarske emisije i recepte iz raznih kuhinja svijeta."
        ],
        "EN": [
            "{sender} offers cooking shows, recipes, culinary tips and delicious dishes from around the world.",
            "{sender} features cooking shows and recipe inspiration from cuisines across the globe."
        ]
    },

    "MUSIK": {
        "label": {"DE": "Musik", "EXYU": "Muzika", "EN": "Music"},
        "keywords": [
            "MUSIC", "MUSIK", "MTV", "VH1",
            "DELUXE", "CLUB", "HITS", "MEZZO",
            "TRACE", "4MUSIC", "CMC", "DM SAT",
            "FOLK", "BALKAN MUSIC", "NRJ", "KISS",
            "DANCE", "ROCK", "POP", "JAZZ", "MUZIKA"
        ],
        "DE": [
            "{sender} präsentiert Musikvideos, Live-Konzerte, Charts und die größten Hits aus verschiedenen Musikrichtungen.",
            "{sender} spielt die angesagtesten Hits, Konzerte und Musikvideos rund um die Uhr."
        ],
        "EXYU": [
            "{sender} prikazuje muzičke spotove, koncerte uživo, top liste i najveće hitove iz različitih žanrova.",
            "{sender} emituje najveće hitove, koncerte i muzičke spotove tokom cijelog dana."
        ],
        "EN": [
            "{sender} features music videos, live concerts, chart hits and the best songs from a variety of genres.",
            "{sender} plays the hottest hits, concerts and music videos around the clock."
        ]
    },

    "COMEDY": {
        "label": {"DE": "Comedy", "EXYU": "Komedija", "EN": "Comedy"},
        "keywords": [
            "COMEDY", "HUMOR", "FUNNY", "LAUGH", "KOMEDIJA"
        ],
        "DE": [
            "{sender} bietet Comedy, Humor, Sitcoms und beste Unterhaltung für gute Laune den ganzen Tag.",
            "{sender} sorgt mit Sitcoms und Comedy-Formaten für gute Laune rund um die Uhr."
        ],
        "EXYU": [
            "{sender} prikazuje humoristične emisije, sitkome i zabavni sadržaj koji će vas nasmijati tokom cijelog dana.",
            "{sender} donosi komedije i sitkome za dobro raspoloženje tokom cijelog dana."
        ],
        "EN": [
            "{sender} features comedy shows, sitcoms and entertaining programs guaranteed to make you laugh.",
            "{sender} brings sitcoms and comedy formats to keep you entertained around the clock."
        ]
    },

    "RELIGION": {
        "label": {"DE": "Religion", "EXYU": "Vjera", "EN": "Religion"},
        "keywords": [
            "EWTN", "KTV", "GOD", "ISLAM",
            "QURAN", "BIBLE", "CHURCH", "SVET", "VJERA"
        ],
        "DE": [
            "{sender} sendet religiöse Inhalte, Gottesdienste, Dokumentationen und inspirierende Programme.",
            "{sender} bringt geistliche Sendungen, Gottesdienste und inspirierende Beiträge."
        ],
        "EXYU": [
            "{sender} emituje vjerske emisije, bogosluženja, dokumentarne sadržaje i inspirativne programe.",
            "{sender} donosi duhovni sadržaj, bogosluženja i inspirativne emisije."
        ],
        "EN": [
            "{sender} broadcasts religious services, documentaries and inspirational programming.",
            "{sender} features spiritual content, church services and inspiring programs."
        ]
    },

    "SPORT": {
        "label": {"DE": "Sport", "EXYU": "Sport", "EN": "Sport"},
        "keywords": [
            "SPORT", "SPORTS", "ESPN", "EUROSPORT",
            "DAZN", "SKY SPORT", "ARENA", "NBA",
            "NFL", "NHL", "MLB", "TENNIS",
            "GOLF", "RACING", "FORMULA", "F1",
            "MOTOGP", "BOX", "FIGHT", "UFC"
        ],
        "DE": [
            "{sender} bietet Live-Sport, Fußball, Motorsport, Tennis und viele weitere Sportereignisse aus aller Welt.",
            "{sender} überträgt Live-Events, Highlights und die größten Sportmomente weltweit."
        ],
        "EXYU": [
            "{sender} donosi sportske prijenose uživo, fudbal, tenis, motosport i druge vrhunske sportske događaje.",
            "{sender} prenosi uživo najveće sportske događaje i highlighte iz cijelog svijeta."
        ],
        "EN": [
            "{sender} features live sports including football, tennis, motorsports and many major sporting events worldwide.",
            "{sender} broadcasts live events, highlights and the biggest sporting moments from around the world."
        ]
    },

    "SERIEN": {
        "label": {"DE": "Serien", "EXYU": "Serije", "EN": "Series"},
        "keywords": [
            "SERIES", "SERIJA", "SERIJE", "DRAMA", "SOAP"
        ],
        "DE": [
            "{sender} zeigt beliebte Serien, Dramen und fesselnde Geschichten in fortlaufenden Episoden.",
            "{sender} präsentiert Serienhits verschiedener Genres, von Drama bis Krimi."
        ],
        "EXYU": [
            "{sender} prikazuje popularne serije, drame i uzbudljive priče u nastavcima.",
            "{sender} donosi serijske hitove raznih žanrova, od drame do krimića."
        ],
        "EN": [
            "{sender} features popular series, dramas and gripping stories told across ongoing episodes.",
            "{sender} presents hit series across genres, from drama to crime."
        ]
    },

    "FILM": {
        "label": {"DE": "Filme", "EXYU": "Filmovi", "EN": "Movies"},
        "keywords": [
            "CINEMA", "FILM", "MOVIE", "HOLLYWOOD",
            "HBO", "CINEMAX", "SKY CINEMA",
            "WARNER", "PARAMOUNT", "UNIVERSAL",
            "SONY", "STAR", "AXN", "AMC",
            "SYFY", "TNT", "THRILLER", "FILMOVI"
        ],
        "DE": [
            "{sender} zeigt Spielfilme, Blockbuster, Filmklassiker und spannende Serien rund um die Uhr.",
            "{sender} präsentiert die größten Kinohits, Klassiker und Blockbuster aus Hollywood."
        ],
        "EXYU": [
            "{sender} prikazuje filmske hitove, klasike i popularne serije tokom cijelog dana.",
            "{sender} donosi najveće filmske hitove i klasike iz Hollywooda tokom cijelog dana."
        ],
        "EN": [
            "{sender} features blockbuster movies, classic films and popular TV series throughout the day.",
            "{sender} presents the biggest Hollywood blockbusters and film classics around the clock."
        ]
    },

    "LIFESTYLE": {
        "label": {"DE": "Lifestyle", "EXYU": "Lifestyle", "EN": "Lifestyle"},
        "keywords": [
            "LIFESTYLE", "STYLE", "FASHION", "HOME",
            "LIVING", "HGTV", "TLC", "BEAUTY",
            "DESIGN", "WOMAN", "LADY"
        ],
        "DE": [
            "{sender} zeigt Sendungen rund um Wohnen, Mode, Lifestyle, Schönheit und inspirierende Ideen für den Alltag.",
            "{sender} präsentiert Mode-, Wohn- und Beauty-Themen für ein inspirierendes Lebensgefühl."
        ],
        "EXYU": [
            "{sender} donosi emisije o modi, uređenju doma, ljepoti, životnom stilu i korisnim savjetima za svakodnevni život.",
            "{sender} prikazuje modu, uređenje doma i teme o ljepoti za inspirativan svakodnevni život."
        ],
        "EN": [
            "{sender} features programs about fashion, home improvement, beauty, lifestyle and everyday inspiration.",
            "{sender} presents fashion, home and beauty content for an inspiring everyday lifestyle."
        ]
    },

    "REGIONAL": {
        "label": {"DE": "Regional", "EXYU": "Regionalni program", "EN": "Regional"},
        "keywords": [
            "REGIONAL", "LOKAL", "LOKALNA"
        ],
        "DE": [
            "{sender} bietet regionale Berichterstattung, lokale Themen und Programme aus Ihrer Umgebung.",
            "{sender} zeigt lokale Nachrichten, Veranstaltungen und Geschichten aus der Region."
        ],
        "EXYU": [
            "{sender} donosi regionalne vijesti, lokalne teme i program iz vaše okoline.",
            "{sender} prikazuje lokalna dešavanja, priče i teme iz regije."
        ],
        "EN": [
            "{sender} offers regional coverage, local topics and programming from your area.",
            "{sender} features local news, events and stories from the region."
        ]
    },

    "UNTERHALTUNG": {
        "label": {"DE": "Unterhaltung", "EXYU": "Zabava", "EN": "Entertainment"},
        "keywords": [
            "RTL", "VOX", "SAT", "PRO7", "PRO SIEBEN",
            "KABEL", "NOVA", "PINK", "HAPPY",
            "HAYAT", "OBN", "FACE", "ATV",
            "KANAL", "TV", "FOX", "ABC",
            "CBS", "NBC", "SHOW", "PLUS",
            "PRIME", "ZABAVA"
        ],
        "DE": [
            "{sender} bietet ein abwechslungsreiches Programm mit Unterhaltung, Shows, Serien und beliebten TV-Formaten für die ganze Familie.",
            "{sender} präsentiert vielfältige Unterhaltung mit Shows und beliebten Formaten für die ganze Familie."
        ],
        "EXYU": [
            "{sender} donosi raznovrstan program sa zabavnim emisijama, serijama i popularnim TV formatima za cijelu porodicu.",
            "{sender} prikazuje raznovrstan zabavni program i popularne TV formate za cijelu porodicu."
        ],
        "EN": [
            "{sender} features a wide range of entertainment including TV shows, series and popular formats for the whole family.",
            "{sender} presents varied entertainment with shows and popular formats for the whole family."
        ]
    }
}

# Feste Prüfreihenfolge: spezifischere Kategorien zuerst, damit
# generische Keywords (z.B. "TV", "SHOW" in UNTERHALTUNG) nicht
# fälschlich vor eindeutigeren Treffern (z.B. "SCIENCE", "REALITY")
# gewinnen. UNTERHALTUNG steht bewusst ganz am Ende als breitester
# Auffang-Kategorie vor dem generischen Fallback-Text.
KATEGORIE_PRIORITAET = [
    "REALITY", "NEWS", "KINDER", "GAMING", "RADIO", "SHOPPING",
    "WISSEN", "NATUR", "DOKU", "AUTO", "REISEN", "KOCHEN",
    "MUSIK", "COMEDY", "RELIGION", "SPORT", "SERIEN", "FILM",
    "LIFESTYLE", "REGIONAL", "UNTERHALTUNG"
]

DE_STANDARD = [
    "Willkommen beim Programm von {sender}. Freuen Sie sich auf abwechslungsreiche Unterhaltung während des ganzen Tages.",
    "{sender} begleitet Sie mit einem vielseitigen Programm durch den Tag."
]

EXYU_STANDARD = [
    "Dobro došli u program {sender}. Očekuje vas raznovrstan sadržaj tokom cijelog dana.",
    "{sender} vas prati sa raznovrsnim programom tokom cijelog dana."
]

EN_STANDARD = [
    "Welcome to {sender}. Enjoy a wide variety of entertainment throughout the day.",
    "{sender} keeps you entertained with a varied program throughout the day."
]


# ==========================================================
# Automatische Beschreibung
# ==========================================================

EXYU_LAENDER = [
    "BA", "RS", "HR", "ME", "CG", "MNE", "MNG", "MO", "MK", "SI",
    "EXYU", "BS"
]

EN_LAENDER = [
    "US", "UK", "GB", "AU", "TUBI", "CITY", "GO", "PRIME", "JOYN", "WOW"
]


def standard_beschreibung(land, sender):
    """
    Ermittelt Sprache + passende Kategorie für einen Sender und gibt
    ein Tupel (beschreibungstext, kategorie_key) zurueck. kategorie_key
    ist None, wenn keine Kategorie erkannt wurde (generischer Fallback-
    Text) - in dem Fall wird spaeter kein <category>-Tag geschrieben.

    Die Auswahl zwischen den mehreren Text-Varianten pro Kategorie/
    Sprache erfolgt deterministisch ueber einen Hash aus dem Sender-
    namen (Summe der Zeichencodes), NICHT per Zufall. So bekommt
    derselbe Sender bei jedem taeglichen Lauf wieder dieselbe Variante -
    kein "Flackern" zwischen unterschiedlichen Texten von Tag zu Tag.
    """

    # Klammerzusätze im Land-Feld ignorieren, z.B. "US (ESPN+ 001)" -> "US"
    land_code = land.split("(")[0].strip().upper()

    if land_code == "DE":
        sprache = "DE"

    elif land_code in EXYU_LAENDER:
        sprache = "EXYU"

    elif land_code in EN_LAENDER:
        sprache = "EN"

    else:
        sprache = "EN"

    sender_upper = sender.upper()
    hash_wert = sum(ord(c) for c in sender)

    for kategorie_key in KATEGORIE_PRIORITAET:
        daten = KATEGORIEN[kategorie_key]

        for keyword in daten["keywords"]:

            if keyword in sender_upper:
                varianten = daten[sprache]
                nummer = hash_wert % len(varianten)
                text = varianten[nummer].format(sender=sender)
                return text, kategorie_key

    if sprache == "DE":
        texte = DE_STANDARD

    elif sprache == "EXYU":
        texte = EXYU_STANDARD

    else:
        texte = EN_STANDARD

    nummer = hash_wert % len(texte)

    return texte[nummer].format(sender=sender), None


def kategorie_label(kategorie_key, land):
    """Liefert den sprachlich passenden Anzeigenamen fuer das
    <category>-Tag, oder None, falls keine Kategorie erkannt wurde."""

    if not kategorie_key:
        return None

    land_code = land.split("(")[0].strip().upper()

    if land_code == "DE":
        sprache = "DE"
    elif land_code in EXYU_LAENDER:
        sprache = "EXYU"
    else:
        sprache = "EN"

    return KATEGORIEN[kategorie_key]["label"][sprache]


def sender_anzeigename(name):
    worte = [wort.capitalize() for wort in name.split()]
    return " ".join(worte)


def sprache_code(land):
    """Liefert den XMLTV-Sprachcode (fuer lang="..."-Attribute) passend
    zur selben Sprachlogik wie in standard_beschreibung/kategorie_label."""

    land_code = land.split("(")[0].strip().upper()

    if land_code == "DE":
        return "de"
    elif land_code in EXYU_LAENDER:
        return "hr"
    else:
        return "en"


# ==========================================================
# XML starten (Teile werden gesammelt und am Ende gejoint,
# statt bei jedem Schritt einen neuen String zu bauen)
# ==========================================================

xml_teile = ['<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n']

sender_daten = []

# ==========================================================
# Bekannte durchnummerierte Sender-Familien (für NAME:-Einträge in
# sender.txt UND für Logo-Overrides in logo_only.txt).
#
# Jede Familie besteht aus einem Kürzel (nur intern verwendet) und
# einem Regex, das den stabilen "Kurznamen" im vollen Playlist-Namen
# findet (z.B. "DYN PPV 3" oder "Flo Racing 12"). Neue Familien
# einfach hier ergänzen - die restliche Logik greift automatisch
# darauf zu.
# ==========================================================
KURZNAME_MUSTER = [
    ("DYN_PPV", re.compile(r"DYN\s*PPV\s*\d+", re.IGNORECASE)),
    # (?![\d/]) verhindert, dass Taglines wie "FloRacing 24/7" fälschlich
    # als Kanalnummer "24" erkannt werden - die echte Kanalnummer steht
    # bei Flo Racing oft erst weiter hinten im Namen (z.B.
    # "FloRacing 24/7 :Flo Racing 02" -> richtig: "Flo Racing 02").
    ("FLO_RACING", re.compile(r"FLO\s*RACING\s*\d+(?![\d/])", re.IGNORECASE)),
]

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

    # NAME:-Präfix: für Sender, deren echter Playlist-Name selbst
    # Pipe-Zeichen enthält (z.B. "- NO EVENT STREAMING - | 8K
    # EXCLUSIVE | DE: DYN PPV 1"). Normales Land|Sender|Beschreibung|
    # Logo-Format würde so einen Namen an den falschen Stellen
    # zerschneiden. Bei "NAME:" wird stattdessen nur am LETZTEN Pipe
    # der Zeile getrennt - alles davor ist der komplette, unveränderte
    # Kanalname (wird 1:1 als id/display-name verwendet, keine
    # Land|Sender-Rekonstruktion), alles danach das Logo.
    if zeile.upper().startswith("NAME:"):
        rest = zeile[5:]
        teile_name = rest.rsplit("|", 1)

        if len(teile_name) != 2:
            continue

        voller_name = teile_name[0].strip()
        logo = teile_name[1].strip()

        if not voller_name:
            continue

        # Für den Sendungstitel NICHT den kompletten Rohnamen
        # wiederverwenden - der ist fast identisch mit dem Kanalnamen
        # selbst (nur andere Groß-/Kleinschreibung). Viele Player
        # (u.a. TiviMate) interpretieren einen Sendungstitel, der
        # praktisch gleich dem Kanalnamen ist, als "keine echten
        # Daten" und zeigen dann trotz vorhandener <title>/<desc>
        # nur "Keine Information" an. Stattdessen wird der stabile
        # Kern des Namens (z.B. "DYN PPV 1" oder "Flo Racing 3")
        # herausgelöst, falls vorhanden - das unterscheidet sich klar
        # vom Kanalnamen.
        #
        # KURZNAME_MUSTER listet alle bekannten, durchnummerierten
        # Sender-Familien auf. Neue Familien (z.B. weitere PPV-/
        # Live-Anbieter) können hier einfach ergänzt werden, ohne die
        # restliche Logik anfassen zu müssen.
        muster_typ = None
        kurzname = voller_name

        for typ, muster in KURZNAME_MUSTER:
            treffer = muster.search(voller_name)
            if treffer:
                # Mehrfache Leerzeichen glätten (z.B. "Flo Racing  02"
                # -> "Flo Racing 02"), damit der Name in der Beschreibung
                # sauber aussieht.
                kurzname = re.sub(r"\s+", " ", treffer.group(0)).strip()
                muster_typ = typ
                break

        beschreibung, kategorie_key = standard_beschreibung("DE", kurzname)

        event_titel = None

        if muster_typ == "DYN_PPV":
            # DYN PPV 1-50 (diese NAME:-Einträge in sender.txt - NICHT
            # zu verwechseln mit den fest verdrahteten API-Kanälen
            # "DYN PPV 1-20" weiter unten, die unverändert bleiben):
            #
            # Der vordere Teil des Namens (vor dem ersten "|") ist bei
            # diesen Kanälen entweder ein Platzhalter wie
            # "- NO EVENT STREAMING -" (kein Live-Event gerade) oder,
            # sobald ein Event läuft, der tatsächliche Event-Name (z.B.
            # "FC Bayern - Real Madrid"), den der Anbieter dort einträgt.
            #
            # Enthält dieser Teil "NO EVENT" -> Kanal ist im Leerlauf,
            # es bleibt beim bisherigen Standardtext (beschreibung s.o.).
            # Enthält er das NICHT -> der Kanalname hat sich wegen eines
            # Events geändert; dieser Name wird übernommen und weiter
            # unten im EPG-Raster als Sendungstitel/-beschreibung
            # angezeigt statt des generischen Platzhaltertexts.
            event_teil = voller_name.split("|", 1)[0].strip()

            if event_teil and "no event" not in event_teil.lower():
                event_titel = event_teil

        elif muster_typ == "FLO_RACING":
            # Beobachtetes Namensschema bei Flo Racing 1-20 (aus
            # TiviMate-Screenshots bestätigt):
            #
            # Kein Event:   "Flo Racing 16 :"
            #               -> "Flo Racing NN" steht direkt am Anfang,
            #                  danach nur noch ein loser Doppelpunkt.
            # Event läuft:  "AMSOIL Championship Off Road @ Jul 25
            #               10:45 AM :Flo Racing 03"
            #               -> der echte Event-Name (inkl. Datum/Zeit)
            #                  steht VOR "Flo Racing NN", getrennt
            #                  durch " :".
            #
            # Beide Fälle lassen sich mit einer Regel erkennen: Der
            # Text VOR dem gefundenen "Flo Racing NN"-Treffer im
            # vollen Namen ist bei "kein Event" leer (weil "Flo Racing
            # NN" ganz am Anfang steht) und bei "Event läuft" der
            # eigentliche Event-Name. Ist er nach dem Bereinigen von
            # Rand-Satzzeichen (":", "|", "-") leer, bleibt es beim
            # Standardtext (wie bei DYN PPV ohne Event); ist er
            # nicht leer, wird er als Sendungstitel übernommen.
            event_teil = voller_name[:treffer.start()].strip(" :|-").strip()

            if event_teil:
                event_titel = event_teil

        aliase = [voller_name]
        if muster_typ and kurzname not in aliase:
            aliase.append(kurzname)

        sender_daten.append({
            "kanal": voller_name,
            "land": "DE",
            "sender": kurzname,
            "beschreibung": beschreibung,
            "logo": logo,
            "exakter_name": True,
            "aliase": aliase,
            "event_titel": event_titel,
            "event_faehig": bool(muster_typ),
            "kategorie": kategorie_key
        })
        continue

    teile = [x.strip() for x in zeile.split("|")]

    while len(teile) < 4:
        teile.append("")

    land = teile[0]
    sender = teile[1]
    beschreibung = teile[2]
    logo = teile[3]
    kanal = f"{land}|{sender}"

    auto_beschreibung, kategorie_key = standard_beschreibung(land, sender)

    if beschreibung == "":
        beschreibung = auto_beschreibung

    sender_daten.append({
        "kanal": kanal,
        "land": land,
        "sender": sender,
        "beschreibung": beschreibung,
        "logo": logo,
        "exakter_name": False,
        "kategorie": kategorie_key
    })

# ==========================================================
# logo_only.txt lesen (optional)
#
# Für Sender, bei denen NUR das Logo gesetzt/geändert werden
# soll - z.B. weil das eigentliche EPG (die Programme) von
# einer anderen Quelle kommt und nicht überschrieben werden soll.
#
# Zwei Zeilenformate werden unterstützt:
#
# 1) Normale Sender (Land + Sendername getrennt):
#    Land|Sender|Logo-URL
#    Land|Sender||Logo-URL   (gleiches Schema wie sender.txt)
#
# 2) Kanalnamen mit Pipe-Zeichen im Namen selbst (z.B. Namen wie
#    "- NO EVENT STREAMING - | 8K EXCLUSIVE | DE: DYN PPV 1"):
#    NAME:<kompletter Kanalname exakt wie in der Playlist>|Logo-URL
#    Hier wird NUR das letzte "|" in der Zeile als Trenner zur
#    Logo-URL verwendet - alles davor (nach "NAME:") ist der Name,
#    egal wie viele Pipes darin vorkommen.
#
#    Das gilt auch für Sender mit täglich wechselndem Namen (z.B.
#    Live-Event-Kanäle wie "(Victory+ 001) | VNL Men's Live Matches :
#    France vs Belgium"). Hier reicht der stabile Teil in Klammern:
#    NAME:(Victory+ 001)|Logo-URL
#    oder kurz (funktioniert automatisch, sobald nur ein "|" in der
#    Zeile vorkommt):
#    (Victory+ 001)|Logo-URL
#
#    Ablauf für dieses Format:
#    a) Zuerst wird per TEILSTRING-Suche (Groß-/Kleinschreibung egal)
#       geprüft, ob ein Sender aus sender.txt diesen Text enthält.
#       Bei Treffer(n) wird dort NUR das Logo überschrieben.
#    b) Kein Treffer? Dann wird ein eigenständiger <channel>-Block
#       angelegt - mit mehreren <display-name>-Varianten (mit und
#       ohne Klammern), damit der Player den Sender trotz wechselndem
#       vollen Namen per Teilstring zuordnen kann.
#
# - Steht der Sender bereits in sender.txt (Format 1), wird dort
#   nur das Logo überschrieben (kein zusätzlicher Eintrag).
# - Sonst wird nur ein <channel>-Block mit Icon angelegt - OHNE
#   <programme>-Platzhalter, damit das echte EPG dieser Quelle
#   erhalten bleibt.
# ==========================================================

kanal_index = {d["kanal"]: d for d in sender_daten}
logo_only_channels = []
gesehene_logo_only_kanaele = set()

# Logo-Overrides für die fest eingebauten DYN-PPV-Kanäle (1-20).
# Diese Kanäle existieren bereits als eigener <channel>-Block mit
# eigener id ("DE| DYN PPV {i} HD") und bekommen dort auch ihre
# Programme (Live-Events/Leerzeiten) zugewiesen. Ein Logo-Eintrag
# in logo_only.txt für einen DYN-PPV-Sender darf deshalb KEINEN
# eigenständigen neuen Channel erzeugen (sonst gehen die Programme
# an der falschen, neuen Channel-id vorbei) - stattdessen wird hier
# nur das Logo für die passende Nummer gemerkt.
dyn_ppv_logo_overrides = {}
DYN_PPV_MUSTER = re.compile(r"DYN\s*PPV\s*(\d+)", re.IGNORECASE)

# Hinweis: Für Flo Racing 1-20 braucht es hier KEINEN eigenen
# Override-Mechanismus wie bei DYN PPV, weil es (anders als bei DYN
# PPV) keinen separaten, fest verdrahteten <channel>-Block gibt -
# die Flo-Racing-Kanäle entstehen ausschließlich über die NAME:-
# Einträge in sender.txt (siehe KURZNAME_MUSTER weiter oben) und
# landen dadurch bereits ganz normal in sender_daten. Ein Logo-
# Eintrag in logo_only.txt für "Flo Racing N" wird deshalb schon
# vom bestehenden Teilstring-Treffer (Fall a) weiter unten erfasst.

try:
    with open("logo_only.txt", "r", encoding="utf-8") as f:
        logo_only_zeilen = f.readlines()
except FileNotFoundError:
    logo_only_zeilen = []

for zeile in logo_only_zeilen:

    zeile = zeile.strip()

    if not zeile or zeile.startswith("#"):
        continue

    ist_name_praefix = zeile.upper().startswith("NAME:")
    roh_teile = zeile.split("|")

    if ist_name_praefix or len(roh_teile) == 2:
        # Kompletter/kurzer Name + Logo-URL, getrennt durch das LETZTE
        # Pipe-Zeichen in der Zeile. "NAME:" Präfix ist optional - wird
        # automatisch erkannt, wenn die Zeile nur ein einziges Pipe hat
        # (z.B. "DE: DYN PPV 1|https://...") oder wenn "NAME:" davor steht
        # (für Namen, die selbst mehrere Pipes enthalten).
        rest = zeile[5:] if ist_name_praefix else zeile
        teile_name = rest.rsplit("|", 1)

        if len(teile_name) != 2:
            continue

        voller_name = teile_name[0].strip()
        logo = teile_name[1].strip()

        if not voller_name or not logo:
            continue

        # a) Teilstring-Treffer gegen bereits bekannte Sender aus
        # sender.txt suchen (z.B. wenn nur "(Victory+ 001)" angegeben
        # wird, der volle Sendername in sender.txt aber
        # "(Victory+ 001) | VNL Men's Live Matches : ..." lautet).
        suchtext = voller_name.lower()
        treffer = [
            d for d in sender_daten
            if suchtext in d["sender"].lower()
        ]

        if treffer:
            for d in treffer:
                d["logo"] = logo
            print(
                f"logo_only.txt: '{voller_name}' per Teilstring auf "
                f"{len(treffer)} Sender aus sender.txt angewendet."
            )
            continue

        # b) Kein Treffer in sender.txt: prüfen, ob es sich um einen
        # DYN-PPV-Sender handelt (z.B. "DE: DYN PPV 1"). Diese Kanäle
        # gibt es weiter unten bereits fest mit eigener Channel-id und
        # eigenen Programmen - hier deshalb NUR das Logo überschreiben,
        # statt einen zweiten, konkurrierenden Channel anzulegen.
        dyn_match = DYN_PPV_MUSTER.search(voller_name)
        if dyn_match:
            nummer = int(dyn_match.group(1))
            dyn_ppv_logo_overrides[nummer] = logo
            print(
                f"logo_only.txt: '{voller_name}' als DYN-PPV-Logo-Override "
                f"für Kanal {nummer} übernommen."
            )
            continue

        # Sonst: eigenständigen Channel anlegen. Klammerinhalt zusätzlich
        # als Alias ohne Klammern herauslösen, damit der Player mehr
        # Chancen zur Zuordnung per Teilstring hat.
        kanal = voller_name

        if kanal not in gesehene_logo_only_kanaele:
            aliase = [voller_name]

            klammer_match = re.search(r"\(([^)]+)\)", voller_name)
            if klammer_match:
                klammer_inhalt = klammer_match.group(1).strip()
                if klammer_inhalt and klammer_inhalt not in aliase:
                    aliase.append(klammer_inhalt)

            ohne_klammern = re.sub(r"[()]", "", voller_name).strip()
            if ohne_klammern and ohne_klammern not in aliase:
                aliase.append(ohne_klammern)

            logo_only_channels.append({
                "kanal": kanal,
                "voller_name": voller_name,
                "aliase": aliase,
                "logo": logo
            })
            gesehene_logo_only_kanaele.add(kanal)

        continue

    # Format 1: Land|Sender|Logo bzw. Land|Sender||Logo
    teile = [x.strip() for x in zeile.split("|")]

    # Gleiches Spaltenschema wie sender.txt: Land|Sender|Beschreibung|Logo
    # Die Beschreibung-Spalte wird hier ignoriert, das Logo ist immer
    # die letzte (4.) Spalte. Wird nur "Land|Sender|Logo" mit 3 Spalten
    # angegeben, ist das Logo dann Spalte 3.
    while len(teile) < 4:
        teile.append("")

    land = teile[0]
    sender = teile[1]
    logo = teile[3] if teile[3] else teile[2]

    if not logo:
        continue

    kanal = f"{land}|{sender}"

    if kanal in kanal_index:
        # Logo für bereits vorhandenen Sender überschreiben
        kanal_index[kanal]["logo"] = logo
    elif kanal not in gesehene_logo_only_kanaele:
        # Neuer, eigenständiger Channel NUR mit Icon, ohne Programme
        logo_only_channels.append({
            "kanal": kanal,
            "land": land,
            "sender": sender,
            "logo": logo
        })
        gesehene_logo_only_kanaele.add(kanal)

# ==========================================================
# <channel>-Blöcke schreiben (sender.txt, mit ggf.
# überschriebenem Logo aus logo_only.txt)
# ==========================================================

for daten in sender_daten:

    # So wie er in der Playlist als tvg-name steht (z.B. "DE| RTL"),
    # unverändert übernommen - das ist entscheidend für die
    # automatische Sender-Zuordnung in TiviMate.
    # Ausnahme: Einträge mit "exakter_name" (aus NAME:-Zeilen in
    # sender.txt) haben ihren kompletten, echten Playlist-Namen
    # bereits direkt in "kanal" stehen - hier NICHT aus Land+Sender
    # neu zusammenbauen, sonst geht der Name kaputt.
    if daten.get("exakter_name"):
        playlist_namen = daten.get("aliase") or [daten["kanal"]]
    else:
        playlist_namen = [f"{daten['land']}| {daten['sender']}"]

    xml_teile.append(f' <channel id="{escape(daten["kanal"])}">')

    for playlist_name in playlist_namen:
        xml_teile.append(f' <display-name>{escape(playlist_name)}</display-name>')

    # Icon wird NUR erzeugt, wenn ein Logo angegeben ist
    # (aus sender.txt oder als Override aus logo_only.txt)
    if daten["logo"]:
        xml_teile.append(f' <icon src="{escape(daten["logo"])}"/>')

    xml_teile.append(" </channel>\n")

# ==========================================================
# <channel>-Blöcke für reine Logo-Einträge (kein Sender in
# sender.txt) - nur Icon, keine Programme
# ==========================================================

for daten in logo_only_channels:
    if "voller_name" in daten:
        namen = daten.get("aliase") or [daten["voller_name"]]
    else:
        namen = [f"{daten['land']}| {daten['sender']}"]

    xml_teile.append(f' <channel id="{escape(daten["kanal"])}">')

    for name in namen:
        xml_teile.append(f' <display-name>{escape(name)}</display-name>')

    xml_teile.append(
        f' <icon src="{escape(daten["logo"])}"/> </channel>\n'
    )


# ==========================================================
# <programme>-Blöcke erzeugen
#
# Das EPG wird per GitHub Actions alle 2 Stunden neu erzeugt und
# deckt dabei immer nur ein Roll-Fenster von 4 Tagen AB JETZT ab
# (nicht 365 Tage - "Epg_365_Tage.xml" ist nur der historische
# Dateiname). Bei diesem kleinen Fenster ist 4-Std-Granularitaet
# fuer ALLE Sender unproblematisch (kein Groessenproblem).
#
# Bei "event_faehigen" Sendern (Flo Racing, DYN PPV - erkannt ueber
# KURZNAME_MUSTER) wird fuer die Bloecke von HEUTE der Live-Event-
# Titel (event_titel, direkt aus dem aktuellen Kanalnamen
# herausgeloest) als Sendungstitel verwendet, falls gerade ein
# Event laeuft - sonst der normale Standardtext. Da das Skript
# alle 2 Stunden neu laeuft, wird ein neu startendes Event so
# zeitnah im EPG sichtbar. Alle Bloecke ab morgen bekommen (weil
# der zukuenftige Kanalname-Zustand nicht bekannt ist) ebenfalls
# den Standardtext.
# ==========================================================

TAGE_ANZAHL = 4
BLOCK_STUNDEN = 4
BLOECKE_PRO_TAG = 24 // BLOCK_STUNDEN

jetzt = datetime.now(timezone.utc)

raster_start = jetzt.replace(
    hour=(jetzt.hour // BLOCK_STUNDEN) * BLOCK_STUNDEN,
    minute=0, second=0, microsecond=0
)
heute_ende = raster_start.replace(hour=0) + timedelta(days=1)


def xmltv_zeit(dt):
    return dt.strftime("%Y%m%d%H%M%S +0000")


def programme_schreiben(daten, start, ende, titel, sprache, beschreibung, kategorie_text):
    xml_teile.append(
        f' <programme start="{xmltv_zeit(start)}" '
        f'stop="{xmltv_zeit(ende)}" channel="{escape(daten["kanal"])}">'
    )
    xml_teile.append(f'<title lang="{sprache}">{escape(titel)}</title>')
    xml_teile.append(f'<desc lang="{sprache}">{escape(beschreibung)}</desc>')
    if kategorie_text:
        xml_teile.append(f'<category lang="{sprache}">{escape(kategorie_text)}</category>')
    xml_teile.append(" </programme>\n")


for daten in sender_daten:

    sprache = sprache_code(daten["land"])
    standard_titel = sender_anzeigename(daten["sender"])
    kategorie_text = kategorie_label(daten.get("kategorie"), daten["land"])
    beschreibung = daten["beschreibung"]
    event_titel = daten.get("event_titel") if daten.get("event_faehig") else None

    for block_index in range(TAGE_ANZAHL * BLOECKE_PRO_TAG):
        block_start = raster_start + timedelta(hours=BLOCK_STUNDEN * block_index)
        block_ende = block_start + timedelta(hours=BLOCK_STUNDEN)

        if event_titel and block_start < heute_ende:
            titel = event_titel
        else:
            titel = standard_titel

        programme_schreiben(daten, block_start, block_ende, titel, sprache, beschreibung, kategorie_text)


xml_teile.append("\n</tv>")

xml_inhalt = "".join(xml_teile)

# ==========================================================
# XML-Validitätsprüfung
#
# Bevor die Datei geschrieben (und später committet) wird, wird
# geprüft, ob das erzeugte XML überhaupt wohlgeformt ist. Bricht das
# Skript hier ab, bleibt die zuletzt funktionierende Epg_365_Tage.xml
# unangetastet erhalten, statt durch eine kaputte Datei ersetzt zu
# werden.
# ==========================================================

try:
    ET.fromstring(xml_inhalt)
except ET.ParseError as e:
    raise SystemExit(f"Fehler: Erzeugtes XML ist ungültig, Abbruch ohne Schreiben: {e}")

with open("Epg_365_Tage.xml", "w", encoding="utf-8") as f:
    f.write(xml_inhalt)

print(f"EPG erfolgreich erstellt ({len(sender_daten)} Sender).")
