"""Optionale, echte Programmdaten von tvmovie.de (Deutschland) - opt-in
ueber das explizite Praefix `TVMOVIE:<Kanalname wie bei tvmovie.de>|
<Logo-URL>`, siehe Parsing-Kommentar in generate_epg.py.

HTML-Scraping der Sender-Tagesseite (`https://www.tvmovie.de/tv/sender-
<slug>`, KEIN Datumsparameter mehr moeglich - das alte WebGrab+Plus-
Site-Plugin nutzte noch `?date=...&type=day`, das liefert nach einem
Website-Redesign inzwischen 404). Die Seite selbst deckt daher praktisch
nur den aktuellen Tag ab (`TVMOVIE_TAGE` sollte auf 1 bleiben) und laedt
laut Beobachtung eines Snapshots offenbar nur einen Teil des Tages
serverseitig aus (~05:00-20:00 Uhr, vermutlich laedt der Rest per
Nachladen/Scrollen via JavaScript nach) - ein reiner Server-Abruf ohne
Browser/JS liefert daher womoeglich nur einen Ausschnitt des Tages statt
des kompletten 24h-Programms. Trotzdem besser als die generische
Kategorie-Beschreibung, wo tvmovie.de tatsaechlich Daten liefert.

Die Kanalsuche nutzt eine im Repo mitgelieferte statische Datei
(`tvmovie_kanalliste.txt`, ~180 Eintraege, aus der Original-Kanalliste
des WebGrab+Plus-Plugins extrahiert, Zeilenformat "<slug>|<Name>") -
kein Netzwerk-Request fuer die Kanalsuche selbst, nur der eigentliche
Programmabruf fuer tatsaechlich getroffene Kanaele geht live. Da hier
HTML statt einer stabilen JSON-API geparst wird, ist diese Quelle
prinzipiell anfaelliger fuer Breaking Changes bei einem weiteren
Website-Redesign - degradiert aber nach derselben Zero-Risk-Garantie an
JEDER Stelle graceful auf None/[]/leere Ergebnisse statt zu werfen:
schlaegt Kanalsuche oder Programmabruf fehl, bekommt der betroffene
Sender in generate_epg.py einfach die normale, kategoriebasierte
generische EPG-Generierung wie jeder andere Sender - dieses Modul darf
einen Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import difflib
import os
import re

import requests
from bs4 import BeautifulSoup

from epg_lib import normalisiere_sendername

BASE_URL = "https://www.tvmovie.de/tv/sender-{slug}"

REQUEST_TIMEOUT_SEKUNDEN = 20

BERLIN_TZ = ZoneInfo("Europe/Berlin")

KANALLISTE_DATEI = os.path.join(os.path.dirname(__file__), "tvmovie_kanalliste.txt")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_kanalliste_cache = None
_seite_cache = {}

_ZEIT_MUSTER = re.compile(r"^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})$")
_DATUM_MUSTER = re.compile(r"(\d{1,2})\.(\d{1,2})\.")


def tvmovie_hole_kanalliste():
    """Laedt (und cached) die statische Kanalliste aus
    tvmovie_kanalliste.txt als Liste von {"site_id":..., "name":...}.
    Leere Liste bei jedem Fehler (Datei fehlt, unlesbar, leer)."""
    global _kanalliste_cache

    if _kanalliste_cache is not None:
        return _kanalliste_cache

    try:
        kanaele = []
        with open(KANALLISTE_DATEI, encoding="utf-8") as f:
            for zeile in f:
                zeile = zeile.strip()
                if not zeile or "|" not in zeile:
                    continue
                site_id, name = zeile.split("|", 1)
                if not site_id.strip() or not name.strip():
                    continue
                kanaele.append({"site_id": site_id.strip(), "name": name.strip()})
        _kanalliste_cache = kanaele
        return kanaele
    except Exception as e:
        print(f"TvMovie-EPG: Kanalliste konnte nicht gelesen werden ({e}), ueberspringe.")
        _kanalliste_cache = []
        return []


def tvmovie_kanal_finden(kanalname):
    """Sucht den tvmovie.de-Kanal, der am besten zu kanalname passt -
    erst exakter Abgleich nach normalisiere_sendername(), sonst
    unscharfer difflib-Abgleich. Gibt den Slug (site_id) zurueck oder
    None."""
    kanaele = tvmovie_hole_kanalliste()
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


def _seite_holen(slug):
    """Holt (und cached pro Kanal/Lauf) die rohe HTML-Seite als Text.
    Gibt bei jedem Fehler None zurueck."""
    if slug in _seite_cache:
        return _seite_cache[slug]

    try:
        response = requests.get(
            BASE_URL.format(slug=slug), headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        _seite_cache[slug] = response.text
        return response.text
    except Exception as e:
        print(f"TvMovie-EPG: Seitenabruf ({slug}) fehlgeschlagen ({e}), ueberspringe.")
        _seite_cache[slug] = None
        return None


def _datum_ableiten(tag, monat):
    """Leitet aus einem reinen Tag/Monat (ohne Jahr, wie von tvmovie.de
    geliefert) das passende Datum ab - nimmt das aktuelle Jahr, oder das
    naechste, falls das Datum sonst mehr als 3 Tage in der Vergangenheit
    laege (Jahreswechsel-Randfall)."""
    heute = datetime.now(BERLIN_TZ).date()
    jahr = heute.year
    try:
        kandidat = datetime(jahr, monat, tag).date()
    except ValueError:
        return None
    if kandidat < heute - timedelta(days=3):
        try:
            kandidat = datetime(jahr + 1, monat, tag).date()
        except ValueError:
            return None
    return kandidat


def _sendung_parsen(anker):
    titel = (anker.get("aria-label") or "").strip()
    if not titel:
        return None

    spans = anker.find_all("span")
    zeit_span = None
    datum_span = None
    genre_teile = []
    for span in spans:
        text = span.get_text(strip=True)
        if zeit_span is None and _ZEIT_MUSTER.match(text):
            zeit_span = text
            continue
        if datum_span is None and _DATUM_MUSTER.search(text):
            datum_span = text
            continue
        if zeit_span is None and text:
            genre_teile.append(text)

    if not zeit_span or not datum_span:
        return None

    zeit_match = _ZEIT_MUSTER.match(zeit_span)
    datum_match = _DATUM_MUSTER.search(datum_span)
    if not zeit_match or not datum_match:
        return None

    start_h, start_m, stop_h, stop_m = (int(g) for g in zeit_match.groups())
    tag, monat = int(datum_match.group(1)), int(datum_match.group(2))

    datum = _datum_ableiten(tag, monat)
    if datum is None:
        return None

    try:
        start = datetime(datum.year, datum.month, datum.day, start_h, start_m, tzinfo=BERLIN_TZ)
        stop = datetime(datum.year, datum.month, datum.day, stop_h, stop_m, tzinfo=BERLIN_TZ)
        if stop <= start:
            stop += timedelta(days=1)
    except Exception:
        return None

    return {
        "title": titel,
        "beschreibung": " / ".join(genre_teile),
        "bild": None,
        "start": start,
        "stop": stop,
    }


def _seite_parsen(html):
    soup = BeautifulSoup(html, "html.parser")

    ergebnis = []
    for anker in soup.select("a.bx-epg-broadcast"):
        sendung = _sendung_parsen(anker)
        if sendung is not None:
            ergebnis.append(sendung)

    ergebnis.sort(key=lambda s: s["start"])
    return ergebnis


def tvmovie_hole_programme(slug, tage=1):
    """Holt Programmdaten fuer den gegebenen tvmovie.de-Kanal (slug).
    `tage` wird ignoriert, wenn > 1 - die Seite unterstuetzt keinen
    Datumsparameter mehr, es gibt nur den aktuellen Tag (evtl. nur
    teilweise, siehe Moduldocstring). Liefert eine nach Startzeit
    sortierte Liste von {"title", "beschreibung", "bild", "start",
    "stop"} (tz-aware) - leere Liste bei jedem Fehler (Netzwerk,
    HTTP-Status, unerwartete HTML-Struktur)."""
    if not slug:
        return []

    html = _seite_holen(slug)
    if html is None:
        return []

    try:
        return _seite_parsen(html)
    except Exception as e:
        print(f"TvMovie-EPG: Parsen fuer Kanal {slug} fehlgeschlagen ({e}), ueberspringe.")
        return []
