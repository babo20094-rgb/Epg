"""Echte Programmdaten fuer ARENA M1/M2/M3 PREMIUM (Nordmazedonien) von
tvarenasport.mk/tv-program/ - AUTOMATISCH fuer MK-Sender, deren Name
"ARENA M1"/"ARENA M2"/"ARENA M3" (mit PREMIUM/FHD/HD/VIP/RAW-Zusaetzen)
entspricht. Kein eigenes Praefix noetig.

Die Seite (statisches HTML, kein Login/JS-API) zeigt je Kanal einen Block
(`tasmk-tvp__ch`, Kanalname im Logo-alt "Арена М1 Премиум") mit einem
Tages-Panel je Tag (`data-tvp-date="YYYY-MM-DD"`, aktuell gestern bis
Sonntag) und je Sendung eine Zeile (Uhrzeit, Sportart, Titel,
Wettbewerb). Zeiten sind lokale mazedonische Zeit (Europe/Skopje).

Grund (Oktober 2026, Nutzeranfrage): MK|ARENA M1 PREMIUM bekam ueber die
Siol-Kaskade slowenische Titel eines anderen Arena-Kanals, M2/M3 nur
"No Data". Siol wird fuer diese Namen deshalb in generate_epg.py
uebersprungen (`arenamk_kanal_finden()`).

Die Seite liefert alles kyrillisch (mazedonisch, Titel in Grossbuchstaben) -
Titel/Sportart/Wettbewerb werden per epg_lib.kyrillisch_zu_latein() in
lateinische Schrift mit normaler Gross-/Kleinschreibung umgewandelt
(Nutzerwunsch Oktober 2026, z. B. "ЛАСК – ЛИВЕРПУЛ" -> "LASK – Liverpul").

Wird nur EINMAL pro Lauf geladen und geparst (Modul-weiter Cache).
Degradiert an JEDER Stelle graceful auf []/None statt zu werfen.
"""

from datetime import datetime, timedelta, timezone

import html
import re

import requests
from quellen import _http, _status
from epg_lib import kyrillisch_zu_latein
from zoneinfo import ZoneInfo

URL = "https://tvarenasport.mk/tv-program/"

REQUEST_TIMEOUT_SEKUNDEN = 20

TZ_SKOPJE = ZoneInfo("Europe/Skopje")

MAX_DAUER = timedelta(hours=3)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_NAME_PATTERN = re.compile(r"^ARENA\s*M\s*([123])\b", re.IGNORECASE)
_KANAL_ALT_PATTERN = re.compile(r"[МM]\s*([123])\b")  # lateinisches oder kyrillisches M

_KANAL_TRENNER = 'class="tasmk-tvp__ch"'
_ALT_PATTERN = re.compile(r'alt="([^"]*)"')
_PANEL_PATTERN = re.compile(r'data-tvp-date="(\d{4}-\d{2}-\d{2})"')
_ZEILE_TRENNER = "tasmk-tvp__row"
_ZEIT_PATTERN = re.compile(r'tasmk-tvp__time">\s*(\d{1,2}):(\d{2})')
_TITEL_PATTERN = re.compile(r'tasmk-tvp__title">([^<]*)')
_SPORT_PATTERN = re.compile(r'tasmk-tvp__sport">([^<]*)')
_COMP_PATTERN = re.compile(r'tasmk-tvp__comp">([^<]*)')

_cache = None


def arenamk_kanal_finden(kanalname):
    """"M1"/"M2"/"M3" (Marker), wenn der Name "ARENA M1/M2/M3 [PREMIUM ...]"
    entspricht, sonst None."""
    name = re.sub(r"\s+", " ", kanalname.strip())
    treffer = _NAME_PATTERN.match(name)
    return f"M{treffer.group(1)}" if treffer else None


def _text(treffer):
    return re.sub(r"\s+", " ", html.unescape(treffer.group(1))).strip() if treffer else ""


def _html_parsen(html_text):
    """-> ({"M1": [Sendungen], ...}, Zeilenzahl). Sendung = {"title",
    "beschreibung", "bild", "start", "stop"} (UTC)."""
    ergebnis = {}
    zeilen_gesamt = 0
    for block in html_text.split(_KANAL_TRENNER)[1:]:
        alt = _ALT_PATTERN.search(block)
        kanal = _KANAL_ALT_PATTERN.search(alt.group(1)) if alt else None
        if not kanal:
            continue
        marker = f"M{kanal.group(1)}"

        roh = []
        paneele = list(_PANEL_PATTERN.finditer(block))
        for i, panel in enumerate(paneele):
            datum = datetime.strptime(panel.group(1), "%Y-%m-%d")
            ende = paneele[i + 1].start() if i + 1 < len(paneele) else len(block)
            vorher = -1
            for zeile in block[panel.end():ende].split(_ZEILE_TRENNER)[1:]:
                zeit = _ZEIT_PATTERN.search(zeile)
                titel = kyrillisch_zu_latein(_text(_TITEL_PATTERN.search(zeile)))
                if not zeit or not titel:
                    continue
                minuten = int(zeit.group(1)) * 60 + int(zeit.group(2))
                tag_versatz = 1 if minuten < vorher else 0  # nach Mitternacht
                vorher = max(vorher, minuten)
                start_lokal = (datum + timedelta(days=tag_versatz, minutes=minuten)).replace(tzinfo=TZ_SKOPJE)
                sport = kyrillisch_zu_latein(_text(_SPORT_PATTERN.search(zeile)))
                wettbewerb = kyrillisch_zu_latein(_text(_COMP_PATTERN.search(zeile)))
                zusatz = " | ".join(t for t in (sport, wettbewerb) if t)
                roh.append((start_lokal, titel, f"{titel}: {zusatz}" if zusatz else titel))

        roh.sort(key=lambda e: e[0])
        zeilen_gesamt += len(roh)
        programme = []
        for k, (start_lokal, titel, beschreibung) in enumerate(roh):
            start = start_lokal.astimezone(timezone.utc)
            # Die Seite listet nur Sport-Events (Luecken dazwischen sind echt
            # leer) - Dauer deshalb auf MAX_DAUER begrenzen, die Luecke fuellt
            # das generische Raster.
            stop = roh[k + 1][0].astimezone(timezone.utc) if k + 1 < len(roh) else start + MAX_DAUER
            stop = min(stop, start + MAX_DAUER)
            if stop <= start:
                continue
            programme.append({
                "title": titel, "beschreibung": beschreibung, "bild": None,
                "start": start, "stop": stop,
            })
        ergebnis[marker] = programme
    return ergebnis, zeilen_gesamt


def _seite_laden():
    """Laedt (und cached) die Seite. Liefert {} bei jedem Fehler."""
    global _cache

    if _cache is not None:
        return _cache

    try:
        response = _http.mit_retry(requests.get, URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        response.encoding = "utf-8"
        ergebnis, zeilen = _html_parsen(response.text)
        _status.parser_meldung("tvarenasport.mk", len(response.text), zeilen)
        print("ArenaMK-EPG (tvarenasport.mk): " + ", ".join(f"{k}: {len(v)}" for k, v in sorted(ergebnis.items())) + " Sendungen geladen.")
        _cache = ergebnis
        return ergebnis
    except Exception as e:
        print(f"ArenaMK-EPG (tvarenasport.mk): Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _cache = {}
        return {}


def arenamk_hole_programme(marker, tage=3):
    """Geladene Programmdaten fuer "M1"/"M2"/"M3", begrenzt auf die naechsten
    `tage` Tage ab heute (UTC). Leere Liste bei jedem Fehler."""
    if not marker:
        return []
    eintraege = _seite_laden().get(marker) or []
    if not eintraege:
        return []
    heute = datetime.now(timezone.utc).date()
    erlaubt = {heute + timedelta(days=i) for i in range(tage)}
    return [p for p in eintraege if p["start"].date() in erlaubt or p["stop"].date() in erlaubt]
