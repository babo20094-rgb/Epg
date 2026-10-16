"""Echte Programmdaten fuer IDJ TV (serbischer Musiksender) von
idjtv.com/tv/guide/ - AUTOMATISCH fuer jeden RS-Sender, dessen Name "IDJ TV"
oder "IDJ MUZIKA 24/7" entspricht (mit HD/VIP/RAW-Zusaetzen). Kein eigenes
Praefix noetig. NICHT "IDJ KIDS" (eigener Sender).

Hintergrund (Oktober 2026): Der Anbieter beschriftet den Kanal "RS| IDJ
MUZIKA 24/7", es ist aber IDJ TV (Nutzer benennt ihn in TiviMate in "RS|
IDJ TV" um). Beide Namen bekommen deshalb dieselben Daten.

Die Seite zeigt statisch (kein Login/JS-API) alle 7 Wochentage als
Tab-Panels (Ponedeljak..Nedelja, in dieser Reihenfolge), je Zeile Uhrzeit
("00:00h") und Titel (in Grossbuchstaben). Nur Uhrzeiten, kein Datum - das
Datum wird aus dem naechsten Vorkommen des Wochentags ab heute berechnet
(rollierende 7-Tage-Vorschau), analog rtvbn_epg.py.

Wird nur EINMAL pro Lauf geladen und geparst (Modul-weiter Cache).
Degradiert an JEDER Stelle graceful auf []/None statt zu werfen - der
betroffene Sender bekommt dann die normale generische EPG-Generierung.
"""

from datetime import datetime, timedelta, timezone

import re

import requests
from quellen import _http, _status
from zoneinfo import ZoneInfo

URL = "https://idjtv.com/tv/guide/"

REQUEST_TIMEOUT_SEKUNDEN = 20

TZ_BELGRADE = ZoneInfo("Europe/Belgrade")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_NAME_PATTERN = re.compile(r"^IDJ\s*(TV|MUZIKA(\s*24\s*/?\s*7)?)\b", re.IGNORECASE)

_PANEL_TRENNER = "<div x-tabs:panel>"
_ZEILE_TRENNER = "rounded-2xl px-3.5"
_ZEIT_PATTERN = re.compile(r"(\d{1,2}):(\d{2})h</div>")
_TITEL_PATTERN = re.compile(r"<h3[^>]*>\s*(?:<a[^>]*>)?([^<]*)", re.DOTALL)

_programme_cache = None


def idjtv_kanal_finden(kanalname):
    """1 (Marker), wenn der Name "IDJ TV"/"IDJ MUZIKA 24/7" entspricht (mit
    beliebigen HD/VIP/RAW-Zusaetzen), sonst None. Matcht NICHT "IDJ KIDS"."""
    name = re.sub(r"\s+", " ", kanalname.strip())
    return 1 if _NAME_PATTERN.match(name) else None


def _naechstes_datum(ziel_wochentag, heute):
    """Naechstes Datum >= heute mit dem gegebenen Wochentag (0=Montag)."""
    return heute + timedelta(days=(ziel_wochentag - heute.weekday()) % 7)


def _titel_bereinigen(titel):
    import html
    return re.sub(r"\s+", " ", html.unescape(titel)).strip()


def _html_parsen(html_text, heute):
    """Parst die Seite zu einer sortierten Liste {"title","beschreibung",
    "bild","start","stop"} (UTC). Reihenfolge der Panels = Montag..Sonntag."""
    i = html_text.find("x-tabs:panels")
    if i == -1:
        return [], 0
    panels = html_text[i:].split(_PANEL_TRENNER)[1:8]
    roh = []
    for wochentag, panel in enumerate(panels):
        datum = _naechstes_datum(wochentag, heute)
        for zeile in panel.split(_ZEILE_TRENNER)[1:]:
            zeit = _ZEIT_PATTERN.search(zeile)
            titel = _TITEL_PATTERN.search(zeile)
            if not zeit or not titel:
                continue
            titel_text = _titel_bereinigen(titel.group(1))
            if not titel_text:
                continue
            start_lokal = datetime(
                datum.year, datum.month, datum.day,
                int(zeit.group(1)), int(zeit.group(2)), tzinfo=TZ_BELGRADE,
            )
            roh.append((start_lokal, titel_text))
    roh.sort(key=lambda e: e[0])
    programme = []
    for k, (start_lokal, titel_text) in enumerate(roh):
        start = start_lokal.astimezone(timezone.utc)
        stop = roh[k + 1][0].astimezone(timezone.utc) if k + 1 < len(roh) else start + timedelta(hours=1)
        if stop <= start:
            continue
        programme.append({
            "title": titel_text, "beschreibung": titel_text, "bild": None,
            "start": start, "stop": stop,
        })
    return programme, len(roh)


def _alle_tage_laden():
    """Laedt (und cached) die Seite. Liefert [] bei jedem Fehler."""
    global _programme_cache

    if _programme_cache is not None:
        return _programme_cache

    try:
        response = _http.mit_retry(requests.get, URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        response.encoding = "utf-8"
        html_text = response.text
        programme, zeilen = _html_parsen(html_text, datetime.now(TZ_BELGRADE).date())
        _status.parser_meldung("idjtv.com", len(html_text), zeilen)
        print(f"IDJ-TV-EPG (idjtv.com): {len(programme)} Sendungen geladen.")
        _programme_cache = programme
        return programme
    except Exception as e:
        print(f"IDJ-TV-EPG (idjtv.com): Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _programme_cache = []
        return []


def idjtv_hole_programme(marker, tage=3):
    """Geladene Programmdaten, begrenzt auf die naechsten `tage` Tage ab
    heute (UTC). Leere Liste bei jedem Fehler."""
    if not marker:
        return []
    eintraege = _alle_tage_laden()
    if not eintraege:
        return []
    heute = datetime.now(timezone.utc).date()
    erlaubt = {heute + timedelta(days=i) for i in range(tage)}
    return [p for p in eintraege if p["start"].date() in erlaubt or p["stop"].date() in erlaubt]
