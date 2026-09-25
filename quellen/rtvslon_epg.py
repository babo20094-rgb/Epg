"""Echte Programmdaten fuer RTV Slon (Tuzla) von rtvslon.ba/tv-program/
- AUTOMATISCH fuer jeden Sender, dessen Name "RTV SLON" (mit HD/VIP/RAW-
Zusaetzen) entspricht. Kein eigenes Praefix noetig.

Anders als die meisten anderen Einzelsender-Quellen zeigt EINE einzige
Seite direkt ZWEI komplette Kalenderwochen (14 Tage, jeweils mit
echtem Datum in der Zwischenueberschrift "TV program za <Wochentag>
<DD.MM.YYYY>.") als reinen Flieass-/Zeilentext ("HH:MM Titel<br>") -
kein Kanalverzeichnis, keine Paginierung noetig, nur EIN Request pro
Lauf deckt alle 14 Tage ab.

Ein Titel-Segment enthaelt oft schon eine kurze Beschreibung, getrennt
per Gedankenstrich ("Rijeka strasti – igrana serija (R)") - wird hier
in title/beschreibung aufgetrennt, damit kuerze_beschreibung() in
generate_epg.py (die nur an ": " trennt) nicht noetig ist. Wiederkehrende
Fuellprogramm-/Werbeblock-Titel ("Marketing", "Teletrgovina", "Video
strane") werden gefiltert, analog zu vikom_epg.py.

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

from epg_lib import normalisiere_sendername

URL = "https://www.rtvslon.ba/tv-program/"

REQUEST_TIMEOUT_SEKUNDEN = 20

SARAJEVO_TZ = ZoneInfo("Europe/Sarajevo")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_WHITELIST = {normalisiere_sendername("RTV Slon")}

_FUELLPROGRAMM = {"marketing", "teletrgovina", "video strane"}

_HEADING_RE = re.compile(r"TV program za [^<]+?\s+(\d{2})\.(\d{2})\.(\d{4})\.")
_ZEILE_RE = re.compile(r"(\d{1,2}):(\d{2})\s+([^<]+?)<br\s*/?>")
_TRENNER_RE = re.compile(r"\s+[–—-]\s*")

_programme_cache = None


def rtvslon_kanal_treffer(sendername):
    """Nur ein exakter Abgleich gegen die enge Whitelist oben (True/
    False) - kein Netzwerk-Request, reiner Namensvergleich."""
    schluessel = normalisiere_sendername(sendername)
    return bool(schluessel) and schluessel in _WHITELIST


def _text_bereinigen(text):
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def _seite_laden():
    """Laedt (und cached) die komplette Seite, geparst zu einer nach
    Startzeit sortierten Liste von {"title", "beschreibung", "start"}
    (tz-aware). Leere Liste bei jedem Fehler."""
    global _programme_cache

    if _programme_cache is not None:
        return _programme_cache

    try:
        response = _http.mit_retry(requests.get, URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        text = response.text

        ueberschriften = list(_HEADING_RE.finditer(text))

        roh = []
        for i, treffer in enumerate(ueberschriften):
            tag, monat, jahr = (int(x) for x in treffer.groups())
            abschnitt_ende = ueberschriften[i + 1].start() if i + 1 < len(ueberschriften) else len(text)
            abschnitt = text[treffer.end():abschnitt_ende]

            for stunde_text, minute_text, titel_roh in _ZEILE_RE.findall(abschnitt):
                titel_roh = _text_bereinigen(titel_roh)
                if not titel_roh:
                    continue
                teile = _TRENNER_RE.split(titel_roh, maxsplit=1)
                kern = teile[0].strip()
                beschreibung = teile[1].strip() if len(teile) > 1 else ""
                if not kern or kern.lower() in _FUELLPROGRAMM:
                    continue
                try:
                    start = datetime(
                        jahr, monat, tag, int(stunde_text), int(minute_text), tzinfo=SARAJEVO_TZ,
                    )
                except ValueError:
                    continue
                roh.append({"title": kern, "beschreibung": beschreibung, "start": start})

        roh.sort(key=lambda e: e["start"])
        _programme_cache = roh
        return roh
    except Exception as e:
        print(f"RtvSlon-EPG: Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _programme_cache = []
        return []


def rtvslon_hole_programme(tage=7):
    """Liefert Programmdaten fuer RTV Slon fuer `tage` Tage ab heute
    (Europe/Sarajevo), Endzeit aus dem Start der jeweils naechsten
    Sendung berechnet (letzte Sendung endet um Mitternacht). Leere
    Liste bei jedem Fehler."""
    roh = _seite_laden()
    if not roh:
        return []

    heute = datetime.now(SARAJEVO_TZ).date()
    grenze = heute + timedelta(days=tage)

    ergebnis = []
    for index, eintrag in enumerate(roh):
        if not (heute <= eintrag["start"].date() < grenze):
            continue
        if index + 1 < len(roh):
            stop = roh[index + 1]["start"]
        else:
            tag_start = eintrag["start"].replace(hour=0, minute=0, second=0, microsecond=0)
            stop = tag_start + timedelta(days=1)
        if stop <= eintrag["start"]:
            continue
        ergebnis.append({
            "title": eintrag["title"],
            "beschreibung": eintrag["beschreibung"],
            "bild": None,
            # Nach UTC konvertieren, nicht Europe/Sarajevo belassen -
            # generate_epg.py haengt beim Schreiben nur "+0000" an die
            # (dann noch lokale) Uhrzeit an, statt sie umzurechnen - ohne
            # diese Konvertierung landen alle Sendungen 1-2h zu spaet im
            # EPG (gleicher Bug wie bei tvmovie_epg.py, September 2026,
            # siehe docs/HISTORIE.md).
            "start": eintrag["start"].astimezone(ZoneInfo("UTC")),
            "stop": stop.astimezone(ZoneInfo("UTC")),
        })

    return ergebnis
