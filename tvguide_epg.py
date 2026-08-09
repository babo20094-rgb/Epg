"""Optionale, echte Programmdaten von der TVGuide.com-US-EPG-API.

Genau wie sky_epg.py/dazn_epg.py/freeview_epg.py ist diese Quelle
AUSSCHLIESSLICH opt-in ueber das "TVGUIDE:"-Praefix in sender.txt - es
gibt hier bewusst KEIN automatisches Matching gegen bestehende
sender.txt-Zeilen (zu viele US-aehnliche Zeilen, zu viele API-Aufrufe pro
Lauf, zu hohes Fehltreffer-Risiko).

Portiert aus dem config.js-Site-Plugin "tvguide.com" des iptv-org/epg-
Projekts, aber deutlich im Umfang reduziert:

- Es wird nur EIN fest hinterlegter providerId ("9100001138", die
  nationale/generische US-Grundaufstellung) verwendet, nicht die
  Postleitzahl-/Anbieter-abhaengige Provider-Auswahl des Originals. Das
  deckt die gaengigen US-Networks (CBS, NBC, ABC, FOX, ...) ab, verpasst
  aber lokale/kabelanbieter-spezifische Sender.
- Das Original holt zusaetzlich pro Sendung per "programDetails"-URL eine
  volle Beschreibung/Rating/Genres nach. Das wird hier NICHT portiert (zu
  viele Extra-Requests: waeren N weitere Requests pro Sendung zusaetzlich
  zu den ohnehin 6 Segment-Requests pro Kanal/Tag) - beschreibung bleibt
  deshalb immer None, genau wie bei dazn_epg.py/arena_epg.py.
- Ein Tag wird als 6 aufeinanderfolgende 4-Stunden-Segmente abgefragt
  (1440 Minuten / 240 Minuten pro Segment), analog zum Original.

Kein Login noetig, nur ein Referer- und User-Agent-Header auf jedem
Request (die API blockt sonst teils generische Requests ohne Browser-
aehnliche Header).

Degradiert bei jedem Fehler (Netzwerk, HTTP-Status, kein Kanal-Treffer,
unerwartetes JSON) graceful auf None/[] statt zu werfen - dieses Modul
darf einen Lauf niemals zum Absturz bringen.
"""

import difflib
from datetime import datetime, timedelta, timezone

import requests

from epg_lib import normalisiere_sendername

API_BASE = "https://backend.tvguide.com/tvschedules/tvguide"

# Fest hinterlegte, nationale US-Grundaufstellung - siehe Modul-Docstring.
PROVIDER_ID = "9100001138"

SEGMENT_MINUTEN = 240
SEGMENTE_PRO_TAG = 1440 // SEGMENT_MINUTEN  # = 6

REQUEST_TIMEOUT_SEKUNDEN = 20

HEADERS = {
    "Referer": "https://www.tvguide.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

# Modul-weiter Cache: pro Segment-Start-Unix-Timestamp wird die rohe
# Response nur einmal pro Lauf geholt, auch wenn mehrere TVGUIDE:-Sender
# in sender.txt stehen.
_segment_cache = {}


def _tagesstart_unix(tag_offset=0):
    tag = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    tag += timedelta(days=tag_offset)
    return int(tag.timestamp())


def _segment_holen(start_unix):
    if start_unix in _segment_cache:
        return _segment_cache[start_unix]

    try:
        response = requests.get(
            f"{API_BASE}/{PROVIDER_ID}/web",
            params={"start": start_unix, "duration": SEGMENT_MINUTEN},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        daten = response.json()
        items = (
            daten.get("data", {}).get("items", [])
            if isinstance(daten, dict) else []
        )
        _segment_cache[start_unix] = items
        return items
    except Exception as e:
        print(f"TVGuide-EPG: Segment-Abruf (start={start_unix}) fehlgeschlagen ({e}), ueberspringe.")
        _segment_cache[start_unix] = []
        return []


def _kanalliste_bereinigen(name):
    if not name:
        return name
    return " ".join(
        wort for wort in name.replace("Channel", " ").replace("Schedule", " ").split()
    ).strip() or name


def tvguide_hole_kanalliste():
    """Holt (und cached) die TVGuide-Kanalliste (nur die eine fest
    hinterlegte nationale providerId, siehe Modul-Docstring) als Liste
    von {"site_id": sourceId, "name": ...}. Leere Liste bei jedem
    Fehler."""
    try:
        response = requests.get(
            f"{API_BASE}/serviceprovider/{PROVIDER_ID}/sources/web",
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        daten = response.json()
        items = daten.get("data", {}).get("items", []) if isinstance(daten, dict) else []
    except Exception as e:
        print(f"TVGuide-EPG: Kanalliste fehlgeschlagen ({e}), ueberspringe.")
        return []

    kanaele = []
    gesehene = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        source_id = item.get("sourceId")
        name_roh = item.get("fullName")
        if source_id is None or not name_roh or source_id in gesehene:
            continue
        gesehene.add(source_id)
        kanaele.append({"site_id": source_id, "name": _kanalliste_bereinigen(name_roh)})

    return kanaele


def tvguide_kanal_finden(kanalname):
    """Sucht den TVGuide-Kanal, der am besten zu kanalname passt - erst
    exakter Abgleich nach normalisiere_sendername(), sonst unscharfer
    difflib-Abgleich (gleiche Vorgehensweise wie die anderen Quellen).
    Gibt die site_id (sourceId) zurueck oder None."""
    kanaele = tvguide_hole_kanalliste()
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


def tvguide_hole_programme(site_id, tage=2):
    """Holt Programmdaten fuer den gegebenen TVGuide-Kanal (sourceId) fuer
    `tage` aufeinanderfolgende Tage ab heute (UTC), jeder Tag als 6
    aufeinanderfolgende 4-Stunden-Segmente abgefragt (siehe Modul-
    Docstring). Liefert eine nach Startzeit sortierte, deduplizierte
    Liste von {"title", "beschreibung", "bild", "start", "stop"} (UTC,
    tz-aware) - leere Liste bei jedem Fehler."""
    if site_id is None:
        return []

    site_id_str = str(site_id)

    alle_sendungen = []
    gesehene = set()

    for tag_index in range(tage):
        tagesstart = _tagesstart_unix(tag_index)

        for segment_index in range(SEGMENTE_PRO_TAG):
            segment_start = tagesstart + segment_index * SEGMENT_MINUTEN * 60
            items = _segment_holen(segment_start)

            for item in items:
                if not isinstance(item, dict):
                    continue
                kanal = item.get("channel") or {}
                if str(kanal.get("sourceId")) != site_id_str:
                    continue

                for eintrag in item.get("programSchedules", []) or []:
                    if not isinstance(eintrag, dict):
                        continue

                    titel = eintrag.get("title")
                    start_unix = eintrag.get("startTime")
                    stop_unix = eintrag.get("endTime")
                    if not titel or start_unix is None or stop_unix is None:
                        continue

                    try:
                        start = datetime.fromtimestamp(start_unix, tz=timezone.utc)
                        stop = datetime.fromtimestamp(stop_unix, tz=timezone.utc)
                    except Exception:
                        continue

                    schluessel = (titel, start, stop)
                    if schluessel in gesehene:
                        continue
                    gesehene.add(schluessel)

                    alle_sendungen.append({
                        "title": titel,
                        "beschreibung": None,
                        "bild": None,
                        "start": start,
                        "stop": stop,
                    })

    alle_sendungen.sort(key=lambda s: s["start"])
    return alle_sendungen
