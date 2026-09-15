"""Echte Programmdaten fuer BN2 (zweiter Kanal von Radio-televizija BN,
Bijeljina) von rtvbn.tv - AUTOMATISCH fuer jeden BA-Sender, dessen Name
"BN2"/"BN 2" entspricht (mit HD/VIP/RAW-Zusaetzen). Kein eigenes
Praefix noetig.

rtvbn.tv bietet fuer den HAUPTkanal ("TV BN") fertige XMLTV-Dateien
(epg-sat.xml usw.), aber KEINE eigene XMLTV-Datei fuer BN2 - dessen
Programm steht nur auf der normalen Programm-Uebersichtsseite
(rtvbn.tv/program) als HTML, dort als eigener "Program BN 2"-Kartenblock
(sichtbar unterschiedlich vom "Program BN"-Block direkt daneben, siehe
Verifikation weiter unten). Die Seite zeigt statisch (kein Login/JS-API
noetig) ALLE 7 Wochentage auf einmal, per <select>-Dropdown/CSS-Klasse
"showHide0".."showHide6" (0=Sonntag, 1=Montag, ... 6=Samstag) umschaltbar
- fuer uns irrelevant, da alle 7 Bloecke direkt im HTML stehen und nur
per CSS ausgeblendet werden. Nur Uhrzeiten, kein Datum je Zeile - das
Datum wird deshalb aus dem naechsten Vorkommen des jeweiligen
Wochentags ab heute berechnet (rollierende 7-Tage-Vorschau).

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
from zoneinfo import ZoneInfo

URL = "https://rtvbn.tv/program"

REQUEST_TIMEOUT_SEKUNDEN = 20

TZ_SARAJEVO = ZoneInfo("Europe/Sarajevo")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_NAME_PATTERN = re.compile(r"^BN\s*2\b", re.IGNORECASE)

# CSS-Klasse "showHideN" -> Python-Wochentag (Montag=0 ... Sonntag=6),
# siehe <select>-Dropdown auf der Seite (Ponedeljak..Nedelja).
_SHOWHIDE_ZU_WOCHENTAG = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}

_TAG_BLOCK_PATTERN = re.compile(r'row showHide showHide(\d)"')
_ZEILE_PATTERN = re.compile(
    r"<li><span>(\d{1,2}):(\d{2})</span><b>([^<]*)</b>\s*([^<]*)</li>"
)

# Modul-weiter Cache: die kombinierte, sortierte Sendungsliste.
_programme_cache = None


def rtvbn_kanal_finden(kanalname):
    """True (als 1/0-Marker), wenn der Name "BN2"/"BN 2" entspricht
    (mit beliebigen HD/VIP/RAW-Zusaetzen), sonst None. Matcht NICHT den
    Hauptkanal "BN TV" oder "BN Music" (kein "2" im Namen)."""
    name = re.sub(r"\s+", " ", kanalname.strip())
    return 1 if _NAME_PATTERN.match(name) else None


def _naechstes_datum(ziel_wochentag, heute):
    """Naechstes Datum >= heute mit dem gegebenen Wochentag (0=Montag)."""
    differenz = (ziel_wochentag - heute.weekday()) % 7
    return heute + timedelta(days=differenz)


def _bn2_block_extrahieren(block_html):
    """Extrahiert den "Program BN 2"-Kartenblock (nur dessen <ul>-Liste)
    aus dem HTML eines einzelnen Wochentag-Containers. None, wenn nicht
    gefunden."""
    start_treffer = re.search(r"<h3>Program BN 2</h3>", block_html)
    if not start_treffer:
        return None
    rest = block_html[start_treffer.end():]
    ul_start = rest.find("<ul>")
    ul_end = rest.find("</ul>")
    if ul_start == -1 or ul_end == -1:
        return None
    return rest[ul_start:ul_end]


def _alle_tage_laden():
    """Laedt (und cached) die Programmseite, parst fuer jeden Wochentag
    den "Program BN 2"-Block und fuegt alles zu einer durchgehenden,
    sortierten Sendungsliste zusammen. Liefert [] bei jedem Fehler."""
    global _programme_cache

    if _programme_cache is not None:
        return _programme_cache

    try:
        response = requests.get(URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        response.encoding = "utf-8"
        html = response.text

        block_marker = list(_TAG_BLOCK_PATTERN.finditer(html))
        heute = datetime.now(TZ_SARAJEVO).date()

        rohe_eintraege = []
        for i, marker in enumerate(block_marker):
            showhide_nr = int(marker.group(1))
            ziel_wochentag = _SHOWHIDE_ZU_WOCHENTAG.get(showhide_nr)
            if ziel_wochentag is None:
                continue

            block_ende = block_marker[i + 1].start() if i + 1 < len(block_marker) else len(html)
            block_html = html[marker.end():block_ende]

            bn2_liste = _bn2_block_extrahieren(block_html)
            if not bn2_liste:
                continue

            datum = _naechstes_datum(ziel_wochentag, heute)

            for std, minu, titel, zusatz in _ZEILE_PATTERN.findall(bn2_liste):
                titel = titel.strip()
                if not titel:
                    continue
                zusatz = zusatz.strip()
                start_lokal = datetime(
                    datum.year, datum.month, datum.day,
                    int(std), int(minu), tzinfo=TZ_SARAJEVO,
                )
                rohe_eintraege.append({
                    "start_lokal": start_lokal,
                    "titel": titel,
                    "beschreibung": f"{titel}: {zusatz}" if zusatz else titel,
                })

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
                "beschreibung": eintrag["beschreibung"],
                "bild": None,
                "start": start,
                "stop": stop,
            })

        print(f"BN2-EPG (rtvbn.tv): {len(programme)} Sendungen geladen.")
        _programme_cache = programme
        return programme
    except Exception as e:
        print(f"BN2-EPG (rtvbn.tv): Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _programme_cache = []
        return []


def rtvbn_hole_programme(marker, tage=3):
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
