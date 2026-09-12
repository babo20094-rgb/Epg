"""Echte Programmdaten von MagentaTV (Crnogorski Telekom, Montenegro),
https://magentatv.me/epg - LETZTER Fallback fuer die montenegrinischen
Laender-Codes "MNG"/"MO" in sender.txt (nach Telemach/mtel.ba/klix.ba),
gleiche Plattform wie magentatv_mk_epg.py ("yo-digital.com"/"Reach"),
aber eigener Mandant mit eigenem natco_key/app_key.

Im Unterschied zu magentatv_mk_epg.py wird hier KEINE feste
station_id->Name-Tabelle gepflegt: der Gast-Modus-Endpunkt
"/me-bifrost/epg/channel" liefert direkt die komplette Senderliste MIT
Namen und station_id in einer einzigen Antwort (bei magentatv.me live
per Diagnose-Workflow verifiziert - der MK-Mandant hat denselben
Endpunkt offenbar nicht zuverlaessig freigegeben, deshalb dort die
Snapshot-Tabelle). Kanalzuordnung deshalb komplett dynamisch, kein
Nachpflegen bei neuen/umbenannten Sendern noetig.

Degradiert wie jede andere Quelle in diesem Projekt an JEDER Stelle
graceful auf None/[]/leere Ergebnisse, statt zu werfen.
"""

from datetime import datetime, timedelta, timezone

import re
import uuid

import requests

from epg_lib import normalisiere_sendername, normalisiere_sendername_kern

BASE_URL = "https://tv-me-prod.yo-digital.com/me-bifrost"

NATCO_KEY = "ANKB5xVVywklLUd9WtEOh8eyLnlAypTM"
APP_KEY = "erYJuNj5fnVXtRgjkr4scxbr3oEkM4I4"
APP_VERSION = "02.0.1470"

REQUEST_TIMEOUT_SEKUNDEN = 20
HOUR_RANGE = 3  # Fenstergroesse pro Anfrage, wie von der Web-App selbst verwendet

# Ein Gast-"Geraet"/eine Session pro Lauf (Modul-weit), NICHT pro
# einzelner Anfrage neu erzeugt - der echte Browser haelt beides fuer
# die komplette Sitzung konstant. Live per Diagnose-Workflow
# beobachtet: mit staendig wechselnder device-id/session-id lieferte
# die Schedules-API bei diesem Mandanten (ME) nur noch leere/fast leere
# Antworten (vermutlich serverseitige Session-Pruefung), waehrend der
# MK-Mandant das toleriert hat - schadet dort aber nicht.
_DEVICE_ID = str(uuid.uuid4())
_SESSION_ID = str(uuid.uuid4())
_sitzung_gestartet = False


def _guest_headers(x_tv_step):
    """Baut die Header-Menge, mit der die Web-App ihre eigenen
    Gast-Anfragen (kein Login) an das Backend schickt - live per
    Diagnose-Workflow (.github/workflows/diag_magentatv_me.yml)
    mitgeschnitten."""
    return {
        "app_key": APP_KEY,
        "app_version": APP_VERSION,
        "device-id": _DEVICE_ID,
        "device-density": "xhdpi",
        "device-name": "Linux - Chrome",
        "device_type": "WEB",
        "x-tv-flow": "EPG",
        "x-tv-step": x_tv_step,
        "x-call-type": "GUEST_USER",
        "x-txn-id": uuid.uuid4().hex,
        "x-request-session-id": _SESSION_ID,
        "x-request-tracking-id": str(uuid.uuid4()),
        "tenant": "tv",
        "bff_token": "",
        "accept": "application/json, text/plain, */*",
        "x-user-agent": f"web|web|Chrome-129|{APP_VERSION}|1",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
        ),
    }


def _sitzung_starten():
    """Ruft einmal pro Lauf /tenant/config auf, bevor die eigentlichen
    Daten geholt werden - repliziert den Start der echten Web-App-
    Sitzung (siehe _DEVICE_ID/_SESSION_ID oben). Ergebnis wird nicht
    ausgewertet, Fehler werden ignoriert - reine Best-Effort-
    Vorbereitung."""
    global _sitzung_gestartet
    if _sitzung_gestartet:
        return
    _sitzung_gestartet = True
    try:
        params = {"is_sso_enabled": "true", "app_language": "me", "natco_code": "me"}
        requests.get(
            f"{BASE_URL}/tenant/config", params=params,
            headers=_guest_headers("CONFIG"), timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
    except Exception:
        pass


def _iso_zeit_parsen(text):
    """Parst 'YYYY-MM-DDTHH:MM:SSZ' ODER 'YYYY-MM-DDTHH:MM:SS.ffZ' (der
    ME-Mandant liefert - anders als MK - Sekundenbruchteile) zu einem
    tz-aware datetime (UTC). None bei Parse-Fehler."""
    try:
        text = re.sub(r"\.\d+Z$", "Z", text)
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None


# Modul-weiter Cache: {"index": {schluessel: station_id}, "kern_index":
# {kern: station_id}, "kern_mehrdeutig": set(...)} - None bis zum ersten
# Zugriff, {} (leer) nach einem endgueltigen Fehlschlag.
_kanal_index_cache = None


def _kanal_index_laden():
    """Laedt (und cached modul-weit) die komplette Senderliste inkl.
    Namen ueber /epg/channel und baut daraus einen Namens-Index fuer
    magentatv_me_kanal_finden(). Leerer Index bei jedem Fehler."""
    global _kanal_index_cache

    if _kanal_index_cache is not None:
        return _kanal_index_cache

    index = {"name_index": {}, "kern_index": {}, "kern_mehrdeutig": set()}

    _sitzung_starten()

    try:
        params = {
            "natco_key": NATCO_KEY,
            "channelMap_id": "",
            "includeVirtualChannels": "false",
            "includeSyntheticChannels": "false",
            "app_language": "me",
            "natco_code": "me",
        }
        response = requests.get(
            f"{BASE_URL}/epg/channel", params=params,
            headers=_guest_headers("EPG_CHANNEL"), timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        rohdaten = response.json()
        kanaele = rohdaten.get("channels", []) or []

        for kanal in kanaele:
            station_id = kanal.get("station_id")
            name = (kanal.get("title") or "").strip()
            if not station_id or not name:
                continue

            schluessel = normalisiere_sendername(name)
            if schluessel:
                index["name_index"].setdefault(schluessel, station_id)

            kern = normalisiere_sendername_kern(name)
            if kern:
                if kern in index["kern_index"] and index["kern_index"][kern] != station_id:
                    index["kern_mehrdeutig"].add(kern)
                index["kern_index"].setdefault(kern, station_id)

        print(f"MagentaTV ME: {len(kanaele)} Sender in der Kanalliste geladen.")
    except Exception as e:
        print(f"MagentaTV ME: Kanalliste laden fehlgeschlagen ({e}), ueberspringe.")

    _kanal_index_cache = index
    return _kanal_index_cache


def _fenster_abrufen(datum, hour_offset):
    """Ruft ein einzelnes 3-Stunden-Fenster fuer ALLE Sender gleichzeitig
    ab. Gibt {station_id: [rohe Sendungs-Dicts]} zurueck, leeres Dict bei
    jedem Fehler (Netzwerk, HTTP-Status, kaputtes JSON)."""
    params = {
        "natco_key": NATCO_KEY,
        "date": datum.strftime("%Y-%m-%d"),
        "hour_offset": hour_offset,
        "hour_range": HOUR_RANGE,
        "channelMap_id": "",
        "filler": "true",
        "includeSyntheticChannels": "false",
        "app_language": "me",
        "natco_code": "me",
    }
    try:
        response = requests.get(
            f"{BASE_URL}/epg/channel/schedules", params=params,
            headers=_guest_headers("EPG_SCHEDULES"), timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        rohdaten = response.json()
        return rohdaten.get("channels", {}) or {}
    except Exception as e:
        print(f"MagentaTV ME: Abruf fuer {datum} +{hour_offset}h fehlgeschlagen ({e}), ueberspringe Fenster.")
        return {}


# Modul-weiter Cache: {station_id: [{"title":..., "beschreibung":...,
# "bild":..., "start":..., "stop":...}, ...]}
_programme_cache = None


def _alle_programme_laden(tage):
    """Laedt (und cached modul-weit) die Sendungen aller Sender fuer die
    naechsten `tage` Tage, in 3-Stunden-Fenstern. Schlaegt ein einzelnes
    Fenster fehl, wird es einfach uebersprungen."""
    global _programme_cache

    if _programme_cache is not None:
        return _programme_cache

    _sitzung_starten()

    programme = {}
    heute = datetime.now(timezone.utc).date()
    gesamt_fenster = 0
    gesamt_sendungen = 0

    for tag_offset in range(tage):
        datum = heute + timedelta(days=tag_offset)
        for hour_offset in range(0, 24, HOUR_RANGE):
            kanaele = _fenster_abrufen(datum, hour_offset)
            gesamt_fenster += 1
            for station_id, eintraege in kanaele.items():
                for roh in eintraege:
                    start = _iso_zeit_parsen(roh.get("start_time", ""))
                    stop = _iso_zeit_parsen(roh.get("end_time", ""))
                    if start is None or stop is None:
                        continue
                    titel = (roh.get("episode_name") or roh.get("description") or "").strip()
                    if not titel:
                        continue
                    beschreibung = (roh.get("full_description") or "").strip()
                    programme.setdefault(station_id, []).append({
                        "title": titel,
                        "beschreibung": beschreibung,
                        "bild": roh.get("poster_image_url") or roh.get("image"),
                        "start": start,
                        "stop": stop,
                    })
                    gesamt_sendungen += 1

    for eintraege in programme.values():
        eintraege.sort(key=lambda s: s["start"])

    print(f"MagentaTV ME: {gesamt_fenster} Zeitfenster abgefragt, {gesamt_sendungen} Sendungen fuer {len(programme)} Sender geladen.")

    _programme_cache = programme
    return _programme_cache


def magentatv_me_kanal_finden(kanalname):
    """Sucht per live geladenem Namens-Index (siehe
    _kanal_index_laden()) nach einem zu kanalname passenden Sender.
    Erst exakter Abgleich nach normalisiere_sendername(), dann
    Kern-Abgleich ohne HD/FHD/UHD/SD. Gibt die station_id zurueck oder
    None."""
    ziel_schluessel = normalisiere_sendername(kanalname)
    if not ziel_schluessel:
        return None

    index = _kanal_index_laden()
    if not index["name_index"]:
        return None

    if ziel_schluessel in index["name_index"]:
        return index["name_index"][ziel_schluessel]

    ziel_kern = normalisiere_sendername_kern(kanalname)
    if ziel_kern and ziel_kern in index["kern_index"] and ziel_kern not in index["kern_mehrdeutig"]:
        return index["kern_index"][ziel_kern]

    return None


def magentatv_me_hole_programme(station_id, tage=2):
    """Liefert die Sendungen fuer den gegebenen Sender (station_id) aus
    dem Modul-Cache, begrenzt auf die naechsten `tage` Tage ab heute
    (UTC). Leere Liste bei jedem Fehler oder wenn fuer diesen Sender
    keine Sendungen vorhanden sind."""
    if station_id is None:
        return []

    programme = _alle_programme_laden(tage)
    return programme.get(station_id, [])
