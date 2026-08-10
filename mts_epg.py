"""Automatische, echte Programmdaten von der mts.rs (Serbien) EPG-API.

AUTOMATISCH fuer jeden ganz normal in sender.txt eingetragenen Sender
mit Land "RS" (kein eigenes Praefix noetig, gleiches Prinzip wie der
BA/ME-Telemach-Autoabgleich in generate_epg.py) - bei ~60 RS-Zeilen in
sender.txt ist das Volumen an zusaetzlichen API-Aufrufen pro Lauf
ueberschaubar. Portiert aus dem config.js-Site-Plugin "mts.rs" des
iptv-org/epg-Projekts (Hybris-Ecommerce-Backend, gleiches Muster wie
mtel.ba, siehe mtel_epg.py), angepasst auf requests + zoneinfo statt
axios/dayjs.

Besonderheit: EIN einziger Endpoint liefert pro Datum sowohl die
komplette Kanalliste als auch die Programmdaten ALLER Kanaele auf
einmal (pageSize=10000) - es gibt keinen separaten Kanalliste-Endpoint.
Das Modul cached daher die rohe Tages-Antwort modul-weit pro Datum, so
dass Kanalsuche und Programmabruf sich denselben Request teilen.

Degradiert an JEDER Stelle graceful auf None/[] statt zu werfen:
schlaegt Kanalsuche oder Programmabruf fehl, bekommt der betroffene
Sender in generate_epg.py einfach die normale, kategoriebasierte
generische EPG-Generierung wie jeder andere Sender - dieses Modul darf
einen Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

import difflib

import requests

from epg_lib import normalisiere_sendername

SEARCH_URL = "https://mts.rs/hybris/ecommerce/b2c/v1/products/search"

REQUEST_TIMEOUT_SEKUNDEN = 20

BELGRADE_TZ = ZoneInfo("Europe/Belgrade")

# Modul-weiter Cache der rohen Tages-Antwort (Kanalliste + Programme in
# einem), analog zu telemach_epg.py/mtel_epg.py - pro Datum nur einmal
# geholt, egal wie viele RS-Sender in sender.txt stehen.
_tages_cache = {}


def _hole_tagesdaten(datum):
    """Holt (und cached pro Datum) die rohe mts.rs-Antwort mit Kanal-
    liste + Programmdaten aller Kanaele fuer diesen Tag. Leere Liste an
    "products" bei jedem Fehler."""
    datum_str = datum.strftime("%Y-%m-%d")

    if datum_str in _tages_cache:
        return _tages_cache[datum_str]

    query = (
        f":pozicija-rastuce:tip-kanala-radio:TV kanali:channelProgramDates:{datum_str}"
    )

    try:
        response = requests.get(
            SEARCH_URL,
            params={
                "sort": "pozicija-rastuce",
                "searchQueryContext": "CHANNEL_PROGRAM",
                "query": query,
                "pageSize": 10000,
            },
            timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        daten = response.json()
        produkte = daten.get("products", []) if isinstance(daten, dict) else []
        _tages_cache[datum_str] = produkte
        return produkte
    except Exception as e:
        print(f"Mts-EPG: Tagesdaten ({datum_str}) fehlgeschlagen ({e}), ueberspringe.")
        _tages_cache[datum_str] = []
        return []


def mts_hole_kanalliste():
    """Holt die komplette mts.rs-Kanalliste (Stand: heutiger Tag) als
    Liste von {"site_id":..., "name":...}. Leere Liste bei jedem
    Fehler."""
    heute = datetime.now(BELGRADE_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    produkte = _hole_tagesdaten(heute)

    kanaele = []
    for kanal in produkte:
        code = kanal.get("code")
        name = kanal.get("name")
        if not code or not name:
            continue
        kanaele.append({"site_id": quote(str(code), safe=""), "name": name})
    return kanaele


def mts_kanal_finden(kanalname):
    """Sucht den mts.rs-Kanal, der am besten zu kanalname passt - erst
    exakter Abgleich nach normalisiere_sendername(), sonst unscharfer
    difflib-Abgleich (gleiche Vorgehensweise wie telemach_kanal_finden()).
    Gibt die (URL-encodete) site_id zurueck oder None."""
    kanaele = mts_hole_kanalliste()
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
    """Parst die von der mts.rs-API gelieferten Zeitstempel (ISO-
    aehnlich, ggf. "Z"-Suffix). Zeitzonenlose Werte werden als
    Europe/Belgrade-Lokalzeit interpretiert. Gibt bei jedem Parse-
    Fehler None zurueck."""
    if not wert:
        return None
    try:
        normalisiert = wert.replace("Z", "+00:00")
        zeitpunkt = datetime.fromisoformat(normalisiert)
        if zeitpunkt.tzinfo is None:
            zeitpunkt = zeitpunkt.replace(tzinfo=BELGRADE_TZ)
        return zeitpunkt.astimezone(timezone.utc)
    except Exception:
        return None


def mts_hole_programme(site_id, tage=2):
    """Holt Programmdaten fuer den gegebenen mts.rs-Kanal (site_id,
    URL-encoded code) fuer `tage` aufeinanderfolgende Tage ab heute
    (Europe/Belgrade). Liefert eine nach Startzeit sortierte Liste von
    {"title", "beschreibung", "bild", "start", "stop"} - leere Liste bei
    jedem Fehler (Netzwerk, HTTP-Status, unerwartetes JSON)."""
    if not site_id:
        return []

    heute = datetime.now(BELGRADE_TZ).replace(hour=0, minute=0, second=0, microsecond=0)

    alle_sendungen = []

    for tag_index in range(tage):
        tag = heute + timedelta(days=tag_index)

        try:
            produkte = _hole_tagesdaten(tag)

            kanal_eintrag = None
            for produkt in produkte:
                code = produkt.get("code")
                if code is not None and quote(str(code), safe="") == site_id:
                    kanal_eintrag = produkt
                    break

            if not kanal_eintrag:
                continue

            for sendung in kanal_eintrag.get("programs", []) or []:
                titel = sendung.get("title")
                start = _zeit_parsen(sendung.get("start"))
                stop = _zeit_parsen(sendung.get("end"))
                if not titel or not start or not stop:
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
            print(f"Mts-EPG: Programmabruf fuer Kanal {site_id} Tag {tag_index} fehlgeschlagen ({e}), ueberspringe Tag.")
            continue

    alle_sendungen.sort(key=lambda s: s["start"])
    return alle_sendungen
