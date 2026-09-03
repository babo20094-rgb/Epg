"""Automatische, echte Programmdaten von MojMaxTV (Hrvatski Telekom,
Kroatien) - mojmaxtv.hrvatskitelekom.hr.

AUTOMATISCH fuer jeden ganz normal in sender.txt eingetragenen Sender
mit Land "HR" (kein eigenes Praefix noetig, gleiches Prinzip wie der
BA/ME-Telemach-Autoabgleich in generate_epg.py) - bei ~42 HR-Zeilen in
sender.txt ist das Volumen an zusaetzlichen API-Aufrufen pro Lauf
ueberschaubar. Portiert aus dem config.js-Site-Plugin
"mojmaxtv.hrvatskitelekom.hr" des iptv-org/epg-Projekts, angepasst auf
requests statt axios/dayjs.

Braucht keinen Nutzer-Login, aber jede Anfrage muss einen Satz
signierter Header mitschicken (fester/eingebetteter App-Key, kein
personenbezogenes Geheimnis). Anders als das Original wird hier bewusst
KEIN Programm-Detail-Request pro Sendung nachgeladen (kein
sub_title/season/episode/Cast) - nur title/beschreibung(leer)/start/
stop, analog zur bewussten Vereinfachung in freeview_epg.py/
tvguide_epg.py.

Degradiert an JEDER Stelle graceful auf None/[] statt zu werfen:
schlaegt Kanalsuche oder Programmabruf fehl, bekommt der betroffene
Sender in generate_epg.py einfach die normale, kategoriebasierte
generische EPG-Generierung wie jeder andere Sender - dieses Modul darf
einen Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import difflib
import hashlib
import re
import time
import uuid

import requests

from epg_lib import normalisiere_sendername

APP_KEY = "GWaBW4RTloLwpUgYVzOiW5zUxFLmoMj5"
NATCO_KEY = "l2lyvGVbUm2EKJE96ImQgcc8PKMZWtbE"
API_ENDPOINT = "https://tv-hr-prod.yo-digital.com/hr-bifrost"

CHANNELS_URL = f"{API_ENDPOINT}/epg/channel"
SCHEDULES_URL = f"{API_ENDPOINT}/epg/channel/schedules"

REQUEST_TIMEOUT_SEKUNDEN = 20

STUNDEN_OFFSETS = (0, 3, 6, 9, 12, 15, 18, 21)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)

# Modul-weit einmalig erzeugte IDs (analog zum "const DEVICE_ID =
# crypto.randomUUID()" auf Modulebene in der JS-Referenz) - bleiben
# fuer den ganzen Lauf gleich, die Tracking-ID wird pro Anfrage neu
# erzeugt.
_DEVICE_ID = str(uuid.uuid4())
_SESSION_ID = str(uuid.uuid4())

# Modul-weiter Cache, analog zu telemach_epg.py.
_kanalliste_cache = None
_schedule_cache = {}


def _headers():
    """Baut einen frischen, signierten Header-Satz fuer eine einzelne
    Anfrage (Tracking-ID + x-txn-id-Hash jedes Mal neu, Device-/
    Session-ID modul-weit stabil - siehe MCP-Aufgabenbeschreibung)."""
    jetzt_ms = int(time.time() * 1000)
    tracking_id = str(uuid.uuid4())

    txn_quelle = f"{tracking_id}{_SESSION_ID}{_DEVICE_ID}{jetzt_ms}"
    txn_id = hashlib.sha256(txn_quelle.encode("utf-8")).hexdigest()[:32]

    return {
        "app_key": APP_KEY,
        "app_version": "02.0.1470",
        "device-id": _DEVICE_ID,
        "tenant": "tv",
        "user-agent": USER_AGENT,
        "origin": "https://mojmaxtv.hrvatskitelekom.hr",
        "x-call-type": "GUEST_USER",
        "x-call-time": str(jetzt_ms),
        "x-request-session-id": _SESSION_ID,
        "x-request-tracking-id": tracking_id,
        "x-tv-step": "EPG_SCHEDULES",
        "x-tv-flow": "EPG",
        "x-user-agent": "web|web|Chrome-149|02.0.1470|1",
        "x-txn-id": txn_id,
    }


def mojmaxtv_hole_kanalliste():
    """Holt (und cached) die komplette MojMaxTV-Kanalliste als Liste
    von {"site_id":..., "name":...}. Leere Liste bei jedem Fehler."""
    global _kanalliste_cache

    if _kanalliste_cache is not None:
        return _kanalliste_cache

    try:
        response = requests.get(
            CHANNELS_URL,
            params={
                "channelMap_id": "",
                "includeVirtualChannels": "false",
                "natco_key": NATCO_KEY,
                "app_language": "hr",
                "natco_code": "hr",
            },
            headers=_headers(),
            timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        daten = response.json()
        roh_kanaele = daten.get("channels", []) if isinstance(daten, dict) else []

        kanaele = []
        for kanal in roh_kanaele:
            station_id = kanal.get("station_id")
            titel = kanal.get("title")
            if not station_id or not titel:
                continue
            kanaele.append({"site_id": station_id, "name": titel})

        _kanalliste_cache = kanaele
        return kanaele
    except Exception as e:
        print(f"MojMaxTV-EPG: Kanalliste fehlgeschlagen ({e}), ueberspringe.")
        _kanalliste_cache = []
        return []


def mojmaxtv_kanal_finden(kanalname):
    """Sucht den MojMaxTV-Kanal, der am besten zu kanalname passt -
    erst exakter Abgleich nach normalisiere_sendername(), sonst
    unscharfer difflib-Abgleich. Gibt die station_id zurueck oder
    None."""
    kanaele = mojmaxtv_hole_kanalliste()
    if not kanaele:
        return None

    # "SK 1".."SK 10" (eigene Playlist-Abkuerzung in sender.txt, z.B.
    # "HR|SK 1") vs. "Sport Klub 1" (voller Name bei MojMaxTV, FALLS
    # vorhanden): die normalisierten Schluessel "SK1" vs. "SPORTKLUB1"
    # liegen bei so kurzen Strings weit unter der difflib-Aehnlichkeits-
    # Schwelle (0.72), ein exakter Treffer war deshalb nie moeglich.
    # WICHTIG (Bug September 2026 behoben): MojMaxTV fuehrt inzwischen
    # GAR KEINEN "Sport Klub"-Kanal mehr in der Kanalliste (nur noch
    # Arena Sport 1-10 u.ae.) - der unscharfe difflib-Fallback unten
    # matchte "SK 1" dadurch faelschlich auf den voellig unabhaengigen
    # Kanal "Sport 1" (deutsche Sendungen statt kroatischem Sport-Klub-
    # Programm). Fuer dieses Alias-Muster wird deshalb NUR noch ein
    # exakter Treffer akzeptiert - kein unscharfer Fallback, lieber
    # kein Treffer als ein falscher.
    sk_match = re.match(r"^SK\s*0*(\d+)$", kanalname.strip(), re.IGNORECASE)
    if sk_match:
        kanalname = f"Sport Klub {sk_match.group(1)}"
        ziel_schluessel = normalisiere_sendername(kanalname)
        for kanal in kanaele:
            if normalisiere_sendername(kanal["name"]) == ziel_schluessel:
                return kanal["site_id"]
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


def _zeit_parsen(wert):
    """Parst die von der MojMaxTV-API gelieferten Zeitstempel (ISO
    8601, ggf. mit "Z"-Suffix) zu einem tz-aware UTC-datetime. Gibt bei
    jedem Parse-Fehler None zurueck."""
    if not wert:
        return None
    try:
        normalisiert = wert.replace("Z", "+00:00")
        zeitpunkt = datetime.fromisoformat(normalisiert)
        if zeitpunkt.tzinfo is None:
            zeitpunkt = zeitpunkt.replace(tzinfo=timezone.utc)
        return zeitpunkt.astimezone(timezone.utc)
    except Exception:
        return None


def _hole_schedules_fuer_tag(datum):
    """Holt (und cached pro Datum) alle 3h-Zeitfenster fuer einen Tag
    und fuegt sie zu {station_id: [sendung, ...]} zusammen. Leeres
    dict bei jedem Fehler/Teilfehler."""
    datum_str = datum.strftime("%Y-%m-%d")

    if datum_str in _schedule_cache:
        return _schedule_cache[datum_str]

    zusammengefasst = {}

    for offset in STUNDEN_OFFSETS:
        try:
            response = requests.get(
                SCHEDULES_URL,
                params={
                    "date": datum_str,
                    "hour_offset": offset,
                    "hour_range": 3,
                    "channelMap_id": "",
                    "filler": "true",
                    "app_language": "hr",
                    "natco_code": "hr",
                },
                headers=_headers(),
                timeout=REQUEST_TIMEOUT_SEKUNDEN,
            )
            response.raise_for_status()
            daten = response.json()
            kanal_dict = daten.get("channels", {}) if isinstance(daten, dict) else {}
            if not isinstance(kanal_dict, dict):
                continue

            for station_id, sendungen in kanal_dict.items():
                if not isinstance(sendungen, list):
                    continue
                zusammengefasst.setdefault(station_id, []).extend(sendungen)
        except Exception as e:
            print(f"MojMaxTV-EPG: Zeitfenster ({datum_str}, offset {offset}) fehlgeschlagen ({e}), ueberspringe Fenster.")
            continue

    _schedule_cache[datum_str] = zusammengefasst
    return zusammengefasst


def mojmaxtv_hole_programme(site_id, tage=2):
    """Holt Programmdaten fuer den gegebenen MojMaxTV-Kanal (station_id)
    fuer `tage` aufeinanderfolgende Tage ab heute (UTC). Liefert eine
    nach Startzeit sortierte Liste von {"title", "beschreibung", "bild",
    "start", "stop"} - leere Liste bei jedem Fehler (Netzwerk, HTTP-
    Status, unerwartetes JSON)."""
    if not site_id:
        return []

    heute = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    alle_sendungen = []

    for tag_index in range(tage):
        tag = heute + timedelta(days=tag_index)

        try:
            kanal_dict = _hole_schedules_fuer_tag(tag)
            sendungen_roh = kanal_dict.get(site_id, []) or []

            for sendung in sendungen_roh:
                titel = sendung.get("description")
                start = _zeit_parsen(sendung.get("start_time"))
                stop = _zeit_parsen(sendung.get("end_time"))
                if not titel or not start or not stop:
                    continue

                alle_sendungen.append({
                    "title": titel,
                    "beschreibung": "",
                    "bild": None,
                    "start": start,
                    "stop": stop,
                })
        except Exception as e:
            print(f"MojMaxTV-EPG: Programmabruf fuer Kanal {site_id} Tag {tag_index} fehlgeschlagen ({e}), ueberspringe Tag.")
            continue

    alle_sendungen.sort(key=lambda s: s["start"])
    return alle_sendungen
