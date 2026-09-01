"""Optionale, echte Programmdaten von den (HTML-gescrapten) Arena-Sport-
EPG-Seiten tvarenasport.hr (Kroatisch, Timezone Europe/Budapest) und
tvarenasport.com (Serbisch, Timezone Europe/Belgrade).

Genau wie sky_epg.py ist diese Quelle AUSSCHLIESSLICH opt-in ueber das
neue "ARENA:"-Praefix in sender.txt - es gibt hier KEIN automatisches
Matching gegen irgendwelche bestehenden sender.txt-Zeilen. Das Land-Feld
(HR oder RS) entscheidet, welche der beiden Seiten gescrapt wird.

Portiert aus den config.js-Site-Plugins "tvarenasport.hr" und
"tvarenasport.com" des iptv-org/epg-Projekts, aber mit requests +
BeautifulSoup statt axios/cheerio und stdlib datetime/zoneinfo statt
dayjs.

Im Unterschied zu Sky/Telemach/mtel.ba liefert eine einzelne Anfrage der
jeweiligen Seite bereits ALLE Kanaele und alle verfuegbaren Tage auf
einmal (kein Login, keine separaten Requests pro Kanal/Tag) - die rohe,
geparste Seite wird deshalb zusaetzlich pro Land gecached, damit mehrere
ARENA:-Sender im selben Lauf nicht wiederholt dieselbe Seite abrufen und
parsen.

Da hier HTML-Struktur statt einer stabilen JSON-API gescrapt wird, ist
dieses Modul prinzipbedingt anfaelliger fuer Breaking Changes bei einem
Website-Redesign als die anderen Quellen - degradiert aber nach demselben
Zero-Risk-Prinzip an JEDER Stelle graceful auf None/[]/leere Ergebnisse
statt zu werfen: schlaegt Kanalsuche oder Programmabruf fehl, bekommt der
betroffene Sender in generate_epg.py einfach die normale, kategorie-
basierte generische EPG-Generierung wie jeder andere Sender - dieses
Modul darf einen Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta

import difflib
import re

import requests
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

from epg_lib import normalisiere_sendername

HR_URL = "https://tvarenaprogram.com/live/v2/hr"
RS_URL = "https://www.tvarenasport.com/tv-scheme"

REQUEST_TIMEOUT_SEKUNDEN = 20

_LAND_PARAMETER = {
    "HR": {"url": HR_URL, "tz": ZoneInfo("Europe/Budapest")},
    "RS": {"url": RS_URL, "tz": ZoneInfo("Europe/Belgrade")},
}

# Modul-weite Caches: Kanalliste und die rohe geparste Seite werden pro
# Land nur einmal pro Lauf geholt, auch wenn mehrere ARENA:-Sender in
# sender.txt stehen.
_kanalliste_cache = {}
_seite_cache = {}


def _land_normalisieren(land):
    land = (land or "HR").strip().upper()
    return land if land in _LAND_PARAMETER else "HR"


def _seite_holen(land):
    """Holt (und cached pro Land) die rohe HTML-Seite als BeautifulSoup-
    Objekt. Gibt bei jedem Fehler None zurueck."""
    land = _land_normalisieren(land)

    if land in _seite_cache:
        return _seite_cache[land]

    parameter = _LAND_PARAMETER[land]

    try:
        response = requests.get(
            parameter["url"], timeout=REQUEST_TIMEOUT_SEKUNDEN
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        _seite_cache[land] = soup
        return soup
    except Exception as e:
        print(f"Arena-EPG: Seitenabruf ({land}) fehlgeschlagen ({e}), ueberspringe.")
        _seite_cache[land] = None
        return None


def _hr_id_zu_name(kanal_id):
    if kanal_id.isdigit():
        return f"Arena Sport {int(kanal_id)}"
    if kanal_id[:1].isdigit():
        return f"Arena Sport {kanal_id}"
    match = re.match(r"^a(\d+)(p)?", kanal_id)
    if match:
        name = f"Arena {int(match.group(1))}"
        if match.group(2) == "p":
            name += " Premium"
        return name
    return f"Arena {kanal_id}"


def _rs_id_zu_name(kanal_id):
    if kanal_id.isdigit():
        return f"Arena Sport {int(kanal_id)} Serbia"
    match = re.match(r"^a+(\d+)p$", kanal_id)
    if match:
        return f"Arena Sport {int(match.group(1))} Premium Serbia"
    formatiert = kanal_id
    if formatiert.startswith("a-"):
        formatiert = formatiert[2:]
    if formatiert:
        formatiert = formatiert[0].upper() + formatiert[1:]
    return f"Arena Sport {formatiert} Serbia"


def arena_hole_kanalliste(land="HR"):
    """Holt (und cached pro Land) die komplette Arena-Sport-Kanalliste
    als Liste von {"site_id":..., "name":...}. Leere Liste bei jedem
    Fehler (Netzwerk, HTTP-Status, kein Treffer im HTML)."""
    land = _land_normalisieren(land)

    if land in _kanalliste_cache:
        return _kanalliste_cache[land]

    soup = _seite_holen(land)
    if soup is None:
        _kanalliste_cache[land] = []
        return []

    try:
        kanaele = []
        gesehene_ids = set()

        for img in soup.select(".tv-scheme-chanel-header img"):
            src = img.get("src") or ""
            match = re.search(r"chanel-([a-z0-9]+)\.png", src, re.IGNORECASE)
            if not match:
                continue
            kanal_id = match.group(1)
            if kanal_id in gesehene_ids:
                continue
            gesehene_ids.add(kanal_id)

            if land == "HR":
                name = _hr_id_zu_name(kanal_id)
            else:
                name = _rs_id_zu_name(kanal_id)

            kanaele.append({"site_id": kanal_id, "name": name})

        _kanalliste_cache[land] = kanaele
        return kanaele
    except Exception as e:
        print(f"Arena-EPG: Kanalliste ({land}) fehlgeschlagen ({e}), ueberspringe.")
        _kanalliste_cache[land] = []
        return []


def arena_kanal_finden(kanalname, land="HR"):
    """Sucht den Arena-Sport-Kanal, der am besten zu kanalname passt -
    erst exakter Abgleich nach normalisiere_sendername(), sonst
    unscharfer difflib-Abgleich (gleiche Vorgehensweise wie
    sky_kanal_finden()/telemach_kanal_finden()). Gibt die site_id zurueck
    oder None."""
    kanaele = arena_hole_kanalliste(land)
    if not kanaele:
        return None

    ziel_schluessel = normalisiere_sendername(kanalname)
    if not ziel_schluessel:
        return None

    name_index = {}
    for kanal in kanaele:
        schluessel = normalisiere_sendername(kanal["name"])
        if schluessel:
            name_index.setdefault(schluessel, kanal["site_id"])

    if ziel_schluessel in name_index:
        return name_index[ziel_schluessel]

    aehnliche = difflib.get_close_matches(ziel_schluessel, name_index.keys(), n=1, cutoff=0.72)
    if aehnliche:
        return name_index[aehnliche[0]]

    return None


def _tag_span_parsen(tag_element, tz):
    """Parst ein '.tv-scheme-days' <a>-Element: 3. Kind-<span> enthaelt
    Text im Format 'DD.MM.' - das aktuelle Jahr wird angehaengt. Gibt ein
    date-Objekt zurueck oder None bei Parse-Fehler."""
    try:
        spans = tag_element.find_all("span")
        if len(spans) < 3:
            return None
        text = spans[2].get_text(strip=True)
        match = re.match(r"^(\d{1,2})\.(\d{1,2})\.$", text)
        if not match:
            return None
        tag, monat = int(match.group(1)), int(match.group(2))
        jahr = datetime.now(tz).year
        return datetime(jahr, monat, tag, tzinfo=tz).date()
    except Exception:
        return None


def _zeit_kombinieren(datum, zeit_text, tz):
    """Kombiniert ein date-Objekt mit 'HH:mm'-Text zu einem tz-aware
    datetime. Gibt None bei Parse-Fehler zurueck."""
    try:
        match = re.match(r"^(\d{1,2}):(\d{2})$", zeit_text.strip())
        if not match:
            return None
        stunde, minute = int(match.group(1)), int(match.group(2))
        return datetime(
            datum.year, datum.month, datum.day, stunde, minute, tzinfo=tz
        )
    except Exception:
        return None


def _hr_kanalblock_finden(soup, site_id):
    """Findet fuer die HR-Seite das Kanal-Header-<img> mit passender
    site_id, geht zum umschliessenden Kanal-Container-<div> hoch (Eltern-
    Element des Headers) und gibt es zurueck, oder None."""
    for img in soup.select(".tv-scheme-chanel-header img"):
        src = img.get("src") or ""
        if f"chanel-{site_id}.png" not in src:
            continue
        header = img.find_parent(class_="tv-scheme-chanel-header")
        if header is None:
            continue
        return header.parent
    return None


def _hr_programme_parsen(soup, site_id, tz, tage):
    block = _hr_kanalblock_finden(soup, site_id)
    if block is None:
        return []

    tag_links = block.select(".tv-scheme-days a")
    tage_daten = [_tag_span_parsen(a, tz) for a in tag_links]

    slider_items = block.select(".tv-scheme-new-slider-wrapper .tv-scheme-new-slider-item")

    alle_roh = []
    for index, item in enumerate(slider_items):
        if index >= len(tage_daten) or tage_daten[index] is None:
            continue
        datum = tage_daten[index]

        for content in item.select(".slider-content"):
            zeit_span = content.select_one(".slider-content-top span")
            kategorie_span = content.select_one(".slider-content-middle span")
            titel_p = content.select_one(".slider-content-bottom p")
            beschr_span = content.select_one(".slider-content-bottom span")

            if zeit_span is None:
                continue
            start = _zeit_kombinieren(datum, zeit_span.get_text(strip=True), tz)
            if start is None:
                continue

            titel_roh = titel_p.get_text(strip=True) if titel_p else ""
            beschr_roh = beschr_span.get_text(strip=True) if beschr_span else ""

            # KEIN Tausch (fruehere Version tauschte Titel/Beschreibung,
            # wodurch bei Sport-Events der lange, generische Liga-Infotext
            # aus beschr_span als <title> im EPG-Raster erschien statt des
            # kurzen Spielnamens aus titel_p - siehe CLAUDE.md). Der kurze
            # Text (Team/Spielname) bleibt Titel, der laengere Fliesstext
            # wird zur Beschreibung (dort greift die Kuerzung auf den
            # ersten Satz in generate_epg.py's kuerze_beschreibung()).
            titel = titel_roh
            beschreibung = beschr_roh

            if not titel:
                continue

            alle_roh.append({"title": titel, "beschreibung": beschreibung, "start": start})

    alle_roh.sort(key=lambda s: s["start"])

    ergebnis = []
    for index, sendung in enumerate(alle_roh):
        if index + 1 < len(alle_roh):
            stop = alle_roh[index + 1]["start"]
        else:
            tag_start = sendung["start"].replace(hour=0, minute=0, second=0, microsecond=0)
            stop = tag_start + timedelta(days=1)
        ergebnis.append({
            "title": sendung["title"],
            "beschreibung": sendung["beschreibung"],
            "start": sendung["start"],
            "stop": stop,
        })

    erlaubte_tage = set()
    heute = datetime.now(tz).date()
    for i in range(tage):
        erlaubte_tage.add(heute + timedelta(days=i))

    return [
        p for p in ergebnis
        if p["start"].date() in erlaubte_tage or p["stop"].date() in erlaubte_tage
    ]


def _rs_kanalblock_finden(soup, site_id):
    for block in soup.select(".tv-scheme-chanel"):
        img = block.select_one(".tv-scheme-chanel-header img")
        if img is None:
            continue
        src = img.get("src") or ""
        match = re.search(r"chanel-([\w-]+?)\.png", src)
        if not match or match.group(1) != site_id:
            continue
        return block
    return None


def _rs_programme_parsen(soup, site_id, tz, tage):
    block = _rs_kanalblock_finden(soup, site_id)
    if block is None:
        return []

    tag_links = block.select(".tv-scheme-days a")
    tage_daten = [_tag_span_parsen(a, tz) for a in tag_links]

    slider_items = block.select(".tv-scheme-new-slider-item")

    heute = datetime.now(tz).date()
    ziel_tage = [heute + timedelta(days=i) for i in range(tage)]

    ergebnis = []
    for ziel_datum in ziel_tage:
        if ziel_datum not in tage_daten:
            continue
        index = tage_daten.index(ziel_datum)
        if index >= len(slider_items):
            continue
        item = slider_items[index]

        tages_sendungen = []
        for content in item.select(".slider-content"):
            zeit_span = content.select_one(".slider-content-top span")
            titel_p = content.select_one(".slider-content-bottom p")

            if zeit_span is None:
                continue
            start = _zeit_kombinieren(ziel_datum, zeit_span.get_text(strip=True), tz)
            if start is None:
                continue

            titel_text = titel_p.get_text(strip=True) if titel_p else ""

            league = ""
            is_live = False
            blob = content.select_one(".blob-text")
            if blob is not None:
                is_live = blob.get_text(strip=True).lower() == "uzivo" or blob.get_text(strip=True).lower() == "uživo"

            ausgeschlossene_klassen = {"live-title", "blob-text", "blob-border", "blob"}
            for span in content.select(".slider-content-bottom span"):
                klassen = set(span.get("class") or [])
                if klassen & ausgeschlossene_klassen:
                    continue
                league = span.get_text(strip=True)
                break

            if not titel_text and not league:
                continue

            titel = (league + ": " + titel_text) if league else titel_text
            if is_live:
                titel = "(Uživo) " + titel

            tages_sendungen.append({"title": titel, "start": start})

        tages_sendungen.sort(key=lambda s: s["start"])

        for index2, sendung in enumerate(tages_sendungen):
            if index2 + 1 < len(tages_sendungen):
                stop = tages_sendungen[index2 + 1]["start"]
            else:
                stop = datetime(
                    ziel_datum.year, ziel_datum.month, ziel_datum.day,
                    23, 59, tzinfo=tz,
                )
            ergebnis.append({
                "title": sendung["title"],
                "beschreibung": "",
                "start": sendung["start"],
                "stop": stop,
            })

    return ergebnis


def arena_hole_programme(site_id, land="HR", tage=2):
    """Holt Programmdaten fuer den gegebenen Arena-Sport-Kanal (site_id)
    fuer bis zu `tage` Tage (begrenzt durch die auf der Seite tatsaechlich
    verfuegbaren Tage-Tabs). Liefert eine nach Startzeit sortierte Liste
    von {"title", "beschreibung", "start", "stop"} (UTC, tz-aware) - leere
    Liste bei jedem Fehler (Netzwerk, HTTP-Status, unerwartete HTML-
    Struktur)."""
    if site_id is None:
        return []

    land = _land_normalisieren(land)
    tz = _LAND_PARAMETER[land]["tz"]

    soup = _seite_holen(land)
    if soup is None:
        return []

    try:
        if land == "HR":
            roh = _hr_programme_parsen(soup, site_id, tz, tage)
        else:
            roh = _rs_programme_parsen(soup, site_id, tz, tage)
    except Exception as e:
        print(f"Arena-EPG: Programmabruf fuer Kanal {site_id} ({land}) fehlgeschlagen ({e}), ueberspringe.")
        return []

    ergebnis = []
    for p in roh:
        try:
            ergebnis.append({
                "title": p["title"],
                "beschreibung": p.get("beschreibung") or "",
                "start": p["start"].astimezone(ZoneInfo("UTC")),
                "stop": p["stop"].astimezone(ZoneInfo("UTC")),
            })
        except Exception:
            continue

    ergebnis.sort(key=lambda s: s["start"])
    return ergebnis
