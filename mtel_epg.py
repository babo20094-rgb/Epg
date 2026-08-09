"""Optionale, echte Programmdaten von der Mtel-Bosnien (mtel.ba) EPG-API.

Zweite, nachgelagerte echte EPG-Quelle fuer BA-Sender (nur Bosnien, es
gibt keine Montenegro-Variante) - wird automatisch als Fallback probiert,
wenn die Telemach-Quelle (siehe telemach_epg.py) fuer einen Sender keinen
Kanal-Treffer oder keine Programmdaten liefert. Portiert aus dem
config.js-Site-Plugin "mtel.ba" des iptv-org/epg-Projekts, angepasst auf
requests + zoneinfo statt axios/dayjs (keine neuen Abhaengigkeiten).

Braucht keinen Login (oeffentliche REST-API), ist also einfacher gebaut
als telemach_epg.py. Degradiert an JEDER Stelle graceful auf None/[]
statt zu werfen: schlaegt Kanalsuche oder Programmabruf fehl, bekommt der
betroffene Sender in generate_epg.py einfach die normale, kategorie-
basierte generische EPG-Generierung wie jeder andere Sender - dieses
Modul darf einen Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import difflib

import requests

from epg_lib import normalisiere_sendername

CHANNELS_URL = "https://mtel.ba/hybris/ecommerce/b2c/v1/products/channels/search"
EPG_URL = "https://mtel.ba/hybris/ecommerce/b2c/v1/products/channels/epg"

REQUEST_TIMEOUT_SEKUNDEN = 20

SARAJEVO_TZ = ZoneInfo("Europe/Sarajevo")

_KEIN_INFO_TEXT = "Nema informacija o programu"

# Modul-weiter Cache, analog zu telemach_epg.py - die Kanalliste wird pro
# Plattform nur einmal pro Lauf geholt, auch wenn mehrere BA-Sender ueber
# mtel.ba aufgeloest werden muessen.
_kanalliste_cache = {}


def mtel_hole_kanalliste(platform="iptv"):
    """Holt (und cached pro Plattform) die komplette Mtel-Kanalliste als
    Liste von {"site_id":..., "name":...}. Leere Liste bei jedem Fehler."""
    platform = (platform or "iptv").strip().lower()

    if platform in _kanalliste_cache:
        return _kanalliste_cache[platform]

    kategorie = "tv-msat" if platform == "msat" else "tv-iptv"

    try:
        response = requests.get(
            CHANNELS_URL,
            params={
                "pageSize": 999,
                "query": f":relevantno:tv-kategorija:{kategorie}",
            },
            timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        daten = response.json()

        roh_kanaele = daten.get("products", []) if isinstance(daten, dict) else []

        kanaele = []
        for kanal in roh_kanaele:
            code = kanal.get("code")
            name = kanal.get("name")
            if not code or not name:
                continue
            kanaele.append({"site_id": f"{platform}#{code}", "name": name})

        _kanalliste_cache[platform] = kanaele
        return kanaele
    except Exception as e:
        print(f"Mtel-EPG: Kanalliste ({platform}) fehlgeschlagen ({e}), ueberspringe.")
        _kanalliste_cache[platform] = []
        return []


def mtel_kanal_finden(kanalname, platform="iptv"):
    """Sucht den Mtel-Kanal, der am besten zu kanalname passt - erst
    exakter Abgleich nach normalisiere_sendername(), sonst unscharfer
    difflib-Abgleich (gleiche Vorgehensweise wie telemach_kanal_finden()).
    Gibt die site_id ("<platform>#<code>") zurueck oder None."""
    kanaele = mtel_hole_kanalliste(platform)
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
    """Parst die von der Mtel-API gelieferten lokalen (Europe/Sarajevo),
    naiven Zeitstempel ("YYYY-MM-DD HH:mm") zu einem tz-aware UTC-
    datetime. Gibt bei jedem Parse-Fehler None zurueck."""
    if not wert:
        return None
    try:
        naiv = datetime.strptime(wert, "%Y-%m-%d %H:%M")
        lokal = naiv.replace(tzinfo=SARAJEVO_TZ)
        return lokal.astimezone(timezone.utc)
    except Exception:
        return None


def mtel_hole_programme(site_id, tage=2):
    """Holt Programmdaten fuer den gegebenen Mtel-Kanal (site_id im
    Format "<platform>#<code>") fuer `tage` aufeinanderfolgende Tage ab
    heute (Europe/Sarajevo). Liefert eine nach Startzeit sortierte Liste
    von {"title", "beschreibung", "bild", "start", "stop"} (UTC,
    tz-aware) - leere Liste bei jedem Fehler (Netzwerk, HTTP-Status,
    unerwartetes JSON). Eintraege ohne Programminfo ("Nema informacija o
    programu") werden ausgefiltert."""
    if not site_id or "#" not in site_id:
        return []

    platform, code = site_id.split("#", 1)

    heute = datetime.now(SARAJEVO_TZ).replace(hour=0, minute=0, second=0, microsecond=0)

    alle_sendungen = []

    for tag_index in range(tage):
        tag = heute + timedelta(days=tag_index)

        try:
            response = requests.get(
                EPG_URL,
                params={
                    "platform": f"tv-{platform}",
                    "pageSize": 999,
                    "date": tag.strftime("%Y-%m-%d"),
                },
                timeout=REQUEST_TIMEOUT_SEKUNDEN,
            )
            response.raise_for_status()
            daten = response.json()

            produkte = daten.get("products", []) if isinstance(daten, dict) else []

            kanal_eintrag = None
            for produkt in produkte:
                if produkt.get("code") == code:
                    kanal_eintrag = produkt
                    break

            if not kanal_eintrag:
                continue

            for sendung in kanal_eintrag.get("programs", []) or []:
                titel = sendung.get("title")
                if not titel or _KEIN_INFO_TEXT in titel:
                    continue

                start = _zeit_parsen(sendung.get("start"))
                stop = _zeit_parsen(sendung.get("end"))
                if not start or not stop:
                    continue

                bild_daten = sendung.get("picture") or {}
                bild = bild_daten.get("url") if isinstance(bild_daten, dict) else None

                alle_sendungen.append({
                    "title": titel,
                    "beschreibung": sendung.get("description") or "",
                    "bild": bild,
                    "start": start,
                    "stop": stop,
                })
        except Exception as e:
            print(f"Mtel-EPG: Programmabruf fuer Kanal {site_id} Tag {tag_index} fehlgeschlagen ({e}), ueberspringe Tag.")
            continue

    alle_sendungen.sort(key=lambda s: s["start"])
    return alle_sendungen
