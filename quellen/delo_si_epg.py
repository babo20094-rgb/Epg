"""Echte Programmdaten fuer Sport Klub SLOWENIEN von tvspored.delo.si.

WICHTIG (September 2026): Die bisherige Annahme, Sport Klub Kroatien
(sportklub_epg.py/epgshare01.online) und Sport Klub Slowenien zeigen
dasselbe Programm, war falsch - per Nutzer-Screenshot bestaetigt lief
auf dem echten slowenischen SK1 "Ingolstadt - Aachen" (3. Bundesliga),
waehrend die kroatischen Daten fuer "SK 1" zu diesem Zeitpunkt die
saudische Liga zeigten. tv-spored.siol.net (die normale automatische
SI-Quelle) fuehrt selbst keine echten Sport-Klub-Daten (die Kanalseiten
"sportkl"/"sportklubp" existieren dort zwar, haben aber keine eigene
Sendungsliste - nur ein "andere Kanaele"-Widget). tvspored.delo.si hat
dagegen eine echte, serverseitig gerenderte Sendungsliste (schema.org
"BroadcastEvent"-Microdata) fuer "SK 1" bis "SK 6" - direkt per
Websuche gefunden und live gegen "Ingolstadt - Aachen" verifiziert
(exakter Treffer).

Nur fuer Sport-Klub-Sender (Land SI) gedacht, opt-in ueber
generate_epg.py's SI-Verarbeitungsschleife - kein eigenes sender.txt-
Praefix noetig, genau wie beim bisherigen sportklub_epg.py-Fallback,
den dieses Modul fuer SI-Sender ersetzt.

Die Seite liefert keine mehrtaegige Datumsnavigation ohne JavaScript
(der Datums-/Uhrzeit-Dropdown im HTML aendert die serverseitige Antwort
nicht) - ein einzelner Abruf der Standardseite deckt aber bereits ca.
24-30 Stunden ab (von "gestern spaet abends" bis "morgen frueh"), das
reicht fuer die aktuelle Sendung/die naechsten Stunden voellig aus
(Tage 3+ sind ohnehin immer generisch, wie bei allen anderen echten
Quellen in diesem Repo).

Degradiert an JEDER Stelle graceful auf None/[] statt zu werfen -
schlaegt Kanalsuche oder Seitenabruf fehl, bekommt der betroffene Sender
in generate_epg.py einfach die normale, kategoriebasierte generische
EPG-Generierung. Dieses Modul darf einen Lauf niemals zum Absturz
bringen.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import re
import unicodedata

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://tvspored.delo.si"

REQUEST_TIMEOUT_SEKUNDEN = 20

LJUBLJANA_TZ = ZoneInfo("Europe/Ljubljana")

_ZEIT_PATTERN = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*$")

# Feste Slug-Zuordnung - delo.si fuehrt aktuell "SK 1" bis "SK 6" unter
# genau diesen Slugs (per /programi-Kanalliste bestaetigt).
_SK_SLUGS = {1: "sk1", 2: "sk2", 3: "sk3", 4: "sk4", 5: "sk5", 6: "sk6"}

_SK_NUMMER_PATTERN = re.compile(r"^(?:SPORT\s*KLUB|SK)\s*0*(\d{1,2})$", re.IGNORECASE)

# Modul-weiter Cache pro Slug, analog zu arena_epg.py.
_programm_cache = {}


def delo_si_kanal_finden(kanalname):
    """Erkennt "SK N"/"Sport Klub N" (N = 1-6, optional HD/FHD/UHD/SD
    und/oder die Playlist-Deko-Marker "VIP"/"RAW"/hochgestelltes
    Unicode "ⱽᴵᴾ ᴿᴬᵂ") und gibt den passenden delo.si-Slug zurueck,
    sonst None. Bewusst kein unscharfer Abgleich - die Namenskonvention
    ist hier immer eindeutig nummeriert."""
    if not kanalname:
        return None

    ascii_name = "".join(
        z for z in unicodedata.normalize("NFKD", kanalname.strip())
        if not unicodedata.combining(z)
    )
    ascii_name = re.sub(r"\b(HD|FHD|UHD|SD|VIP|RAW)\b", " ", ascii_name, flags=re.IGNORECASE)
    ascii_name = re.sub(r"\s+", " ", ascii_name).strip()

    treffer = _SK_NUMMER_PATTERN.match(ascii_name)
    if not treffer:
        return None

    nummer = int(treffer.group(1))
    return _SK_SLUGS.get(nummer)


def _seite_holen(slug):
    """Holt (und cached) die rohe Sendungsliste fuer einen Slug als
    Liste von (start_text, titel)-Tupeln. Leere Liste bei jedem Fehler
    (Netzwerk, HTTP-Status, unerwartete Seitenstruktur)."""
    if slug in _programm_cache:
        return _programm_cache[slug]

    url = f"{BASE_URL}/oddaje/{slug}/vsi/vsi/"

    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT_SEKUNDEN,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        events = soup.find_all(attrs={"itemtype": "https://schema.org/BroadcastEvent"})

        rohe_sendungen = []
        for event in events:
            start_el = event.find(attrs={"itemprop": "startDate"})
            name_el = event.find(attrs={"itemprop": "name"})
            if start_el is None or name_el is None:
                continue
            start_text = start_el.get_text(strip=True)
            titel = name_el.get_text(strip=True)
            if not start_text or not titel:
                continue
            rohe_sendungen.append((start_text, titel))

        if not rohe_sendungen:
            print(f"Delo.si-EPG: Sendungsliste ({slug}) leer/unerwartete Struktur, ueberspringe.")

        _programm_cache[slug] = rohe_sendungen
        return rohe_sendungen
    except Exception as e:
        print(f"Delo.si-EPG: Seitenabruf ({slug}) fehlgeschlagen ({e}), ueberspringe.")
        _programm_cache[slug] = []
        return []


def delo_si_hole_programme(slug):
    """Holt Programmdaten fuer den gegebenen delo.si-Slug. Liefert eine
    nach Startzeit sortierte Liste von {"title", "beschreibung", "bild",
    "start", "stop"} - leere Liste bei jedem Fehler. Die Seite liefert
    keine Endzeiten - die Endzeit einer Sendung wird aus der Startzeit
    der naechsten Sendung berechnet (letzte Sendung endet mit der
    letzten bekannten Startzeit + 2h als grobe Schaetzung, analog zu
    arena_epg.py/klix_epg.py). Der Tageswechsel wird daran erkannt, dass
    eine Startzeit kleiner ist als die vorherige (die Liste beginnt oft
    noch am spaeten Vortag)."""
    if not slug:
        return []

    rohe_sendungen = _seite_holen(slug)
    if not rohe_sendungen:
        return []

    heute = datetime.now(LJUBLJANA_TZ).replace(hour=0, minute=0, second=0, microsecond=0)

    # Die Liste beginnt oft noch am spaeten VORTAG (z.B. "23:15", dann
    # erst "01:15" am eigentlichen "heute") - ein einzelner Zeitsprung
    # nach unten direkt am Anfang der Liste bedeutet deshalb "Vortag",
    # nicht "naechster Tag". Peekt die ersten beiden Zeiten, um den
    # Start-Tagesversatz zu bestimmen, statt bei 0 zu beginnen.
    erste_minuten = None
    zweite_minuten = None
    for start_text, _titel in rohe_sendungen[:2]:
        treffer = _ZEIT_PATTERN.match(start_text)
        if not treffer:
            continue
        minuten = int(treffer.group(1)) * 60 + int(treffer.group(2))
        if erste_minuten is None:
            erste_minuten = minuten
        else:
            zweite_minuten = minuten

    tag_versatz = -1 if (erste_minuten is not None and zweite_minuten is not None and erste_minuten > zweite_minuten) else 0

    geparste = []
    vorherige_minuten = None

    for start_text, titel in rohe_sendungen:
        treffer = _ZEIT_PATTERN.match(start_text)
        if not treffer:
            continue
        stunde, minute = int(treffer.group(1)), int(treffer.group(2))
        if stunde > 23 or minute > 59:
            continue

        minuten_seit_mitternacht = stunde * 60 + minute
        if vorherige_minuten is not None and minuten_seit_mitternacht < vorherige_minuten:
            tag_versatz += 1
        vorherige_minuten = minuten_seit_mitternacht

        try:
            start = (heute + timedelta(days=tag_versatz)).replace(hour=stunde, minute=minute)
        except Exception:
            continue

        geparste.append({"title": titel, "start": start})

    geparste.sort(key=lambda s: s["start"])

    alle_sendungen = []
    for index, sendung in enumerate(geparste):
        if index + 1 < len(geparste):
            stop = geparste[index + 1]["start"]
        else:
            stop = sendung["start"] + timedelta(hours=2)

        alle_sendungen.append({
            "title": sendung["title"],
            "beschreibung": "",
            "bild": None,
            "start": sendung["start"].astimezone(ZoneInfo("UTC")),
            "stop": stop.astimezone(ZoneInfo("UTC")),
        })

    return alle_sendungen
