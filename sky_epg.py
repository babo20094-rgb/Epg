"""Optionale, echte Programmdaten von der Sky-Deutschland-EPG-API (HAWK).

Im Gegensatz zu Telemach/mtel.ba (siehe telemach_epg.py, mtel_epg.py) ist
diese Quelle AUSSCHLIESSLICH opt-in ueber das neue "SKY:"-Praefix in
sender.txt - es gibt hier bewusst KEIN automatisches Matching gegen alle
Sender mit Land "DE" (zu viele DE-Zeilen in sender.txt, das waeren zu
viele API-Aufrufe pro Lauf und ein zu hohes Risiko fuer Fehltreffer).

Portiert aus dem config.js-Site-Plugin "sky.com" des iptv-org/epg-
Projekts, aber deutlich im Umfang reduziert: nur die HAWK-API (nicht-UHD-
Kanaele) und nur das Territory "DE" werden unterstuetzt - die Atlantis-
API (fuer UHD-Kanaele, braucht zusaetzliche Header + eine lokale
channels.xml-Lookup-Tabelle, die wir nicht haben) und die anderen
Territories (GB/IT) wurden komplett weggelassen. Aus Einfachheit wird pro
Sender/Tag ein eigener Schedule-Request gemacht (kein Batching mehrerer
sids ueber die lokale XML-Datei wie im Original).

Braucht keinen Login (oeffentliche REST-API), nur den Header
"X-SkyOTT-Territory: DE" auf jedem Request. Degradiert an JEDER Stelle
graceful auf None/[] statt zu werfen: schlaegt Kanalsuche oder
Programmabruf fehl, bekommt der betroffene Sender in generate_epg.py
einfach die normale, kategoriebasierte generische EPG-Generierung wie
jeder andere Sender - dieses Modul darf einen Lauf niemals zum Absturz
bringen.
"""

from datetime import datetime, timedelta, timezone

import difflib

import requests

from epg_lib import normalisiere_sendername

HAWK_API_ENDPOINT = "https://awk.epgsky.com/hawk/linear"

REQUEST_TIMEOUT_SEKUNDEN = 20

# Modul-weiter Cache, analog zu telemach_epg.py/mtel_epg.py - die
# Kanalliste wird pro Territory nur einmal pro Lauf geholt, auch wenn
# mehrere SKY:-Sender in sender.txt stehen.
_kanalliste_cache = {}


def _territory_normalisieren(territory):
    """Es wird nur "DE" unterstuetzt (kein GB/IT-Port) - jeder andere
    Wert faellt still auf "DE" zurueck."""
    territory = (territory or "DE").strip().upper()
    return territory if territory == "DE" else "DE"


def sky_hole_kanalliste(territory="DE"):
    """Holt (und cached pro Territory) die komplette Sky-Kanalliste
    (nur HAWK/nicht-UHD, siehe Modul-Docstring) als Liste von
    {"site_id":..., "name":...}. Leere Liste bei jedem Fehler."""
    territory = _territory_normalisieren(territory)

    if territory in _kanalliste_cache:
        return _kanalliste_cache[territory]

    headers = {"X-SkyOTT-Territory": territory}

    try:
        regions_response = requests.get(
            f"{HAWK_API_ENDPOINT}/regions",
            headers=headers,
            timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        regions_response.raise_for_status()
        regions_daten = regions_response.json()
        regionen = regions_daten.get("regions", []) if isinstance(regions_daten, dict) else []

        kanaele = []
        gesehene_sids = set()

        for region in regionen:
            bouquet_id = region.get("bouquetId")
            sub_bouquet_id = region.get("subBouquetId")
            if bouquet_id is None or sub_bouquet_id is None:
                continue

            try:
                services_response = requests.get(
                    f"{HAWK_API_ENDPOINT}/services/{bouquet_id}/{sub_bouquet_id}",
                    headers=headers,
                    timeout=REQUEST_TIMEOUT_SEKUNDEN,
                )
                services_response.raise_for_status()
                services_daten = services_response.json()
                services = services_daten.get("services", []) if isinstance(services_daten, dict) else []

                for service in services:
                    sid = service.get("sid")
                    name = service.get("t")
                    if sid is None or not name or sid in gesehene_sids:
                        continue
                    gesehene_sids.add(sid)
                    kanaele.append({"site_id": sid, "name": name})
            except Exception as e:
                print(f"Sky-EPG: Services fuer Region {bouquet_id}/{sub_bouquet_id} fehlgeschlagen ({e}), ueberspringe Region.")
                continue

        _kanalliste_cache[territory] = kanaele
        return kanaele
    except Exception as e:
        print(f"Sky-EPG: Kanalliste ({territory}) fehlgeschlagen ({e}), ueberspringe.")
        _kanalliste_cache[territory] = []
        return []


def sky_kanal_finden(kanalname, territory="DE"):
    """Sucht den Sky-Kanal, der am besten zu kanalname passt - erst
    exakter Abgleich nach normalisiere_sendername(), sonst unscharfer
    difflib-Abgleich (gleiche Vorgehensweise wie telemach_kanal_finden()/
    mtel_kanal_finden()). Gibt die site_id (sid) zurueck oder None."""
    kanaele = sky_hole_kanalliste(territory)
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


def sky_hole_programme(site_id, territory="DE", tage=2):
    """Holt Programmdaten fuer den gegebenen Sky-Kanal (sid) fuer `tage`
    aufeinanderfolgende Tage ab heute (UTC, entspricht dem "days: 2" im
    Original). Liefert eine nach Startzeit sortierte Liste von {"title",
    "beschreibung", "bild", "start", "stop"} (UTC, tz-aware) - leere
    Liste bei jedem Fehler (Netzwerk, HTTP-Status, unerwartetes JSON)."""
    if site_id is None:
        return []

    territory = _territory_normalisieren(territory)
    headers = {"X-SkyOTT-Territory": territory}

    heute = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    alle_sendungen = []
    gesehene_eids = set()

    for tag_index in range(tage):
        tag = heute + timedelta(days=tag_index)

        try:
            response = requests.get(
                f"{HAWK_API_ENDPOINT}/schedule/{tag.strftime('%Y%m%d')}/{site_id}",
                headers=headers,
                timeout=REQUEST_TIMEOUT_SEKUNDEN,
            )
            response.raise_for_status()
            daten = response.json()

            schedule = daten.get("schedule", []) if isinstance(daten, dict) else []

            kanal_eintrag = None
            for eintrag in schedule:
                if eintrag.get("sid") == site_id:
                    kanal_eintrag = eintrag
                    break

            if not kanal_eintrag:
                continue

            for event in kanal_eintrag.get("events", []) or []:
                eid = event.get("eid")
                if eid is not None and eid in gesehene_eids:
                    continue

                start_unix = event.get("st")
                dauer_sekunden = event.get("d")
                titel = event.get("t")
                if start_unix is None or dauer_sekunden is None or not titel:
                    continue

                start = datetime.fromtimestamp(start_unix, tz=timezone.utc)
                stop = start + timedelta(seconds=dauer_sekunden)

                programmuuid = event.get("programmeuuid")
                bild = (
                    f"https://images.metadata.sky.com/pd-image/{programmuuid}/16-9/640"
                    if programmuuid else None
                )

                if eid is not None:
                    gesehene_eids.add(eid)

                alle_sendungen.append({
                    "title": titel,
                    "beschreibung": event.get("sy") or "",
                    "bild": bild,
                    "start": start,
                    "stop": stop,
                })
        except Exception as e:
            print(f"Sky-EPG: Programmabruf fuer Kanal {site_id} Tag {tag_index} fehlgeschlagen ({e}), ueberspringe Tag.")
            continue

    alle_sendungen.sort(key=lambda s: s["start"])
    return alle_sendungen
