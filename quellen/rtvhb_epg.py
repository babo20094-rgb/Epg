"""Optionale, echte Programmdaten von rtv-hb.com (Radiotelevizija Herceg-
Bosne, Bosnien) - AUTOMATISCH als vierter Versuch fuer BA-Sender (nach
Telemach/mtel.ba/klix.ba, siehe die Verarbeitungsbloecke in
generate_epg.py), nur wenn keine der anderen Quellen fuer diesen Sender
etwas gefunden hat.

rtv-hb.com fuehrt (anders als Telemach/mtel.ba/klix.ba) KEINE
Mehrkanal-Kanalliste - die Seite ist der Sender-eigene TV-Guide fuer
GENAU EINEN Kanal ("RTV Herceg Bosne"). Es gibt daher keine Kanalsuche
per site_id, sondern nur einen Namensabgleich (`rtvhb_kanal_finden()`),
ob der uebergebene Sendername ueberhaupt "RTV Herceg Bosne" meint (auch
bei leicht abweichender Schreibweise wie "TV Herceg Bosne"/"Radio-
televizija Herceg Bosne"/mit Bindestrich).

Der Wochenplan liegt statisch je Wochentag unter
`https://rtv-hb.com/tv-program/<wochentag>` (bosnisch: ponedjeljak,
utorak, srijeda, petak, subota, nedjelja) - fuer "cetvrtak" (Donnerstag)
liefert dieser Pfad einen 404, die Seite ist dort stattdessen nur unter
`https://rtv-hb.com/node/714` erreichbar (eigener interner Node-Pfad,
vermutlich ein Redaktions-Artefakt der Drupal-Seite - falls sich das
irgendwann aendert, siehe docs/HISTORIE.md fuer diesen Sonderfall).

Jede Seite listet den kompletten Tag als `<li class="list-group-item">`
-Eintraege mit Startzeit-Endzeit ("field-time-schedule-tv"), Titel
("field-title-schedule-tv") und kurzer Beschreibung ("field-
description"). Da der Plan wochentagsbasiert (nicht datumsbasiert) ist,
wird fuer jeden der naechsten `tage` Kalendertage der passende
Wochentags-Pfad abgerufen und auf das echte Datum gemappt.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen - dieses Modul darf einen
Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import difflib
import re

import requests
from bs4 import BeautifulSoup

from quellen import _http
from epg_lib import normalisiere_sendername

BASIS_URL = "https://rtv-hb.com"

# Bosnischer Wochentag (Montag=0) -> URL-Pfad. Donnerstag ist auf der
# Seite selbst kein "/tv-program/cetvrtak", sondern nur ueber den
# internen Node-Pfad erreichbar (siehe Modul-Docstring).
_WOCHENTAG_PFAD = {
    0: "/tv-program/ponedjeljak",
    1: "/tv-program/utorak",
    2: "/tv-program/srijeda",
    3: "/node/714",
    4: "/tv-program/petak",
    5: "/tv-program/subota",
    6: "/tv-program/nedjelja",
}

# Bekannte Schreibweisen des Sendernamens - fuer den unscharfen Abgleich
# in rtvhb_kanal_finden() gegen den in sender.txt hinterlegten Namen.
_BEKANNTE_NAMEN = [
    "RTV Herceg Bosne",
    "TV Herceg Bosne",
    "Radiotelevizija Herceg Bosne",
    "Radiotelevizija Herceg-Bosne",
    "RTV Herceg-Bosne",
]

REQUEST_TIMEOUT_SEKUNDEN = 20

SARAJEVO_TZ = ZoneInfo("Europe/Sarajevo")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_tag_cache = {}

_BEKANNTE_SCHLUESSEL = {normalisiere_sendername(n) for n in _BEKANNTE_NAMEN}


def rtvhb_kanal_finden(kanalname):
    """Prueft, ob kanalname "RTV Herceg Bosne" meint (auch bei leicht
    abweichender Schreibweise) - gibt True/False zurueck. Es gibt nur
    diesen einen Kanal auf rtv-hb.com, daher keine echte Kanalsuche."""
    ziel_schluessel = normalisiere_sendername(kanalname)
    if not ziel_schluessel:
        return False

    if ziel_schluessel in _BEKANNTE_SCHLUESSEL:
        return True

    aehnliche = difflib.get_close_matches(
        ziel_schluessel, _BEKANNTE_SCHLUESSEL, n=1, cutoff=0.72
    )
    return bool(aehnliche)


def _zeit_parsen(text, basis_tag):
    """Parst "HH:MM - HH:MM"/"HH:MM- HH:MM" (Leerzeichen um den
    Bindestrich variiert auf der Seite) zu (start, stop) als
    Sarajevo-datetimes fuer basis_tag. Ein Endzeit-Wert von 00:00
    bedeutet Mitternacht des FOLGETAGS. Gibt None bei jedem
    Parse-Fehler zurueck."""
    match = re.match(
        r"^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$", (text or "").strip()
    )
    if not match:
        return None
    start_h, start_m, stop_h, stop_m = (int(g) for g in match.groups())
    start = datetime(basis_tag.year, basis_tag.month, basis_tag.day, start_h, start_m, tzinfo=SARAJEVO_TZ)
    stop = datetime(basis_tag.year, basis_tag.month, basis_tag.day, stop_h, stop_m, tzinfo=SARAJEVO_TZ)
    if stop <= start:
        stop += timedelta(days=1)
    return start, stop


def _seite_holen(pfad):
    """Holt (und cached pro Pfad) die rohe HTML-Seite als BeautifulSoup-
    Objekt. Gibt bei jedem Fehler None zurueck."""
    if pfad in _tag_cache:
        return _tag_cache[pfad]

    try:
        response = _http.mit_retry(
            requests.get, BASIS_URL + pfad, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        _tag_cache[pfad] = soup
        return soup
    except Exception as e:
        print(f"RTV-HB-EPG: Abruf von {pfad} fehlgeschlagen ({e}), ueberspringe.")
        _tag_cache[pfad] = None
        return None


def _tag_programme_parsen(soup, tag):
    ergebnis = []
    for item in soup.select("li.list-group-item"):
        zeit_feld = item.select_one(".field--name-field-time-schedule-tv")
        titel_feld = item.select_one(".field--name-field-title-schedule-tv")
        if zeit_feld is None or titel_feld is None:
            continue

        zeitspanne = _zeit_parsen(zeit_feld.get_text(" ", strip=True), tag)
        titel = titel_feld.get_text(" ", strip=True)
        if zeitspanne is None or not titel:
            continue

        beschr_feld = item.select_one(".field--name-field-description")
        beschreibung = beschr_feld.get_text(" ", strip=True) if beschr_feld else ""

        start, stop = zeitspanne
        ergebnis.append({
            "title": titel,
            "beschreibung": beschreibung,
            "bild": None,
            "start": start,
            "stop": stop,
        })

    return ergebnis


def rtvhb_hole_programme(tage=3):
    """Holt den Wochentags-basierten Programmplan von rtv-hb.com fuer
    `tage` aufeinanderfolgende Kalendertage ab heute (Europe/Sarajevo).
    Liefert eine nach Startzeit sortierte Liste von {"title",
    "beschreibung", "bild", "start", "stop"} (UTC, tz-aware) - leere
    Liste bei jedem Fehler."""
    heute = datetime.now(SARAJEVO_TZ).date()

    alle = []
    for i in range(tage):
        tag = heute + timedelta(days=i)
        pfad = _WOCHENTAG_PFAD.get(tag.weekday())
        if pfad is None:
            continue
        soup = _seite_holen(pfad)
        if soup is None:
            continue
        try:
            alle.extend(_tag_programme_parsen(soup, tag))
        except Exception as e:
            print(f"RTV-HB-EPG: Parsen fuer Tag {tag} fehlgeschlagen ({e}), ueberspringe Tag.")
            continue

    ergebnis = []
    for p in alle:
        try:
            ergebnis.append({
                "title": p["title"],
                "beschreibung": p.get("beschreibung") or "",
                "bild": None,
                "start": p["start"].astimezone(timezone.utc),
                "stop": p["stop"].astimezone(timezone.utc),
            })
        except Exception:
            continue

    ergebnis.sort(key=lambda s: s["start"])
    return ergebnis
