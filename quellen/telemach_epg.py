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

from epg_lib import (
    kanal_index_suchen,
    kern_index_aufbauen,
    normalisiere_sendername,
)

# Telemach haengt an JEDEN Kanalnamen ein oder mehrere Land-Tags in
# Klammern an (z.B. "TVCG 1 HD (ME)", "TV e (CG)/(BIH)") - reine
# Metadaten (das Land ist ja schon ueber den country-Parameter gewaehlt),
# aber ohne Entfernung landen die Buchstaben nach normalisiere_sendername()
# ungewollt im Vergleichsschluessel (z.B. "HBO HD (ME)" -> "HBOHDME" statt
# "HBOHD") und ein kurzer sender.txt-Name wie "HBO" fällt dadurch sowohl
# beim exakten als auch beim unscharfen Abgleich durch, obwohl der Kanal
# eigentlich existiert (August/September 2026, Montenegro-Sender-Audit).
_LAND_TAG_MUSTER = re.compile(r"\s*\([A-Za-z]{2,4}\)")


def _ohne_land_tag(name):
    return _LAND_TAG_MUSTER.sub("", name or "").strip()


# Der montenegrinische oeffentlich-rechtliche Sender hiess frueher "RTCG"
# (Radio i Televizija Crne Gore) - in der eigenen Playlist/sender.txt noch
# so benannt, bei Telemach aber unter dem neueren Markennamen "TVCG"
# gefuehrt. Bekannte, bestaetigte Umbenennung (kein Fuzzy-Risiko wie beim
# frueheren Sky-Cinema-Special-Fall) - wird nur auf den ZIEL-Namen
# (sender.txt-Seite) angewendet, bevor der Abgleich laeuft.
_RTCG_ALIAS_MUSTER = re.compile(r"^RTV?CG\b", re.IGNORECASE)


def _rtcg_alias(kanalname):
    return _RTCG_ALIAS_MUSTER.sub("TVCG", kanalname or "", count=1)

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
    """Sucht den Telemach-Kanal, der am besten zu kanalname passt - erst
    exakter Abgleich nach normalisiere_sendername(), dann ein Kern-Abgleich
    ohne HD/FHD/UHD/SD, zuletzt unscharfer difflib-Abgleich (siehe
    epg_lib.kanal_index_suchen()). Die von Telemach an jeden Namen
    angehaengten Land-Tags in Klammern (z.B. "(ME)", "(BIH)") werden vor
    dem Vergleich entfernt - sonst verfaelschen sie den Schluessel und
    kurze Namen wie "HBO" finden keinen Treffer mehr, siehe
    _ohne_land_tag(). Gibt die site_id zurueck oder None."""
    kanaele = telemach_hole_kanalliste(country)
    if not kanaele:
        return None

    bereinigt = [
        {"name": _ohne_land_tag(kanal["name"]), "site_id": kanal["site_id"]}
        for kanal in kanaele
    ]

    name_index = {}
    for kanal in bereinigt:
        schluessel = normalisiere_sendername(kanal["name"])
        if schluessel:
            name_index.setdefault(schluessel, kanal["site_id"])

    kern_index = kern_index_aufbauen(bereinigt, "name", "site_id")

    treffer = kanal_index_suchen(kanalname, name_index, kern_index)
    if treffer is None and _RTCG_ALIAS_MUSTER.match((kanalname or "").strip()):
        treffer = kanal_index_suchen(_rtcg_alias(kanalname), name_index, kern_index)
    return treffer


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
