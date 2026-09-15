"""Echte Programmdaten fuer Blagovesti TV (serbischer geistlicher Sender)
von program.blagovesti.tv - AUTOMATISCH fuer jeden BA/RS-Sender, dessen
Name "BLAGOVESTI TV" ODER "BLAGOVIJESTI TV" entspricht (beide
Schreibweisen sind in sender.txt vertreten - dieselbe Playlist-Quelle,
nur unterschiedliche Transliteration; mit oder ohne HD/VIP/RAW-
Zusaetze). Kein eigenes Praefix noetig.

Die Seite hat KEINE einzelne mehrtaegige Uebersicht, sondern sieben
statische Wochentags-Seiten (program.blagovesti.tv/ponedeljak.html ...
nedelja.html, serbische Wochentagsnamen Montag-Sonntag), die jeweils
IMMER die aktuelle Kalenderwoche zeigen (Datum steht im <title>, z.B.
"Blagovesti TV - Utorak 15.09.2026."). Alle sieben Seiten werden pro
Lauf einmal geladen und ueber das eingebettete Datum zu einem
durchgehenden Zeitplan zusammengefuegt - bereits vergangene Wochentage
(fruehere Kalenderwoche) werden beim Zusammenfuegen automatisch verworfen.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt Download oder
Parsen fehl, bekommt der betroffene Sender in generate_epg.py einfach
die normale, kategoriebasierte generische EPG-Generierung wie jeder
andere Sender - dieses Modul darf einen Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import re

import requests
from zoneinfo import ZoneInfo

BASIS_URL = "https://program.blagovesti.tv/{tag}.html"

REQUEST_TIMEOUT_SEKUNDEN = 20

TZ_BELGRADE = ZoneInfo("Europe/Belgrade")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# Montag-Sonntag, serbische Wochentagsnamen wie in den URLs verwendet.
_WOCHENTAGE = ["ponedeljak", "utorak", "sreda", "cetvrtak", "petak", "subota", "nedelja"]

_NAME_PATTERN = re.compile(r"^BLAGOV(?:I?JESTI|ESTI)\s*TV\b", re.IGNORECASE)

_ZEILE_PATTERN = re.compile(
    r'class="time-cell">\s*(\d{1,2}):(\d{2}):(\d{2})\s*</td>\s*'
    r'<td class="show-cell">\s*(.*?)\s*</td>',
    re.DOTALL,
)

_DATUM_PATTERN = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")

# Modul-weiter Cache: die kombinierte, sortierte Sendungsliste (einmal
# pro Lauf berechnet, unabhaengig davon, wie viele "BLAGOVESTI TV"-
# Varianten in sender.txt stehen).
_programme_cache = None


def blagovesti_kanal_finden(kanalname):
    """True (als 1/0-Marker), wenn der Name "BLAGOVESTI TV" entspricht
    (mit beliebigen HD/VIP/RAW-Zusaetzen), sonst None."""
    name = re.sub(r"\s+", " ", kanalname.strip())
    return 1 if _NAME_PATTERN.match(name) else None


def _tag_laden(tag):
    """Laedt und parst eine einzelne Wochentags-Seite. Liefert eine
    Liste von {"start_lokal", "titel"}-Dicts, oder [] bei jedem Fehler."""
    try:
        url = BASIS_URL.format(tag=tag)
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        response.encoding = "utf-8"
        html = response.text

        titel_treffer = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
        if not titel_treffer:
            return []
        datum_treffer = _DATUM_PATTERN.search(titel_treffer.group(1))
        if not datum_treffer:
            return []
        tag_zahl, monat, jahr = (int(t) for t in datum_treffer.groups())

        eintraege = []
        for zeit_std, zeit_min, zeit_sek, titel_html in _ZEILE_PATTERN.findall(html):
            titel = re.sub(r"<[^>]+>", "", titel_html).strip()
            titel = re.sub(r"\s+", " ", titel)
            if not titel:
                continue
            start_lokal = datetime(
                jahr, monat, tag_zahl,
                int(zeit_std), int(zeit_min), int(zeit_sek),
                tzinfo=TZ_BELGRADE,
            )
            eintraege.append({"start_lokal": start_lokal, "titel": titel})

        return eintraege
    except Exception as e:
        print(f"Blagovesti-EPG ({tag}): Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        return []


def _alle_tage_laden():
    """Laedt (und cached) alle sieben Wochentags-Seiten, fuegt sie ueber
    ihr eingebettetes Datum zu einer durchgehenden, sortierten
    Sendungsliste zusammen. Liefert [] bei jedem Fehler."""
    global _programme_cache

    if _programme_cache is not None:
        return _programme_cache

    rohe_eintraege = []
    for tag in _WOCHENTAGE:
        rohe_eintraege.extend(_tag_laden(tag))

    rohe_eintraege.sort(key=lambda e: e["start_lokal"])

    programme = []
    for i, eintrag in enumerate(rohe_eintraege):
        start = eintrag["start_lokal"].astimezone(timezone.utc)
        if i + 1 < len(rohe_eintraege):
            stop = rohe_eintraege[i + 1]["start_lokal"].astimezone(timezone.utc)
        else:
            stop = start + timedelta(hours=1)
        if stop <= start:
            continue
        programme.append({
            "title": eintrag["titel"],
            "beschreibung": eintrag["titel"],
            "bild": None,
            "start": start,
            "stop": stop,
        })

    print(f"Blagovesti-EPG: {len(programme)} Sendungen geladen.")
    _programme_cache = programme
    return programme


def blagovesti_hole_programme(marker, tage=3):
    """Liefert die bereits geladenen Programmdaten, begrenzt auf die
    naechsten `tage` Tage ab heute (UTC). Leere Liste bei jedem Fehler
    oder wenn keine Sendungen vorhanden sind."""
    if not marker:
        return []

    eintraege = _alle_tage_laden()
    if not eintraege:
        return []

    heute = datetime.now(timezone.utc).date()
    erlaubte_tage = {heute + timedelta(days=i) for i in range(tage)}

    return [
        p for p in eintraege
        if p["start"].date() in erlaubte_tage or p["stop"].date() in erlaubte_tage
    ]
