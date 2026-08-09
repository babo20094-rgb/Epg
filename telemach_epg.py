"""Optionale, echte Programmdaten von der Telemach BA/ME EPG-API.

Nur fuer Sender, die per neuem "TELEMACH:"-Praefix in sender.txt
eingetragen wurden (opt-in, kein automatisches Matching gegen alle
bosnischen/montenegrinischen Sender). Portiert aus dem config.js-Site-
Plugin "epg.telemach.ba" des iptv-org/epg-Projekts, angepasst auf
requests statt axios/dayjs (keine neuen Abhaengigkeiten).

Degradiert an JEDER Stelle graceful auf None/[] statt zu werfen: schlaegt
Login, Kanalsuche oder Programmabruf fehl, bekommt der betroffene Sender
in generate_epg.py einfach die normale, kategoriebasierte generische
EPG-Generierung wie jeder andere Sender - dieses Modul darf einen Lauf
niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import difflib
import re

import requests

from epg_lib import normalisiere_sendername

BASIC_TOKEN = (
    "MjdlMTFmNWUtODhlMi00OGU0LWJkNDItOGUxNWFiYmM2NmY1OjEyejJzMXJ3bXdhZmsxMGNkdzl0cjloOWFjYjZwdjJoZDhscXZ0aGc="
)

TOKEN_URL = "https://api-web.ug-be.cdn.united.cloud/oauth/token?grant_type=client_credentials"
CHANNELS_URL = "https://api-web.ug-be.cdn.united.cloud/v1/public/channels"
EPG_URL = "https://api-web.ug-be.cdn.united.cloud/v1/public/events/epg"

REQUEST_TIMEOUT_SEKUNDEN = 20

# communityId/languageId je Land, siehe config.js-Referenz.
_LAND_PARAMETER = {
    "ba": {"communityId": 12, "languageId": 59, "referer": "https://epg.telemach.ba/"},
    "me": {"communityId": 5, "languageId": 10001, "referer": "https://epg.telemach.me/"},
}

# Modul-weiter Cache, analog zum "let session" in der JS-Referenz - Login
# und Kanalliste werden pro Lauf nur einmal geholt, auch wenn mehrere
# TELEMACH:-Sender in sender.txt stehen.
_access_token_cache = None
_kanalliste_cache = {}


def _land_normalisieren(country):
    country = (country or "ba").strip().lower()
    return country if country in _LAND_PARAMETER else "ba"


def telemach_login():
    """Holt (und cached) ein OAuth-Access-Token per Client-Credentials-
    Flow. Gibt bei jedem Fehler (Netzwerk, HTTP-Status, fehlendes Feld
    im JSON) None zurueck, statt zu werfen."""
    global _access_token_cache

    if _access_token_cache:
        return _access_token_cache

    try:
        response = requests.post(
            TOKEN_URL,
            headers={"Authorization": f"Basic {BASIC_TOKEN}"},
            timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        daten = response.json()
        token = daten.get("access_token")
        if not token:
            print("Telemach-EPG: Login-Antwort ohne access_token, ueberspringe.")
            return None
        _access_token_cache = token
        return token
    except Exception as e:
        print(f"Telemach-EPG: Login fehlgeschlagen ({e}), ueberspringe.")
        return None


def telemach_hole_kanalliste(country="ba"):
    """Holt (und cached pro Land) die komplette Telemach-Kanalliste als
    Liste von {"site_id":..., "name":...}. Leere Liste bei jedem Fehler."""
    country = _land_normalisieren(country)

    if country in _kanalliste_cache:
        return _kanalliste_cache[country]

    token = telemach_login()
    if not token:
        return []

    parameter = _LAND_PARAMETER[country]

    try:
        response = requests.get(
            CHANNELS_URL,
            params={
                "channelType": "TV",
                "communityId": parameter["communityId"],
                "languageId": parameter["languageId"],
                "imageSize": "L",
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Referer": parameter["referer"],
            },
            timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        roh_kanaele = response.json()
        if not isinstance(roh_kanaele, list):
            roh_kanaele = roh_kanaele.get("data", []) if isinstance(roh_kanaele, dict) else []

        kanaele = []
        for kanal in roh_kanaele:
            kanal_id = kanal.get("id")
            name = kanal.get("name")
            if kanal_id is None or not name:
                continue
            kanaele.append({"site_id": kanal_id, "name": name})

        _kanalliste_cache[country] = kanaele
        return kanaele
    except Exception as e:
        print(f"Telemach-EPG: Kanalliste ({country}) fehlgeschlagen ({e}), ueberspringe.")
        _kanalliste_cache[country] = []
        return []


def telemach_kanal_finden(kanalname, country="ba"):
    """Sucht den Telemach-Kanal, der am besten zu kanalname passt -
    erst exakter Abgleich nach normalisiere_sendername(), sonst
    unscharfer difflib-Abgleich (gleiche Vorgehensweise wie finde_logo()
    in epg_lib.py). Gibt die site_id zurueck oder None."""
    kanaele = telemach_hole_kanalliste(country)
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
    """Parst die von der Telemach-API gelieferten Zeitstempel (ISO 8601,
    z.B. "2026-08-09T20:00:00+00:00") zu einem tz-aware UTC-datetime.
    Gibt bei jedem Parse-Fehler None zurueck."""
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


def telemach_hole_programme(site_id, country="ba", tage=3):
    """Holt Programmdaten fuer den gegebenen Telemach-Kanal (site_id) fuer
    `tage` aufeinanderfolgende Tage ab heute (UTC). Liefert eine nach
    Startzeit sortierte Liste von {"title", "beschreibung", "bild",
    "start", "stop"} - leere Liste bei jedem Fehler (Netzwerk, HTTP-
    Status, unerwartetes JSON)."""
    country = _land_normalisieren(country)
    token = telemach_login()
    if not token or site_id is None:
        return []

    parameter = _LAND_PARAMETER[country]
    headers = {
        "Authorization": f"Bearer {token}",
        "Referer": parameter["referer"],
    }

    heute = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    alle_sendungen = []

    for tag_index in range(tage):
        tag = heute + timedelta(days=tag_index)
        von = tag.strftime("%Y-%m-%dT%H:%M:%S-00:00")
        bis = (tag + timedelta(days=1) - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S-00:00")

        try:
            response = requests.get(
                EPG_URL,
                params={
                    "fromTime": von,
                    "toTime": bis,
                    "communityId": parameter["communityId"],
                    "languageId": parameter["languageId"],
                    "cid": site_id,
                },
                headers=headers,
                timeout=REQUEST_TIMEOUT_SEKUNDEN,
            )
            response.raise_for_status()
            daten = response.json()

            sendungen_roh = daten.get(str(site_id)) or daten.get(site_id) or []
            if not isinstance(sendungen_roh, list):
                continue

            for sendung in sendungen_roh:
                start = _zeit_parsen(sendung.get("startTime"))
                stop = _zeit_parsen(sendung.get("endTime"))
                titel = sendung.get("title")
                if not start or not stop or not titel:
                    continue

                bilder = sendung.get("images") or []
                bild = bilder[0].get("path") if bilder and isinstance(bilder[0], dict) else None

                alle_sendungen.append({
                    "title": titel,
                    "beschreibung": sendung.get("shortDescription") or "",
                    "bild": bild,
                    "start": start,
                    "stop": stop,
                })
        except Exception as e:
            print(f"Telemach-EPG: Programmabruf fuer Kanal {site_id} Tag {tag_index} fehlgeschlagen ({e}), ueberspringe Tag.")
            continue

    alle_sendungen.sort(key=lambda s: s["start"])
    return alle_sendungen
