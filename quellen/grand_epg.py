"""Echte Programmdaten fuer den serbischen Sender Grand TV von
grand.rs/tv-program/ - AUTOMATISCH fuer jeden RS-Sender, dessen Name
"GRAND TV" entspricht (mit HD/VIP/RAW-Zusaetzen). Kein eigenes Praefix
noetig. Matcht NICHT "Grand 1"/"Grand 2" (andere, eigenstaendige
Kanaele derselben Senderfamilie).

Die Seite zeigt ohne Login/JS-API ein rollierendes Wochenraster (Montag
bis Sonntag der aktuellen Woche) direkt als serverseitig gerendertes
HTML - sieben "tv-guide-box"-Bloecke (einer je Wochentag, Datum als
"TT.MM." ohne Jahr) mit je einer Liste aus "tv-guide-show-row"-Zeilen
(Uhrzeit + Sendungstitel). Keine Endzeit je Zeile - wird wie bei anderen
Quellen dieses Repos (z.B. rtvbn_epg.py) aus der Startzeit der naechsten
Sendung berechnet.

Wird nur EINMAL pro Lauf geladen und geparst (Modul-weiter Cache).
Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt Download oder
Parsen fehl, bekommt der betroffene Sender in generate_epg.py einfach
die normale, kategoriebasierte generische EPG-Generierung wie jeder
andere Sender - dieses Modul darf einen Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import re

import requests
from quellen import _http
from zoneinfo import ZoneInfo

URL = "https://grand.rs/tv-program/"

REQUEST_TIMEOUT_SEKUNDEN = 20

TZ_BELGRADE = ZoneInfo("Europe/Belgrade")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_NAME_PATTERN = re.compile(r"^GRAND\s*TV\b", re.IGNORECASE)

# Nur die Datums-Markierung selbst matchen, NICHT den nachfolgenden
# "tv-guide-shows"-Block per (.*?) mitfangen: jede einzelne Sendungs-
# zeile endet bereits mit "</div></div>" (Zeit- und Name-<div> beide
# geschlossen), ein nicht-gieriges Muster wuerde daher faelschlich
# schon nach der ERSTEN Zeile abbrechen statt am Ende des ganzen Tages-
# Blocks. Stattdessen wird die Grenze zwischen den Bloecken ueber die
# Position des jeweils naechsten Treffers bestimmt (siehe
# _alle_tage_laden(), analog zu rtvbn_epg.py).
_TAG_DATUM_PATTERN = re.compile(r'tv-guide-date">[^<]*?(\d{1,2})\.(\d{1,2})\.</div>')
_ZEILE_PATTERN = re.compile(
    r'tv-guide-show-time">(\d{1,2}):(\d{2})</div>'
    r'<div class="tv-guide-show-name">([^<]*)</div>'
)

# Modul-weiter Cache: die kombinierte, sortierte Sendungsliste.
_programme_cache = None


def grand_kanal_finden(kanalname):
    """True (als 1/0-Marker), wenn der Name "GRAND TV" entspricht (mit
    beliebigen HD/VIP/RAW-Zusaetzen), sonst None. Matcht NICHT "Grand
    1"/"Grand 2" (kein "TV" direkt nach "Grand" bei diesen)."""
    name = re.sub(r"\s+", " ", kanalname.strip())
    return 1 if _NAME_PATTERN.match(name) else None


def _datum_ableiten(tag, monat, heute):
    """Leitet aus einem reinen Tag/Monat (ohne Jahr, wie von grand.rs
    geliefert) das passende Datum ab - nimmt das aktuelle Jahr, oder das
    naechste, falls das Datum sonst mehr als 7 Tage in der Vergangenheit
    laege. Die Seite zeigt die GESAMTE aktuelle Woche (Montag bis
    Sonntag), der Montag kann daher schon bis zu 6 Tage in der
    Vergangenheit liegen (falls "heute" ein Sonntag ist) - eine engere
    Toleranz wie bei tvmovie_epg.py (nur der aktuelle Tag) wuerde diesen
    faelschlich ins naechste Jahr verschieben (beobachtet: "14.09."
    landete bei "heute"=18.09. faelschlich auf 2027 statt 2026)."""
    jahr = heute.year
    try:
        kandidat = datetime(jahr, monat, tag).date()
    except ValueError:
        return None
    if kandidat < heute - timedelta(days=7):
        try:
            kandidat = datetime(jahr + 1, monat, tag).date()
        except ValueError:
            return None
    return kandidat


def _alle_tage_laden():
    """Laedt (und cached) die Programmseite, parst alle sieben
    Wochentags-Bloecke und fuegt alles zu einer durchgehenden, sortierten
    Sendungsliste zusammen. Liefert [] bei jedem Fehler."""
    global _programme_cache

    if _programme_cache is not None:
        return _programme_cache

    try:
        response = _http.mit_retry(requests.get, URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        response.encoding = "utf-8"
        html = response.text

        heute = datetime.now(TZ_BELGRADE).date()

        datums_treffer = list(_TAG_DATUM_PATTERN.finditer(html))

        rohe_eintraege = []
        for i, tag_treffer in enumerate(datums_treffer):
            tag, monat = tag_treffer.groups()
            datum = _datum_ableiten(int(tag), int(monat), heute)
            if datum is None:
                continue

            block_ende = datums_treffer[i + 1].start() if i + 1 < len(datums_treffer) else len(html)
            shows_html = html[tag_treffer.end():block_ende]

            for std, minu, titel in _ZEILE_PATTERN.findall(shows_html):
                titel = titel.strip()
                if not titel:
                    continue
                start_lokal = datetime(
                    datum.year, datum.month, datum.day,
                    int(std), int(minu), tzinfo=TZ_BELGRADE,
                )
                rohe_eintraege.append({"start_lokal": start_lokal, "titel": titel})

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

        print(f"Grand-TV-EPG (grand.rs): {len(programme)} Sendungen geladen.")
        _programme_cache = programme
        return programme
    except Exception as e:
        print(f"Grand-TV-EPG (grand.rs): Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _programme_cache = []
        return []


def grand_hole_programme(marker, tage=3):
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
