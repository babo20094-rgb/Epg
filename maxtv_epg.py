"""Optionale, echte Programmdaten von der Max TV Go EPG-API (Nordmazedonien,
Spectar/prd-static-mkt).

Anders als SKY:/MAGENTA:/DAZN:/ARENA:/FREEVIEW:/TVGUIDE: gibt es hier KEIN
eigenes Praefix - dieses Modul wird automatisch fuer JEDEN normal
eingetragenen Sender mit Land "MK" in sender.txt versucht (analog zum
automatischen Telemach-Abgleich fuer BA/ME), weil sender.txt nur ~50
MK-Zeilen enthaelt - ein vertretbares API-Aufrufvolumen. Portiert aus dem
config.js-Site-Plugin "maxtvgo.mk" des iptv-org/epg-Projekts, angepasst auf
requests statt axios/dayjs (keine neuen Abhaengigkeiten). Keine Anmeldung
noetig, rein oeffentliche JSON-API.

Degradiert an JEDER Stelle graceful auf None/[] statt zu werfen: schlaegt
Kanalsuche oder Programmabruf fehl, bekommt der betroffene Sender in
generate_epg.py einfach die normale, kategoriebasierte generische
EPG-Generierung wie jeder andere Sender - dieses Modul darf einen Lauf
niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import difflib

import requests

from epg_lib import normalisiere_sendername

CHANNELS_URL = (
    "https://prd-static-mkt.spectar.tv/rev-1636968171/client_api.php/"
    "channel/all/application_id/deep_blue/device_configuration/2/"
    "instance_id/1/language/mk/http_proto/https/format/json"
)

EPG_URL_TEMPLATE = (
    "https://prd-static-mkt.spectar.tv/rev-1636968171/client_api.php/"
    "epg/list/instance_id/1/language/mk/channel_id/{channel_id}/"
    "start/{start}/stop/{stop}/include_current/true/format/json"
)

REQUEST_TIMEOUT_SEKUNDEN = 20

# Modul-weiter Cache, analog zum Telemach-/mtel-Vorbild - die Kanalliste
# wird pro Lauf nur einmal geholt, egal wie viele MK-Sender es gibt.
_kanalliste_cache = None


def maxtv_hole_kanalliste():
    """Holt (und cached) die komplette Max-TV-Go-Kanalliste als Liste von
    {"site_id":..., "name":...}. Leere Liste bei jedem Fehler (Netzwerk,
    HTTP-Status, unerwartetes JSON)."""
    global _kanalliste_cache

    if _kanalliste_cache is not None:
        return _kanalliste_cache

    try:
        response = requests.get(CHANNELS_URL, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        roh_kanaele = response.json()
        if not isinstance(roh_kanaele, list):
            roh_kanaele = []

        kanaele = []
        for kanal in roh_kanaele:
            if not isinstance(kanal, dict):
                continue
            kanal_id = kanal.get("id")
            name = kanal.get("name")
            if kanal_id is None or not name:
                continue
            kanaele.append({"site_id": kanal_id, "name": name})

        _kanalliste_cache = kanaele
        return kanaele
    except Exception as e:
        print(f"MaxTV-EPG: Kanalliste fehlgeschlagen ({e}), ueberspringe.")
        _kanalliste_cache = []
        return []


def maxtv_kanal_finden(kanalname):
    """Sucht den Max-TV-Go-Kanal, der am besten zu kanalname passt - erst
    exakter Abgleich nach normalisiere_sendername(), sonst unscharfer
    difflib-Abgleich (gleiche Vorgehensweise wie bei Telemach/Sky/...).
    Gibt die site_id zurueck oder None."""
    kanaele = maxtv_hole_kanalliste()
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


def _zeit_parsen(wert):
    """Parst die von der Max-TV-Go-API gelieferten XMLTV-artigen
    Zeitstempel ("YYYYMMDDHHmmss +ZZZZ") zu einem tz-aware UTC-datetime.
    Gibt bei jedem Parse-Fehler None zurueck."""
    if not wert:
        return None
    try:
        zeitpunkt = datetime.strptime(wert.strip(), "%Y%m%d%H%M%S %z")
        return zeitpunkt.astimezone(timezone.utc)
    except Exception:
        return None


def maxtv_hole_programme(site_id, tage=2):
    """Holt Programmdaten fuer den gegebenen Max-TV-Go-Kanal (site_id) fuer
    `tage` aufeinanderfolgende Tage ab heute (UTC). Liefert eine nach
    Startzeit sortierte Liste von {"title", "beschreibung", "bild",
    "start", "stop"} - leere Liste bei jedem Fehler (Netzwerk, HTTP-
    Status, unerwartetes JSON, unparsbare Zeitstempel)."""
    if site_id is None:
        return []

    heute = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    alle_sendungen = []

    for tag_index in range(tage):
        tag = heute + timedelta(days=tag_index)
        von = tag.strftime("%Y%m%d%H%M%S")
        bis = (tag + timedelta(days=1)).strftime("%Y%m%d%H%M%S")

        url = EPG_URL_TEMPLATE.format(channel_id=site_id, start=von, stop=bis)

        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT_SEKUNDEN)
            response.raise_for_status()
            daten = response.json()

            sendungen_roh = daten.get("programme") if isinstance(daten, dict) else None
            if not isinstance(sendungen_roh, list):
                continue

            for sendung in sendungen_roh:
                if not isinstance(sendung, dict):
                    continue
                attribute = sendung.get("@attributes") or {}
                start = _zeit_parsen(attribute.get("start"))
                stop = _zeit_parsen(attribute.get("stop"))
                titel = sendung.get("title")
                if not start or not stop or not titel:
                    continue

                icon = sendung.get("icon") or {}
                icon_attribute = icon.get("@attributes") if isinstance(icon, dict) else None
                bild = icon_attribute.get("src") if isinstance(icon_attribute, dict) else None

                beschreibung = sendung.get("desc")
                if not isinstance(beschreibung, str):
                    beschreibung = ""

                alle_sendungen.append({
                    "title": titel,
                    "beschreibung": beschreibung,
                    "bild": bild,
                    "start": start,
                    "stop": stop,
                })
        except Exception as e:
            print(f"MaxTV-EPG: Programmabruf fuer Kanal {site_id} Tag {tag_index} fehlgeschlagen ({e}), ueberspringe Tag.")
            continue

    alle_sendungen.sort(key=lambda s: s["start"])
    return alle_sendungen
