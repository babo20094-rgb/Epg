"""Echte Programmdaten fuer Regional Fernsehen Oberbayern (rfo) von
https://www.rfo.de/livestream/ - AUTOMATISCH fuer jeden Sender, dessen
Name "REGIONAL FERNSEHEN OBERBAYERN" (mit HD/VIP/RAW-Zusaetzen)
entspricht. Kein eigenes Praefix noetig.

EINE einzige Seite liefert das komplette 7-Tage-Programm (Oktober 2026:
810 Eintraege) direkt im HTML, eingebettet als JSON-Text mit Titel,
Start-/Endzeit ("HH:MM"), Beschreibung und Datum ("YYYY.MM.DD") je
Sendung - kein Kanalverzeichnis, keine Paginierung, nur EIN Request pro
Lauf. Die Zeichen im eingebetteten JSON sind doppelt escaped
("S\\\\u00fcd"), deshalb wird per Regex statt als JSON geparst und
anschliessend zweistufig dekodiert (siehe _dekodieren()).

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt Download oder
Parsen fehl, bekommt der betroffene Sender in generate_epg.py einfach
die normale, kategoriebasierte generische EPG-Generierung wie jeder
andere Sender - dieses Modul darf einen Lauf niemals zum Absturz
bringen.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import html
import re

import requests
from quellen import _http

from epg_lib import normalisiere_sendername_kern

URL = "https://www.rfo.de/livestream/"

REQUEST_TIMEOUT_SEKUNDEN = 30

BERLIN_TZ = ZoneInfo("Europe/Berlin")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_WHITELIST = {normalisiere_sendername_kern("Regional Fernsehen Oberbayern")}

# Zeichenketten-Inhalt = beliebig viele "kein Anfuehrungszeichen/Backslash"
# oder "Backslash + beliebiges Zeichen"-Paare, damit ein Treffer nie ueber
# das Ende eines JSON-Strings hinauslaeuft (ein naives ".*?" verschluckte
# sonst den Text vorheriger Objekte als Titel).
_STR = r'((?:[^"\\]|\\.)*)'
_EINTRAG_RE = re.compile(
    r'\{"title":"' + _STR + r'","from":"(\d{1,2}):(\d{2})","to":"(\d{1,2}):(\d{2})",'
    r'"description":"' + _STR + r'","date":"(\d{4})\.(\d{2})\.(\d{2})"'
)

_programme_cache = None


def rfo_kanal_treffer(sendername):
    """Nur ein exakter Abgleich gegen die enge Whitelist oben (True/
    False) - kein Netzwerk-Request, reiner Namensvergleich."""
    schluessel = normalisiere_sendername_kern(sendername)
    return bool(schluessel) and schluessel in _WHITELIST


def _dekodieren(text):
    """Dekodiert die doppelt escapten JSON-Strings ("\\\\u00fc" -> "ue"
    usw.) und HTML-Entities, normalisiert Leerzeichen."""
    text = (text or "").replace("\\\\/", "/").replace("\\/", "/")
    text = re.sub(r"\\\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    text = text.replace('\\\\"', '"').replace('\\"', '"')
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _seite_laden():
    """Laedt (und cached) die komplette Seite, geparst zu einer nach
    Startzeit sortierten Liste von {"title", "beschreibung", "start",
    "stop"} (tz-aware Europe/Berlin). Leere Liste bei jedem Fehler."""
    global _programme_cache

    if _programme_cache is not None:
        return _programme_cache

    try:
        response = _http.mit_retry(requests.get, URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        text = response.text

        eintraege = {}
        for titel_roh, sh, sm, eh, em, beschr_roh, jahr, monat, tag in _EINTRAG_RE.findall(text):
            titel = _dekodieren(titel_roh)
            if not titel:
                continue
            try:
                start = datetime(int(jahr), int(monat), int(tag), int(sh), int(sm), tzinfo=BERLIN_TZ)
                stop = datetime(int(jahr), int(monat), int(tag), int(eh), int(em), tzinfo=BERLIN_TZ)
            except ValueError:
                continue
            if stop <= start:
                stop += timedelta(days=1)  # Sendung ueber Mitternacht (z.B. 23:45 - 00:00)
            # Dieselbe Sendung steht im HTML mehrfach (Listenansicht +
            # Tagesansicht) - ueber den Startzeitpunkt deduplizieren.
            eintraege.setdefault(start, {
                "title": titel,
                "beschreibung": _dekodieren(beschr_roh),
                "start": start,
                "stop": stop,
            })

        ergebnis = sorted(eintraege.values(), key=lambda e: e["start"])
        _programme_cache = ergebnis
        return ergebnis
    except Exception as e:
        print(f"RFO-EPG: Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _programme_cache = []
        return []


def rfo_hole_programme(tage=7):
    """Liefert Programmdaten fuer Regional Fernsehen Oberbayern fuer
    `tage` Tage ab heute (Europe/Berlin). Leere Liste bei jedem Fehler."""
    roh = _seite_laden()
    if not roh:
        return []

    heute = datetime.now(BERLIN_TZ).date()
    grenze = heute + timedelta(days=tage)

    ergebnis = []
    for eintrag in roh:
        if not (heute <= eintrag["start"].date() < grenze):
            continue
        ergebnis.append({
            "title": eintrag["title"],
            "beschreibung": eintrag["beschreibung"],
            "bild": None,
            # Nach UTC konvertieren - generate_epg.py haengt beim
            # Schreiben nur "+0000" an die Uhrzeit an, statt sie
            # umzurechnen (siehe rtvslon_epg.py/docs/HISTORIE.md).
            "start": eintrag["start"].astimezone(ZoneInfo("UTC")),
            "stop": eintrag["stop"].astimezone(ZoneInfo("UTC")),
        })

    return ergebnis
