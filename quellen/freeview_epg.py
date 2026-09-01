"""Optionale, echte Programmdaten von der Freeview-UK-TV-Guide-API.

Genau wie sky_epg.py/dazn_epg.py/arena_epg.py ist diese Quelle
AUSSCHLIESSLICH opt-in ueber das "FREEVIEW:"-Praefix in sender.txt - es
gibt hier bewusst KEIN automatisches Matching gegen bestehende
sender.txt-Zeilen (zu viele GB/UK-aehnliche Zeilen, zu viele API-Aufrufe
pro Lauf, zu hohes Fehltreffer-Risiko).

Portiert aus dem config.js-Site-Plugin "freeview.co.uk" des iptv-org/epg-
Projekts, aber deutlich im Umfang reduziert:

- Das Original loopt beim channels()-Abruf ueber ~169 regionale UK-
  Network-IDs (64257 bis 64425), um wirklich JEDEN regionalen Opt-out-
  Kanal zu erfassen. Wir fragen stattdessen NUR die eine repraesentative
  Network-ID 64257 ("Greater London") ab - das deckt alle NATIONALEN
  Kanaele ab (BBC One, ITV1, Channel 4, Sky-Kanaele auf Freeview, etc.),
  verpasst aber rein regionale Lokalnachrichten-Opt-outs. Fuer diesen
  Repo-Kontext (primaer nationale Sender) eine akzeptable Vereinfachung.
- Das Original holt zusaetzlich pro Sendung per "loadProgramDetails" eine
  laengere Synopsis per separatem HTTP-Request nach. Das wird hier NICHT
  portiert (zu viele Extra-Requests fuer unseren Zweck) - beschreibung
  bleibt entsprechend meistens None, genau wie bei dazn_epg.py/
  arena_epg.py.
- Die Dauer-Angabe im JSON-Feld "duration" wird im Original per npm-Paket
  "parse-duration" geparst, dessen genaues Eingabeformat hier nicht
  verifiziert werden konnte (kein Live-Netzwerkzugriff aus dieser
  Sandbox moeglich). _dauer_parsen() implementiert deshalb einen best-
  effort-Parser, der mehrere plausible Formate abdeckt (reine Sekunden-
  Zahl, "HH:MM:SS", zusammengesetzte Strings wie "1h30m") und bei jedem
  unbekannten Format graceful ueberspringt (kein Crash) - siehe
  Kommentar bei _dauer_parsen(). Diese Annahme ist NICHT gegen eine
  echte Response verifiziert und sollte bei Gelegenheit gegengeprueft
  werden, sobald ein Live-Abruf moeglich ist.

Kein Login noetig, keine besonderen Header.

Degradiert bei jedem Fehler (Netzwerk, HTTP-Status, kein Kanal-Treffer,
unerwartetes JSON, unparsbare Dauer) graceful auf None/[] statt zu
werfen - dieses Modul darf einen Lauf niemals zum Absturz bringen.
"""

import difflib
import re
from datetime import datetime, timedelta, timezone

import requests

from epg_lib import normalisiere_sendername

API_URL = "https://www.freeview.co.uk/api/tv-guide"

# Repraesentative Network-ID ("Greater London") - siehe Modul-Docstring.
NETWORK_ID = "64257"

REQUEST_TIMEOUT_SEKUNDEN = 20

# Modul-weiter Cache: die rohe tv-guide-Response wird pro (network_id,
# Tages-Unix-Timestamp) nur einmal pro Lauf geholt.
_raw_cache = {}


def _tagesstart_unix(tag_offset=0):
    tag = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    tag += timedelta(days=tag_offset)
    return int(tag.timestamp())


def _guide_holen(network_id, start_unix):
    schluessel = (network_id, start_unix)
    if schluessel in _raw_cache:
        return _raw_cache[schluessel]

    try:
        response = requests.get(
            API_URL,
            params={"nid": network_id, "start": start_unix},
            timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        daten = response.json()
        programs = (
            daten.get("data", {}).get("programs", [])
            if isinstance(daten, dict) else []
        )
        _raw_cache[schluessel] = programs
        return programs
    except Exception as e:
        print(f"Freeview-EPG: Guide-Abruf (nid={network_id}, start={start_unix}) fehlgeschlagen ({e}), ueberspringe.")
        _raw_cache[schluessel] = []
        return []


def freeview_hole_kanalliste():
    """Holt (und cached) die Freeview-Kanalliste (nur nationale Kanaele
    ueber die eine repraesentative Network-ID, siehe Modul-Docstring) als
    Liste von {"site_id": "64257#<service_id>", "name": ...}. Leere
    Liste bei jedem Fehler."""
    programs = _guide_holen(NETWORK_ID, _tagesstart_unix(0))

    kanaele = []
    gesehene = set()
    for programm in programs:
        if not isinstance(programm, dict):
            continue
        service_id = programm.get("service_id")
        title = programm.get("title")
        if service_id is None or not title or service_id in gesehene:
            continue
        gesehene.add(service_id)
        kanaele.append({"site_id": f"{NETWORK_ID}#{service_id}", "name": title})

    return kanaele


def freeview_kanal_finden(kanalname):
    """Sucht den Freeview-Kanal, der am besten zu kanalname passt - erst
    exakter Abgleich nach normalisiere_sendername(), sonst unscharfer
    difflib-Abgleich (gleiche Vorgehensweise wie die anderen Quellen).
    Gibt die site_id ("64257#<service_id>") zurueck oder None."""
    kanaele = freeview_hole_kanalliste()
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


def _dauer_parsen(wert):
    """Best-effort-Parser fuer die "duration"-Angabe im Freeview-JSON,
    dessen genaues Format nicht gegen eine echte Response verifiziert
    werden konnte (siehe Modul-Docstring). Probiert der Reihe nach:
    1. reine Zahl -> Sekunden
    2. "HH:MM:SS" oder "MM:SS"
    3. zusammengesetzter String wie "1h30m", "1h 30m", "90m"
    Gibt eine timedelta zurueck oder None, wenn nichts davon passt."""
    if wert is None:
        return None

    if isinstance(wert, (int, float)):
        try:
            return timedelta(seconds=float(wert))
        except Exception:
            return None

    text = str(wert).strip()
    if not text:
        return None

    try:
        return timedelta(seconds=float(text))
    except ValueError:
        pass

    if ":" in text:
        teile = text.split(":")
        try:
            teile = [int(t) for t in teile]
        except ValueError:
            teile = None
        if teile is not None:
            if len(teile) == 3:
                h, m, s = teile
                return timedelta(hours=h, minutes=m, seconds=s)
            if len(teile) == 2:
                m, s = teile
                return timedelta(minutes=m, seconds=s)

    treffer = re.findall(r"(\d+)\s*h|(\d+)\s*m(?!s)|(\d+)\s*s", text, flags=re.IGNORECASE)
    if treffer:
        stunden = minuten = sekunden = 0
        for h, m, s in treffer:
            if h:
                stunden += int(h)
            if m:
                minuten += int(m)
            if s:
                sekunden += int(s)
        if stunden or minuten or sekunden:
            return timedelta(hours=stunden, minutes=minuten, seconds=sekunden)

    return None


def freeview_hole_programme(site_id, tage=2):
    """Holt Programmdaten fuer den gegebenen Freeview-Kanal
    ("64257#<service_id>") fuer `tage` aufeinanderfolgende Tage ab heute
    (UTC, entspricht dem "days: 2" im Original). Liefert eine nach
    Startzeit sortierte Liste von {"title", "beschreibung", "bild",
    "start", "stop"} (UTC, tz-aware) - leere Liste bei jedem Fehler."""
    if not site_id or "#" not in site_id:
        return []

    network_id, _, service_id = site_id.partition("#")

    alle_sendungen = []
    gesehene = set()

    for tag_index in range(tage):
        start_unix = _tagesstart_unix(tag_index)
        programs = _guide_holen(network_id, start_unix)

        kanal_programm = None
        for programm in programs:
            if isinstance(programm, dict) and str(programm.get("service_id")) == service_id:
                kanal_programm = programm
                break

        if kanal_programm is None:
            continue

        for event in kanal_programm.get("events", []) or []:
            if not isinstance(event, dict):
                continue

            haupttitel = event.get("main_title")
            start_roh = event.get("start_time")
            dauer_roh = event.get("duration")
            if not haupttitel or not start_roh or dauer_roh is None:
                continue

            try:
                text = start_roh.replace("Z", "+00:00")
                start = datetime.fromisoformat(text)
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                start = start.astimezone(timezone.utc)
            except Exception:
                continue

            dauer = _dauer_parsen(dauer_roh)
            if dauer is None:
                # Unbekanntes Dauer-Format: diese eine Sendung wird
                # uebersprungen statt abzustuerzen (siehe Modul-Docstring).
                continue

            stop = start + dauer

            untertitel = event.get("secondary_title")
            titel = f"{haupttitel} ({untertitel})" if untertitel else haupttitel

            schluessel = (titel, start, stop)
            if schluessel in gesehene:
                continue
            gesehene.add(schluessel)

            alle_sendungen.append({
                "title": titel,
                "beschreibung": None,
                "bild": event.get("image_url") or None,
                "start": start,
                "stop": stop,
            })

    alle_sendungen.sort(key=lambda s: s["start"])
    return alle_sendungen
