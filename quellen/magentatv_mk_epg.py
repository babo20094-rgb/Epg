"""Echte Programmdaten von MagentaTV GO Nordmazedonien
(https://www.magentatv.mk/epg) - LETZTER Fallback fuer MK-Sender (nach
mk_epg.py/iptv-epg.org) UND zusaetzlich fuer BA/RS/HR-Sender, die im
selben Balkan-Paket mitlaufen (Serbien/Kroatien/Bosnien-Kanaele wie
PRVA, B92, RTL 2, die PINK-Familie, ARENA Fight/Esport usw.), aber
bisher keine eigene echte Quelle hatten - siehe docs/HISTORIE.md.

Hintergrund/Recherche (September 2026): MagentaTV GO ist eine reine
JavaScript-SPA (Backend "yo-digital.com"/Plattform "Reach"), die
Sender+Sendungen erst per XHR nachlaedt. Ein direkter Login ist NICHT
noetig - die Web-App ruft ihr eigenes Backend im Gast-Modus
("x-call-type: GUEST_USER") auf, das oeffentlich (ohne Account/Token)
funktioniert. Per GitHub-Actions-Diagnose-Workflow
(.github/workflows/diag_magentatv.yml) wurden die echten, im Browser
verwendeten Header/Endpunkte mitgeschnitten (siehe dortige Artefakte).

WICHTIG: Der Endpunkt liegt hinter Akamai und antwortet aus manchen
Rechenzentrums-/Cloud-IP-Bereichen mit HTTP 500 (z.B. aus der
Claude-Code-Sandbox) - lief aber zuverlaessig aus GitHub-Actions-
Runnern. Degradiert deshalb hier wie jede andere Quelle graceful auf
leere Ergebnisse, falls der Abruf aus irgendeinem Grund fehlschlaegt.

Sender-Zuordnung: Die Schedules-API liefert Sendungen ausschliesslich
nach einer internen numerischen "station_id" (z.B. "19122" fuer
MRT 1 HD), OHNE Sendernamen in der Antwort. Diese station_id ist aber
identisch mit der Nummer in den Logo-Bild-URLs
(https://ottapp-akamai-client-a.proda.dtp.tv3cloud.com/images/images/
station/<station_id>/4x3/logomedium.png) und im channel-logo-<img
alt="..."> der Web-App. Eine feste station_id->Name-Tabelle
(STATION_NAMEN unten) wurde deshalb einmalig aus mehreren, komplett
durchgescrollten Snapshots der Sender-Karussells extrahiert (siehe
Chat-Verlauf/Commit-Historie) - kein Live-Abruf einer Kanalliste
noetig, da dieser Katalog laut Recherche stabil ist. Faellt ein Sender
NICHT in dieser Tabelle auf, wird er von diesem Modul einfach
uebersprungen (mk_kanal_finden()/generische Quellen bleiben Fallback).
"""

from datetime import datetime, timedelta, timezone

import re

import requests
import uuid

from epg_lib import normalisiere_sendername, normalisiere_sendername_kern

BASE_URL = "https://tv-mk-prod.yo-digital.com/mk-bifrost/epg/channel/schedules"

NATCO_KEY = "HEEb5emU9KZG4prn2NaUkiv96g3IxpS6"
APP_KEY = "webq1ptdD5Gy4IatUZRiTezSu6sNc57A"
APP_VERSION = "02.0.1470"

REQUEST_TIMEOUT_SEKUNDEN = 20
HOUR_RANGE = 3  # Fenstergroesse pro Anfrage, wie von der Web-App selbst verwendet

# station_id (siehe Logo-URLs) -> Sendername, wie auf magentatv.mk/epg
# angezeigt. Nur die per Snapshot bestaetigten Sender - bewusst keine
# Vollstaendigkeit fuer den kompletten ~346-Sender-Katalog.
STATION_NAMEN = {
    "19068": "City Play",
    "19071": "PINK HITS",
    "19075": "PINK MUSIC 2",
    "19077": "BRAVO",
    "19078": "PINK EXTRA",
    "19080": "STAR",
    "19093": "PINK FOLK 1",
    "19094": "PINK FOLK 2",
    "19095": "PINK REALITY",
    "19096": "PINK WORLD",
    "19097": "PINK N ROLL",
    "19098": "PINK ZABAVA",
    "19100": "PINK HITS 2",
    "19102": "PINK SHOW",
    "19109": "ARENA FIGHT HD",
    "19111": "DA VINCI HD",
    "19112": "TV EDO",
    "19113": "DM sat",
    "19114": "Infokanal",
    "19122": "MRT 1 HD",
    "19124": "МРТ 2 HD",
    "19135": "BRAINZ HD",
    "19137": "NOVA S HD",
    "19139": "M NET HD",
    "19146": "ALPHA HD",
    "19148": "RTV 21",
    "19155": "T ACTION",
    "19162": "NICKTOONS",
    "19164": "T DRAMA",
    "19167": "AGRO TV HD",
    "19168": "РТС СВЕТ HD",
    "19176": "ТВК",
    "19177": "STAR CHANNEL",
    "19178": "STAR LIFE",
    "19181": "NAT GEO HD",
    "19184": "PRVA HD",
    "19188": "PRVA FILES HD",
    "19189": "PRVA KICK HD",
    "19190": "PRVA LIFE HD",
    "19191": "KCN 1",
    "19192": "KCN 2",
    "19193": "KCN 3",
    "19194": "B92 HD",
    "19195": "HAPPY HD",
    "19196": "HAPPY REALITY 1",
    "19197": "HAPPY REALITY 2",
    "19220": "LUXE TV HD",
    "19221": "USKANA",
    "19222": "ТВ КОБРА",
    "19223": "ERA",
    "19225": "HAYAT MUSIC BOX",
    "19227": "ТВ СВЕТ",
    "19230": "KLAN KOSOVA",
    "19231": "ANIMAL PLANET HD",
    "19232": "RTV 21 M HD",
    "19236": "TEVE 1",
    "19237": "TOP ESTRADA",
    "19238": "DISCOVERY HD",
    "19240": "M1",
    "19241": "M1 GOLD",
    "19243": "DISCOVERY ID HD",
    "19251": "ZDRAVA TELEVIZIJA",
    "19253": "RTK",
    "19254": "ART KINO 1",
    "19255": "T PRIME 2",
    "19269": "RTL 2",
    "19270": "RTL LIVING",
    "19271": "RTL KOCKICA",
    "19285": "GRAND 2",
    "19287": "Kanal 5 HD",
    "19289": "СОБРАНИСКИ КАНАЛ HD",
    "19292": "TV 5 HD",
    "19293": "FTV HD",
    "19295": "VIASAT EXPLORER HD",
    "19297": "VIASAT HISTORY HD",
    "19298": "VIASAT NATURE HD",
    "19301": "VIASAT KINO",
    "19304": "TV SHENJA",
    "19308": "SITEL HD",
    "19309": "ALSAT M HD",
    "19310": "EUROSPORT HD",
    "19311": "EUROSPORT 2 HD",
    "19316": "HBO HD",
    "19319": "CINEMAX HD",
    "19320": "CINEMAX 2 HD",
    "19324": "DUKAGJINI TV",
    "19325": "KANAL 10",
    "19326": "ARTA TV",
    "19337": "BBC EARTH HD",
    "19338": "FOOD NETWORK HD",
    "19342": "TELMA HD",
    "19346": "ART KINO 3",
    "19347": "GRAND",
    "19416": "ART KINO 2",
    "19424": "BESA",
    "19425": "DISNEY CHANNEL",
    "19426": "DISNEY JUNIOR",
    "19427": "ATV",
    "19428": "NTV SHENDETI",
    "20020": "ARENA ESPORT HD",
    "20021": "BALKAN TRIP HD",
    "20045": "SUPERSTAR 2 HD",
    "20134": "JEKA",
    "20137": "RR",
    "20138": "WWM",
    "22480": "ВИСТЕЛ",
    "22681": "UAT 1",
    "22682": "UAT 2",
    "22683": "UAT 3",
    "22684": "UAT 4",
    "22686": "UAT 6",
    "22743": "ИНФО КАНАЛ 2",
    "22744": "ИНФО КАНАЛ 3",
    "22817": "SCI-FI",
    "22819": "DIVA",
    "22820": "MEZZO",
    "22821": "MEZZO LIVE",
    "24055": "EUROSPORT4K",
    "24608": "ZIKO TV",
    "24609": "TV LIRIA",
    "24610": "TV PRIZREN",
    "24611": "TV DIELLI",
    "24696": "HGTV",
    "25122": "ARENA TENIS HD",
    "25123": "ADRENALIN HD",
    "25170": "HYPE",
    "25171": "HYPE 2",
    "25434": "VIZION PLUS",
    "25438": "MAX HD",
    "25439": "FILM HITS HD",
    "25449": "TRING ACTION",
    "25452": "FILM DRAME",
    "25460": "STAR PLUS TV",
    "25469": "TRING LIFE",
    "25477": "KLAN PLUS",
    "25478": "KLAN TV HD",
    "25498": "GOLD HD",
    "25899": "TRAVEL XP HD",
    "26098": "ТВ ХОРИЗОНТ",
}


# Ein Gast-"Geraet"/eine Session pro Lauf (Modul-weit), NICHT pro
# einzelner Anfrage neu erzeugt - der echte Browser haelt beides fuer
# die komplette Sitzung konstant (siehe magentatv_me_epg.py, wo eine
# staendig wechselnde device-id/session-id die Schedules-API leerlaufen
# liess).
_DEVICE_ID = str(uuid.uuid4())
_SESSION_ID = str(uuid.uuid4())
_sitzung_gestartet = False


def _guest_headers(x_tv_step="EPG_SCHEDULES"):
    """Baut die Header-Menge, mit der die Web-App ihre eigenen
    Gast-Anfragen (kein Login) an das Backend schickt - live per
    Diagnose-Workflow (.github/workflows/diag_magentatv.yml)
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
    Sitzung. Ergebnis wird nicht ausgewertet, Fehler werden ignoriert."""
    global _sitzung_gestartet
    if _sitzung_gestartet:
        return
    _sitzung_gestartet = True
    try:
        params = {"is_sso_enabled": "true", "app_language": "mk", "natco_code": "mk"}
        requests.get(
            "https://tv-mk-prod.yo-digital.com/mk-bifrost/tenant/config", params=params,
            headers=_guest_headers("CONFIG"), timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
    except Exception:
        pass


def _iso_zeit_parsen(text):
    """Parst 'YYYY-MM-DDTHH:MM:SSZ' ODER 'YYYY-MM-DDTHH:MM:SS.ffZ'
    (vorsorglich tolerant, siehe magentatv_me_epg.py, wo der ME-Mandant
    Sekundenbruchteile liefert) zu einem tz-aware datetime (UTC). None
    bei Parse-Fehler."""
    try:
        text = re.sub(r"\.\d+Z$", "Z", text)
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None


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
        "app_language": "mk",
        "natco_code": "mk",
    }
    try:
        response = requests.get(
            BASE_URL, params=params, headers=_guest_headers(), timeout=REQUEST_TIMEOUT_SEKUNDEN
        )
        response.raise_for_status()
        rohdaten = response.json()
        return rohdaten.get("channels", {}) or {}
    except Exception as e:
        print(f"MagentaTV MK: Abruf fuer {datum} +{hour_offset}h fehlgeschlagen ({e}), ueberspringe Fenster.")
        return {}


# Modul-weiter Cache: {station_id: [{"title":..., "beschreibung":...,
# "bild":..., "start":..., "stop":...}, ...]}
_programme_cache = None


def _alle_programme_laden(tage):
    """Laedt (und cached modul-weit) die Sendungen aller bekannten
    Sender fuer die naechsten `tage` Tage, in 3-Stunden-Fenstern.
    Schlaegt ein einzelnes Fenster fehl, wird es einfach uebersprungen -
    kein Grund, den gesamten Lauf abzubrechen."""
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

    print(f"MagentaTV MK: {gesamt_fenster} Zeitfenster abgefragt, {gesamt_sendungen} Sendungen fuer {len(programme)} Sender geladen.")

    _programme_cache = programme
    return _programme_cache


def magentatv_mk_kanal_finden(kanalname):
    """Sucht in der festen STATION_NAMEN-Tabelle nach einem zu
    kanalname passenden Sender. Erst exakter Abgleich nach
    normalisiere_sendername(), dann Kern-Abgleich ohne HD/FHD/UHD/SD.
    Gibt die station_id zurueck oder None."""
    ziel_schluessel = normalisiere_sendername(kanalname)
    if not ziel_schluessel:
        return None

    name_index = {}
    kern_index = {}
    kern_mehrdeutig = set()
    for station_id, name in STATION_NAMEN.items():
        schluessel = normalisiere_sendername(name)
        if schluessel:
            name_index.setdefault(schluessel, station_id)

        kern = normalisiere_sendername_kern(name)
        if kern:
            if kern in kern_index and kern_index[kern] != station_id:
                kern_mehrdeutig.add(kern)
            kern_index.setdefault(kern, station_id)

    if ziel_schluessel in name_index:
        return name_index[ziel_schluessel]

    ziel_kern = normalisiere_sendername_kern(kanalname)
    if ziel_kern and ziel_kern in kern_index and ziel_kern not in kern_mehrdeutig:
        return kern_index[ziel_kern]

    return None


def magentatv_mk_hole_programme(station_id, tage=2):
    """Liefert die Sendungen fuer den gegebenen Sender (station_id) aus
    dem Modul-Cache, begrenzt auf die naechsten `tage` Tage ab heute
    (UTC). Leere Liste bei jedem Fehler oder wenn fuer diesen Sender
    keine Sendungen vorhanden sind."""
    if station_id is None:
        return []

    programme = _alle_programme_laden(tage)
    return programme.get(station_id, [])
