"""Echte Programmdaten fuer "MySports 1-9"/"MySports EDGE" (CH) von
teleboy.ch - AUTOMATISCH fuer jeden Sender, dessen Name auf "MYSPORTS
<Nummer>" oder "MYSPORTS EDGE" passt (mit oder ohne HD/4K/VIP/RAW-
Zusaetzen). Kein eigenes Praefix noetig.

Hintergrund (September 2026): die generische DE-Kaskade (deswird.org/
tvmovie.de/hoerzu.de) kennt gar keinen echten "MySports"-Kanal - der
unscharfe difflib-Abgleich matchte "MYSPORTS" bisher faelschlich auf
den voellig anderen Sender "Sky Sport"/"eSports1" (aehnliche
Buchstabenfolge), was als "echter Treffer" durchging und dauerhaft
falsche fremde Programmdaten anzeigte. MySports-Sender werden daher in
generate_epg.py VOR der DE-Kaskade abgefangen (siehe MAGENTA-SPORT-PPV-
Sonderfall) und gehen direkt hierher.

teleboy.ch (Schweizer IPTV-Anbieter) fuehrt "MySports 1" unter drei
Sprachvarianten (Eins/Un/Uno) - hier wird bewusst die deutsche Variante
("mySports Eins") verwendet. "MySports 10" gibt es bei teleboy.ch NICHT
(nur 1-9 + EDGE) - dafuer liefert diese Quelle daher bewusst keinen
Treffer, der Sender bleibt beim generischen Platzhalter.

Nutzt die oeffentliche, im Teleboy-Webseiten-Frontend selbst offen
sichtbare API (https://tv.api.teleboy.ch/epg/broadcasts, Header
"x-teleboy-apikey") - kein Login, kein eigener Account noetig, exakt
dieselbe Anfrage wie die normale TV-Programm-Seite
(https://www.teleboy.ch/programm/sender/<id>/<slug>) im Browser macht.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt Download, Parsen
oder Kanalsuche fehl, bekommt der betroffene Sender in generate_epg.py
einfach die normale, kategoriebasierte generische EPG-Generierung wie
jeder andere Sender - dieses Modul darf einen Lauf niemals zum Absturz
bringen.
"""

from datetime import datetime, timedelta, timezone

import re

import requests
from quellen import _http

BASIS_URL = "https://tv.api.teleboy.ch/epg/broadcasts"
API_KEY = "541f13d53884e15c21045ea7d39d7b173add142a724cb030f7e698b951e8a538"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "x-teleboy-apikey": API_KEY,
}
REQUEST_TIMEOUT_SEKUNDEN = 20

# Teleboy-Stations-IDs je MySports-Nummer bzw. "EDGE" (per
# https://tv.api.teleboy.ch/epg/stations am 26.09.2026 verifiziert).
# "MySports 1" laeuft bei teleboy.ch nur unter der deutschen
# Sprachvariante "mySports Eins" (ID 622) - die franzoesische/
# italienische Variante (Un/Uno) wird bewusst NICHT verwendet.
# "MySports 10" existiert bei teleboy.ch nicht (bewusst kein Eintrag).
_STATION_IDS = {
    "1": 622,
    "2": 624,
    "3": 625,
    "4": 626,
    "5": 627,
    "6": 628,
    "7": 629,
    "8": 630,
    "9": 631,
    "EDGE": 633,
}

_MYSPORTS_PATTERN = re.compile(r"^MYSPORTS\s*(\d{1,2}|EDGE)\b", re.IGNORECASE)

# Anzahl der zu ladenden Tage (heute + Folgetage) - bewusst knapp
# gehalten wie bei den anderen Quellen (ein Request pro Sender).
_LADE_TAGE = 2

# Modul-weiter Cache je Station-ID: None (noch nicht geladen) oder die
# geladene Programmliste.
_programme_cache = {}


def mysports_kanal_finden(kanalname):
    """Erkennt "MYSPORTS <Nummer>" bzw. "MYSPORTS EDGE" (mit beliebigen
    Whitespace-/HD/4K/VIP/RAW-Zusaetzen) und gibt die zugehoerige
    teleboy.ch-Stations-ID zurueck, sonst None. "MYSPORTS 10" liefert
    bewusst None (siehe Moduldocstring)."""
    if not kanalname:
        return None
    treffer = _MYSPORTS_PATTERN.match(kanalname.strip())
    if not treffer:
        return None
    schluessel = treffer.group(1).upper()
    return _STATION_IDS.get(schluessel)


def _laden(station_id):
    """Laedt und parst (und cached) die Sendungen der naechsten
    `_LADE_TAGE` Tage fuer eine Station-ID. Liefert eine Liste von
    {"title", "beschreibung", "bild", "start", "stop"}-Dicts (UTC),
    oder [] bei jedem Fehler."""
    if station_id in _programme_cache:
        return _programme_cache[station_id]

    jetzt = datetime.now(timezone.utc)
    beginn = jetzt - timedelta(hours=6)
    ende = jetzt + timedelta(days=_LADE_TAGE)

    programme = []
    try:
        params = {
            "station": str(station_id),
            "begin": beginn.strftime("%Y-%m-%d %H:%M:%S"),
            "end": ende.strftime("%Y-%m-%d %H:%M:%S"),
            "limit": 200,
            "sort": "time",
        }
        response = _http.mit_retry(
            requests.get, BASIS_URL, headers=HEADERS, params=params, timeout=REQUEST_TIMEOUT_SEKUNDEN
        )
        response.raise_for_status()
        antwort = response.json()
        if not antwort.get("success"):
            raise ValueError(antwort.get("error_message", "unbekannter API-Fehler"))

        for item in antwort.get("data", {}).get("items", []):
            titel = (item.get("title") or "").strip()
            if not titel:
                continue
            start = datetime.fromisoformat(item["begin"]).astimezone(timezone.utc)
            stop = datetime.fromisoformat(item["end"]).astimezone(timezone.utc)
            if stop <= start:
                continue
            beschreibung = (item.get("subtitle") or "").strip()
            if not beschreibung or beschreibung == titel:
                beschreibung = (item.get("short_description") or titel).strip()
            programme.append({
                "title": titel,
                "beschreibung": beschreibung,
                "bild": None,
                "start": start,
                "stop": stop,
            })
        programme.sort(key=lambda p: p["start"])
    except Exception as e:
        print(f"MySports-Teleboy-EPG (Station {station_id}): Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        programme = []

    _programme_cache[station_id] = programme
    return programme


def mysports_hole_programme(station_id, tage=2):
    """Liefert die bereits geladenen Programmdaten fuer eine per
    mysports_kanal_finden() ermittelte Station-ID. Leere Liste bei
    jedem Fehler oder wenn station_id None ist."""
    if not station_id:
        return []
    return _laden(station_id)
