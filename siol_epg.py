"""Automatische, echte Programmdaten von tv-spored.siol.net (Slowenien).

AUTOMATISCH fuer jeden ganz normal in sender.txt eingetragenen Sender
mit Land "SI" (kein eigenes Praefix noetig, gleiches Prinzip wie der
BA/ME-Telemach-Autoabgleich in generate_epg.py) - bei nur ~2 SI-Zeilen
in sender.txt ist das Volumen an zusaetzlichen Abrufen pro Lauf
minimal. Portiert aus dem config.js-Site-Plugin "tv-spored.siol.net"
des iptv-org/epg-Projekts.

WICHTIGE EINSCHRAENKUNG: tv-spored.siol.net liefert keine stabile JSON-
API, sondern rendert eine Next.js-Seite, deren Daten in <script>-Tags
als serialisierte "self.__next_f.push([1, "<key>:<json>"])"-Aufrufe
eingebettet sind. Das Original wertet dafuer das komplette Skript per
`new Function` als echtes JavaScript aus - das wird hier bewusst NICHT
nachgebaut (kein eval von Fremdcode in Python). Stattdessen wird der
Text der <script>-Tags per Regex nach den push()-Aufrufen durchsucht,
der gepushte String als JSON-String-Literal dekodiert, ein fuehrendes
"<Zahl>:"-Praefix abgetrennt und der Rest als JSON geparst; die
entstehende verschachtelte Struktur wird rekursiv nach einem
bestimmten Schluessel durchsucht ("channelsAsJson" fuer Programme,
"tvChannelsAsJson" fuer die Kanalliste). Dieser Ansatz ist von Natur
aus SEHR anfaellig fuer Aenderungen am Seiten-/Build-Layout von
tv-spored.siol.net (anders als bei den JSON-API-Quellen dieses Repos,
z.B. mts_epg.py oder mojmaxtv_epg.py) - schlaegt die Extraktion an
irgendeiner Stelle fehl, wird das konsequent und leise mit [] beant-
wortet statt mit einer Exception, und generate_epg.py faellt fuer den
betroffenen Sender auf die normale, kategoriebasierte generische EPG-
Generierung zurueck. Dieses Modul darf einen Lauf niemals zum Absturz
bringen.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import difflib
import json
import re

import requests
from bs4 import BeautifulSoup

from epg_lib import normalisiere_sendername

BASE_URL = "https://tv-spored.siol.net"

REQUEST_TIMEOUT_SEKUNDEN = 20

LJUBLJANA_TZ = ZoneInfo("Europe/Ljubljana")

_PUSH_PATTERN = re.compile(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)')
_PRAEFIX_PATTERN = re.compile(r'^\d+:')

# Modul-weiter Cache, analog zu telemach_epg.py.
_kanalliste_cache = None
_programm_cache = {}


def _finde_schluessel(struktur, gesuchter_schluessel):
    """Durchsucht eine beliebig verschachtelte dict/list-Struktur
    rekursiv nach dem ersten Vorkommen von `gesuchter_schluessel` als
    dict-Schluessel und gibt dessen Wert zurueck. None, wenn nichts
    gefunden wird."""
    if isinstance(struktur, dict):
        if gesuchter_schluessel in struktur:
            return struktur[gesuchter_schluessel]
        for wert in struktur.values():
            treffer = _finde_schluessel(wert, gesuchter_schluessel)
            if treffer is not None:
                return treffer
    elif isinstance(struktur, list):
        for element in struktur:
            treffer = _finde_schluessel(element, gesuchter_schluessel)
            if treffer is not None:
                return treffer
    return None


def _extrahiere_schluessel_aus_html(html_text, gesuchter_schluessel):
    """Sucht in allen <script>-Tags einer Seite nach
    self.__next_f.push([1, "..."])-Aufrufen, dekodiert deren Inhalt und
    sucht darin rekursiv nach `gesuchter_schluessel`. Gibt den
    gefundenen Wert zurueck oder None - niemals eine Exception, jeder
    Parse-Fehler an einer einzelnen Stelle wird einfach uebersprungen
    (die Seite besteht aus vielen solcher Chunks, nur einer davon
    enthaelt normalerweise den gesuchten Schluessel)."""
    try:
        soup = BeautifulSoup(html_text, "html.parser")
    except Exception:
        return None

    for script in soup.find_all("script"):
        text = script.string or script.get_text() or ""
        if not text or "self.__next_f.push" not in text:
            continue

        for match in _PUSH_PATTERN.finditer(text):
            roh = match.group(1)
            try:
                dekodiert = json.loads('"' + roh + '"')
            except Exception:
                continue

            ohne_praefix = _PRAEFIX_PATTERN.sub("", dekodiert, count=1)

            try:
                struktur = json.loads(ohne_praefix)
            except Exception:
                continue

            treffer = _finde_schluessel(struktur, gesuchter_schluessel)
            if treffer is not None:
                return treffer

    return None


def siol_hole_kanalliste():
    """Holt (und cached) die komplette siol.net-Kanalliste (per HTML-
    Scraping der Startseite) als Liste von {"site_id":..., "name":...}.
    Leere Liste bei jedem Fehler (Netzwerk, unerwartete Seitenstruktur)."""
    global _kanalliste_cache

    if _kanalliste_cache is not None:
        return _kanalliste_cache

    try:
        response = requests.get(BASE_URL, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()

        roh_kanaele = _extrahiere_schluessel_aus_html(response.text, "tvChannelsAsJson")
        if not isinstance(roh_kanaele, list):
            print("Siol-EPG: Kanalliste nicht gefunden/unerwartete Struktur, ueberspringe.")
            _kanalliste_cache = []
            return []

        kanaele = []
        for kanal in roh_kanaele:
            if not isinstance(kanal, dict):
                continue
            name = kanal.get("name")
            external_id = kanal.get("externalId")
            if not name or not external_id:
                continue
            kanaele.append({"site_id": str(external_id).lower(), "name": name})

        _kanalliste_cache = kanaele
        return kanaele
    except Exception as e:
        print(f"Siol-EPG: Kanalliste fehlgeschlagen ({e}), ueberspringe.")
        _kanalliste_cache = []
        return []


def siol_kanal_finden(kanalname):
    """Sucht den siol.net-Kanal, der am besten zu kanalname passt -
    erst exakter Abgleich nach normalisiere_sendername(), sonst
    unscharfer difflib-Abgleich. Gibt die site_id zurueck oder None."""
    kanaele = siol_hole_kanalliste()
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
    """Parst die von siol.net gelieferten Zeitstempel (ISO 8601, ggf.
    zeitzonenlos -> dann Europe/Ljubljana angenommen) zu einem
    tz-aware UTC-datetime. Gibt bei jedem Parse-Fehler None zurueck."""
    if not wert:
        return None
    try:
        normalisiert = wert.replace("Z", "+00:00")
        zeitpunkt = datetime.fromisoformat(normalisiert)
        if zeitpunkt.tzinfo is None:
            zeitpunkt = zeitpunkt.replace(tzinfo=LJUBLJANA_TZ)
        return zeitpunkt.astimezone(timezone.utc)
    except Exception:
        return None


def _hole_events_fuer_kanal_und_tag(site_id, datum):
    """Holt (und cached pro Kanal+Datum) die Event-Liste fuer einen
    Kanal/Tag per HTML-Scraping. Leere Liste bei jedem Fehler."""
    datum_str = datum.strftime("%Y%m%d")
    cache_key = (site_id, datum_str)

    if cache_key in _programm_cache:
        return _programm_cache[cache_key]

    url = f"{BASE_URL}/kanal/{site_id}/datum/{datum_str}"

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()

        roh_kanaele = _extrahiere_schluessel_aus_html(response.text, "channelsAsJson")
        if not isinstance(roh_kanaele, list) or not roh_kanaele:
            _programm_cache[cache_key] = []
            return []

        erster = roh_kanaele[0]
        events = erster.get("events") if isinstance(erster, dict) else None
        if not isinstance(events, list):
            events = []

        _programm_cache[cache_key] = events
        return events
    except Exception as e:
        print(f"Siol-EPG: Programmabruf fuer Kanal {site_id} ({datum_str}) fehlgeschlagen ({e}), ueberspringe Tag.")
        _programm_cache[cache_key] = []
        return []


def siol_hole_programme(site_id, tage=2):
    """Holt Programmdaten fuer den gegebenen siol.net-Kanal (site_id)
    fuer `tage` aufeinanderfolgende Tage ab heute (Europe/Ljubljana).
    Liefert eine nach Startzeit sortierte Liste von {"title",
    "beschreibung", "bild", "start", "stop"} - leere Liste bei jedem
    Fehler (Netzwerk, HTTP-Status, unerwartete/fehlende Seitenstruktur)."""
    if not site_id:
        return []

    heute = datetime.now(LJUBLJANA_TZ).replace(hour=0, minute=0, second=0, microsecond=0)

    alle_sendungen = []

    for tag_index in range(tage):
        tag = heute + timedelta(days=tag_index)

        try:
            events = _hole_events_fuer_kanal_und_tag(site_id, tag)

            for event in events:
                if not isinstance(event, dict):
                    continue
                titel = event.get("title")
                start = _zeit_parsen(event.get("startDateTime"))
                stop = _zeit_parsen(event.get("stopDateTime"))
                if not titel or not start or not stop:
                    continue

                alle_sendungen.append({
                    "title": titel,
                    "beschreibung": event.get("category") or "",
                    "bild": None,
                    "start": start,
                    "stop": stop,
                })
        except Exception as e:
            print(f"Siol-EPG: Verarbeitung fuer Kanal {site_id} Tag {tag_index} fehlgeschlagen ({e}), ueberspringe Tag.")
            continue

    alle_sendungen.sort(key=lambda s: s["start"])
    return alle_sendungen
