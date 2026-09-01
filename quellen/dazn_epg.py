"""Optionale, echte Programmdaten von der DAZN-EPG-API (rail-router).

Genau wie sky_epg.py/magenta_epg.py/arena_epg.py ist diese Quelle
AUSSCHLIESSLICH opt-in ueber das neue "DAZN:"-Praefix in sender.txt - es
gibt hier bewusst KEIN automatisches Matching gegen bestehende
sender.txt-Zeilen (zu viele DE-Zeilen, zu viele API-Aufrufe pro Lauf, zu
hohes Fehltreffer-Risiko).

Portiert aus dem config.js-Site-Plugin "dazn.com" des iptv-org/epg-
Projekts, aber deutlich im Umfang reduziert: nur die Variante mit einem
EXPLIZIT vom Nutzer angegebenen Laendercode wird unterstuetzt, nicht die
"alle Laender aggregiert"-Variante des Originals - wir fragen immer genau
das eine Land ab, das die jeweilige DAZN:-Zeile verlangt. Aus demselben
Grund entfaellt die createSiteId-Praefixierung des Originals (die dient
dort nur dazu, IDs aus verschiedenen Laendern kollisionsfrei in einem
gemeinsamen Namensraum zu halten) - die rohe AssetId wird 1:1 als site_id
verwendet.

Die Laender->Sprache-Zuordnung des Originals (COUNTRY_LANGUAGES) wird nur
in einem kleinen, fuer diesen Repo-Kontext relevanten Ausschnitt portiert:
de/at/ch/li -> "de", alle anderen Laender -> "en" (Fallback). Das ist eine
bewusste Vereinfachung gegenueber der vollstaendigen Tabelle des Originals,
aber fuer den hier erwarteten, primaer deutschsprachigen Nutzerkreis
ausreichend.

Kein Login noetig, nur die zwei statischen Header (Accept, Referer) auf
jedem Request.

WICHTIGE EINSCHRAENKUNG (im Unterschied zu Telemach/Sky, die echte
mehrtaegige Tagesraster liefern): die DAZN-API kennt kein Datum als
Parameter - ein Request liefert immer nur das aktuell verfuegbare
Now/Next/Later-Fenster fuer den jeweiligen Kanal. In der Praxis deckt das
oft nur die naechsten paar Sendungen/Stunden ab, kein echtes
mehrtaegiges Raster. Der `tage`-Parameter von dazn_hole_programme()
existiert nur der Schnittstellen-Konsistenz mit den anderen Quellen
halber und hat auf das tatsaechliche Datenfenster keinen Einfluss.

Degradiert bei jedem Fehler (Netzwerk, HTTP-Status, kein Kanal-Treffer,
unerwartetes JSON) graceful auf None/[] statt zu werfen - dieses Modul
darf einen Lauf niemals zum Absturz bringen.
"""

import difflib

import requests

from epg_lib import normalisiere_sendername

API_URL = "https://rail-router.discovery.indazn.com/eu/v10/Rail"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.dazn.com/",
}

REQUEST_TIMEOUT_SEKUNDEN = 20

# Kleiner, bewusst nicht erschoepfender Ausschnitt der COUNTRY_LANGUAGES-
# Tabelle des Originals - siehe Modul-Docstring.
_LAND_SPRACHE = {
    "de": "de",
    "at": "de",
    "ch": "de",
    "li": "de",
}

# Modul-weiter Cache: die rohe Rail-Response wird pro Land nur einmal pro
# Lauf geholt, auch wenn mehrere DAZN:-Sender desselben Landes in
# sender.txt stehen (analog zu sky_epg.py/arena_epg.py).
_raw_cache = {}


def _land_normalisieren(land):
    """Erwartet einen 2-Buchstaben-Laendercode (z.B. "de"); jeder andere
    Wert faellt still auf "de" zurueck (Validierung passiert eigentlich
    schon in generate_epg.py, hier nochmal zur Sicherheit)."""
    land = (land or "de").strip().lower()
    if len(land) == 2 and land.isalpha():
        return land
    return "de"


def _sprache_fuer_land(land):
    return _LAND_SPRACHE.get(land, "en")


def _rail_holen(land):
    """Holt (und cached pro Land) die rohe Rail-Response (Liste der
    Tiles). Leere Liste bei jedem Fehler."""
    land = _land_normalisieren(land)

    if land in _raw_cache:
        return _raw_cache[land]

    sprache = _sprache_fuer_land(land)

    try:
        response = requests.get(
            API_URL,
            params={
                "platform": "web",
                "id": "Livetvschedule",
                "country": land,
                "brand": "dazn",
                "languageCode": sprache,
            },
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        daten = response.json()
        tiles = daten.get("Tiles", []) if isinstance(daten, dict) else []
        _raw_cache[land] = tiles
        return tiles
    except Exception as e:
        print(f"DAZN-EPG: Kanalliste ({land}) fehlgeschlagen ({e}), ueberspringe.")
        _raw_cache[land] = []
        return []


def dazn_hole_kanalliste(land="de"):
    """Holt (und cached pro Land) die komplette DAZN-Kanalliste als Liste
    von {"site_id":..., "name":...}. Leere Liste bei jedem Fehler."""
    tiles = _rail_holen(land)

    kanaele = []
    for tile in tiles:
        if not isinstance(tile, dict):
            continue
        asset_id = tile.get("AssetId")
        title = tile.get("Title")
        if not asset_id or not title:
            continue
        kanaele.append({"site_id": asset_id, "name": title})

    return kanaele


def dazn_kanal_finden(kanalname, land="de"):
    """Sucht den DAZN-Kanal, der am besten zu kanalname passt - erst
    exakter Abgleich nach normalisiere_sendername(), sonst unscharfer
    difflib-Abgleich (gleiche Vorgehensweise wie sky_kanal_finden()/
    arena_kanal_finden()). Gibt die site_id (AssetId) zurueck oder
    None."""
    kanaele = dazn_hole_kanalliste(land)
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


def dazn_hole_programme(site_id, land="de", tage=3):
    """Holt Programmdaten (Now/Next/Later) fuer den gegebenen DAZN-Kanal
    (AssetId). `tage` existiert nur der Schnittstellen-Konsistenz halber
    mit den anderen Quellen - die DAZN-API liefert IMMER nur ihr aktuelles
    Now/Next/Later-Fenster, kein echtes mehrtaegiges Datumsraster (siehe
    Modul-Docstring), der Parameter hat also praktisch keinen Einfluss
    auf das Ergebnis. Liefert eine nach Startzeit sortierte, deduplizierte
    Liste von {"title", "beschreibung", "bild", "start", "stop"} (UTC,
    tz-aware) - leere Liste bei jedem Fehler."""
    if not site_id:
        return []

    tiles = _rail_holen(land)

    kanal_tile = None
    for tile in tiles:
        if isinstance(tile, dict) and tile.get("AssetId") == site_id:
            kanal_tile = tile
            break

    if kanal_tile is None:
        return []

    schedule = kanal_tile.get("LinearSchedule")
    if not isinstance(schedule, dict):
        return []

    roh_eintraege = [schedule.get("Now"), schedule.get("Next")]
    roh_eintraege.extend(schedule.get("Later") or [])

    alle_sendungen = []
    gesehene = set()

    for item in roh_eintraege:
        if not item or not isinstance(item, dict):
            continue

        titel = item.get("Title")
        start_roh = item.get("Start")
        stop_roh = item.get("End")
        if not titel or not start_roh or not stop_roh:
            continue

        try:
            start = _iso_parsen(start_roh)
            stop = _iso_parsen(stop_roh)
        except Exception:
            continue

        if start is None or stop is None:
            continue

        schluessel = (titel, start, stop)
        if schluessel in gesehene:
            continue
        gesehene.add(schluessel)

        alle_sendungen.append({
            "title": titel,
            "beschreibung": item.get("Description") or None,
            "bild": None,
            "start": start,
            "stop": stop,
        })

    alle_sendungen.sort(key=lambda s: s["start"])
    return alle_sendungen


def _iso_parsen(wert):
    """Parst einen ISO-8601-String (z.B. "2026-08-09T18:00:00Z") zu
    einem UTC-aware datetime. Gibt None bei Parse-Fehler zurueck."""
    from datetime import datetime, timezone

    try:
        text = wert.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None
