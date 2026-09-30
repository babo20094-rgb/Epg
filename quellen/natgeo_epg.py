"""Echte Programmdaten fuer "National Geographic" UND "National
Geographic Wild" (RS) von natgeotv.com - AUTOMATISCH fuer jeden
RS-Sender, dessen Name auf "NATIONAL GEO(GRAPHIC)" ODER die gaengige
Playlist-Abkuerzung "NGC" passt (mit oder ohne HD/FHD/VIP/RAW-
Zusaetzen); der Name-Zusatz "WILD" waehlt den eigenen Wild-Kanal-Slug
(beide Kanaele laufen auf derselben Website, nur unter verschiedenen
URLs). Kein eigenes Praefix noetig.

https://www.natgeotv.com/rs/tv-program/{natgeo,nationalgeographicwild}
liefert - anders als die meisten anderen hier angebundenen Quellen -
server-seitig bereits gerendertes HTML mit einem mehrtaegigen
Tagesplan (aktueller Tag + 3 Folgetage) in `<li class="acilia-
schedule-event" data-datetime-timestamp="..."
data-end-timestamp="...">`-Bloecken je Sendung (Unix-Timestamps in
Sekunden, direkt als UTC verwendbar - kein eigenes Zeitzonen-Handling
noetig). Titel steht im `<h3>`, eine kurze Episoden-/Staffel-Zeile im
`<h4>` und die volle Beschreibung im folgenden `<p>` (beide innerhalb
des versteckten "acilia-schedule-event-content"-Akkordeon-Panels).

Wird pro Slug nur EINMAL pro Lauf geladen und geparst (Modul-weiter
Cache je Slug, analog zu rtv_rs_epg.py/sportklub_epg.py).

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt Download, Parsen
oder Kanalsuche fehl, bekommt der betroffene Sender in generate_epg.py
einfach die normale, kategoriebasierte generische EPG-Generierung wie
jeder andere Sender - dieses Modul darf einen Lauf niemals zum Absturz
bringen.
"""

from datetime import datetime, timedelta, timezone

import re
import unicodedata

import requests
from quellen import _http
from bs4 import BeautifulSoup

BASIS_URL = "https://www.natgeotv.com/rs/tv-program/{slug}"

# Sendername-Praefix -> natgeotv.com-URL-Slug.
_SLUGS = {
    "natgeo": "natgeo",
    "wild": "nationalgeographicwild",
}

REQUEST_TIMEOUT_SEKUNDEN = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# "NGC" ist die gaengige Playlist-Abkuerzung fuer "National
# Geographic Channel" (z.B. "RS|NGC HD"/"RS|NGC WILD HD").
_NATGEO_WILD_PATTERN = re.compile(r"^(NATIONAL\s*GEO(GRAPHIC)?|NGC)\s*WILD\b", re.IGNORECASE)
_NATGEO_PATTERN = re.compile(r"^(NATIONAL\s*GEO(GRAPHIC)?|NGC)\b", re.IGNORECASE)

# Modul-weiter Cache je Slug: {slug: [programme...]}
_programme_cache = {}


def _vip_raw_hd_entfernen(name):
    """Entfernt die playlist-eigenen Deko-Marker "VIP"/"RAW"/"HD"/"FHD"
    (auch in hochgestellter Unicode-Schreibweise wie "ⱽᴵᴾ ᴿᴬᵂ" - NFKD
    zerlegt diese zu normalen Buchstaben)."""
    zerlegt = unicodedata.normalize("NFKD", name)
    zerlegt = "".join(z for z in zerlegt if not unicodedata.combining(z))
    return re.sub(r"\bVIP\b|\bRAW\b|\bF?HD\b", " ", zerlegt, flags=re.IGNORECASE).strip()


def natgeo_kanal_finden(kanalname):
    """Erkennt "National Geo(graphic)" bzw. "National Geo(graphic)
    Wild" (mit beliebigen Whitespace-/HD/FHD/VIP/RAW-Zusaetzen) und
    gibt den passenden Slug-Schluessel ("natgeo"/"wild") zurueck, sonst
    None. Einfacher Praefix-Vergleich (kein Fuzzy-Abgleich, kein
    Fehltreffer-Risiko) - "Wild" muss VOR dem allgemeinen Muster
    geprueft werden, sonst wuerde es faelschlich als "natgeo" erkannt."""
    name = _vip_raw_hd_entfernen(kanalname.strip())
    name = re.sub(r"\s+", " ", name)

    if _NATGEO_WILD_PATTERN.match(name):
        return "wild"
    if _NATGEO_PATTERN.match(name):
        return "natgeo"

    return None


def _text_bereinigen(tag):
    if tag is None:
        return ""
    return re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()


def _seite_laden(schluessel):
    """Laedt und parst (und cached) den mehrtaegigen Tagesplan fuer den
    gegebenen Slug-Schluessel ("natgeo"/"wild"). Liefert eine Liste von
    {"title", "beschreibung", "bild", "start", "stop"}-Dicts (UTC),
    oder [] bei jedem Fehler."""
    if schluessel in _programme_cache:
        return _programme_cache[schluessel]

    slug = _SLUGS.get(schluessel)
    if not slug:
        return []

    try:
        url = BASIS_URL.format(slug=slug)
        response = _http.mit_retry(requests.get, url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        programme = []
        for eintrag in soup.select("li.acilia-schedule-event"):
            start_ts = eintrag.get("data-datetime-timestamp")
            stop_ts = eintrag.get("data-end-timestamp")
            if not start_ts or not stop_ts:
                continue
            try:
                start = datetime.fromtimestamp(int(start_ts), tz=timezone.utc)
                stop = datetime.fromtimestamp(int(stop_ts), tz=timezone.utc)
            except (TypeError, ValueError):
                continue
            if stop <= start:
                continue

            titel = _text_bereinigen(eintrag.select_one("h3"))
            if not titel:
                continue

            untertitel = _text_bereinigen(eintrag.select_one(".acilia-schedule-event-content h4"))
            volltext = _text_bereinigen(eintrag.select_one(".acilia-schedule-event-content p"))

            teile = [t for t in (untertitel, volltext) if t]
            beschreibung = ": ".join(teile) if teile else titel

            programme.append({
                "title": titel,
                "beschreibung": beschreibung,
                "bild": None,
                "start": start,
                "stop": stop,
            })

        programme.sort(key=lambda p: p["start"])
        print(f"NatGeo-EPG ({slug}): {len(programme)} Sendungen geladen.")
        _programme_cache[schluessel] = programme
        return programme
    except Exception as e:
        print(f"NatGeo-EPG ({slug}): Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _programme_cache[schluessel] = []
        return []


def natgeo_hole_programme(schluessel, tage=2):
    """Liefert die bereits geladenen Programmdaten fuer die naechsten
    `tage` Tage ab heute (UTC). Leere Liste bei jedem Fehler."""
    if not schluessel:
        return []

    eintraege = _seite_laden(schluessel)
    if not eintraege:
        return []

    heute = datetime.now(timezone.utc).date()
    erlaubte_tage = {heute + timedelta(days=i) for i in range(tage)}

    return [
        p for p in eintraege
        if p["start"].date() in erlaubte_tage or p["stop"].date() in erlaubte_tage
    ]
