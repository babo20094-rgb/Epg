"""Automatische, echte Programmdaten von tv-spored.siol.net (Slowenien
UND Nordmazedonien).

AUTOMATISCH fuer jeden ganz normal in sender.txt eingetragenen Sender
mit Land "SI" oder "MK" (kein eigenes Praefix noetig, gleiches Prinzip
wie der BA/ME-Telemach-Autoabgleich in generate_epg.py). siol.net fuehrt
neben slowenischen auch eine kleine Zahl mazedonischer Sender (Alfa TV,
Alsat Macedonia, TV Sitel, MTV 1/2/3 - die MRT-Kanaele).

WICHTIGE EINSCHRAENKUNG: tv-spored.siol.net liefert keine stabile JSON-
API, sondern rendert eine Next.js-Seite. Das Sendungsraster steht dabei
direkt als lesbares HTML im Seitenquelltext (kein <script>-JSON-Payload
mehr wie in einer frueheren Version dieses Moduls - die Seite wurde
September 2026 offenbar neu gebaut, der alte "self.__next_f.push(...)"-
Scraping-Ansatz fand keine Daten mehr). Jede Sendung ist ein <a>-Element
mit einer Startzeit ("H.MM", ohne fuehrende Null, Punkt statt
Doppelpunkt) und einem Titel; eine Endzeit liefert die Seite nicht -
sie wird wie bei arena_epg.py/klix_epg.py aus der Startzeit der
naechsten Sendung berechnet (letzte Sendung des Tages endet um
Mitternacht). Wie bei allen anderen echten Quellen dieses Repos gilt:
schlaegt die Extraktion an irgendeiner Stelle fehl (Netzwerk,
unerwartete Seitenstruktur), wird das konsequent und leise mit []
beantwortet statt mit einer Exception, und generate_epg.py faellt fuer
den betroffenen Sender auf die normale, kategoriebasierte generische
EPG-Generierung zurueck. Dieses Modul darf einen Lauf niemals zum
Absturz bringen.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import difflib
import re

import requests
from bs4 import BeautifulSoup

from epg_lib import normalisiere_sendername, normalisiere_sendername_kern

BASE_URL = "https://tv-spored.siol.net"

REQUEST_TIMEOUT_SEKUNDEN = 20

LJUBLJANA_TZ = ZoneInfo("Europe/Ljubljana")

_ZEIT_PATTERN = re.compile(r"^\s*(\d{1,2})\.(\d{2})\s*$")

# Modul-weiter Cache, analog zu telemach_epg.py.
_kanalliste_cache = None
_programm_cache = {}


def siol_hole_kanalliste():
    """Holt (und cached) die komplette siol.net-Kanalliste (per HTML-
    Scraping der Kanaluebersichtsseite) als Liste von {"site_id":...,
    "name":...}. Leere Liste bei jedem Fehler (Netzwerk, unerwartete
    Seitenstruktur)."""
    global _kanalliste_cache

    if _kanalliste_cache is not None:
        return _kanalliste_cache

    try:
        response = requests.get(f"{BASE_URL}/kanali", timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        kanaele = []
        gesehen = set()
        for link in soup.find_all("a", href=re.compile(r"^/kanal/[a-z0-9_-]+$")):
            site_id = link["href"].rsplit("/", 1)[-1]
            if site_id in gesehen:
                continue
            bild = link.find("img")
            name = bild.get("alt") if bild else None
            if not name:
                continue
            gesehen.add(site_id)
            kanaele.append({"site_id": site_id, "name": name})

        if not kanaele:
            print("Siol-EPG: Kanalliste nicht gefunden/unerwartete Struktur, ueberspringe.")

        _kanalliste_cache = kanaele
        return kanaele
    except Exception as e:
        print(f"Siol-EPG: Kanalliste fehlgeschlagen ({e}), ueberspringe.")
        _kanalliste_cache = []
        return []


# Feste Alias-Aufloesung fuer kurze, mehrdeutige mazedonische
# Sendernamen: siol.net fuehrt die MRT-Sender unter dem Kuerzel "MTV"
# (site_id "mktv1"/"mktv2"/"mktv3"), die eigene Playlist/sender.txt
# nennt sie ueblich "MRT 1"/"MRT 2"/"MRT 3"; "Alsat Macedonia" wird in
# der Playlist meist verkuerzt "Alsat M" genannt. Bei so kurzen,
# generischen Namen ("MRT1") landet der unscharfe difflib-Abgleich
# unten sonst GEFAEHRLICH nah an voellig anderen, inhaltlich falschen
# Sendern anderer Laender (bestaetigt: "MRT1"->"RTS1" [Serbien],
# "MRT2"->"RTS2" [Serbien], "MRT3"->"HRT3" [Kroatien], "MRT2HD"->
# "MTVLIVEHD" [voellig anderer Sender] - jeweils nur 1-2 Zeichen
# Unterschied bei kurzer Gesamtlaenge, damit weit ueber der
# 0.72-Aehnlichkeits-Schwelle, obwohl es komplett andere Sender sind).
# Diese festen Aliase werden deshalb VOR dem unscharfen Abgleich anhand
# des HD/FHD/SD-bereinigten Kerns geprueft und bei Treffer direkt
# zurueckgegeben - kein Fehltreffer-Risiko mehr fuer diese Sender.
_MK_ALIASE = {
    "MRT1": "mktv1",
    "MRT2": "mktv2",
    "MRT3": "mktv3",
    "ALSATM": "alsatm",
}


def siol_kanal_finden(kanalname):
    """Sucht den siol.net-Kanal, der am besten zu kanalname passt -
    erst feste Alias-Aufloesung (MRT 1-3/Alsat M), dann exakter
    Abgleich nach normalisiere_sendername(), sonst unscharfer
    difflib-Abgleich. Gibt die site_id zurueck oder None."""
    kanaele = siol_hole_kanalliste()
    if not kanaele:
        return None

    ziel_schluessel = normalisiere_sendername(kanalname)
    if not ziel_schluessel:
        return None

    alias_schluessel = normalisiere_sendername_kern(kanalname)
    if alias_schluessel in _MK_ALIASE:
        vorhandene_ids = {kanal["site_id"] for kanal in kanaele}
        alias_id = _MK_ALIASE[alias_schluessel]
        if alias_id in vorhandene_ids:
            return alias_id

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


def _startzeit_parsen(text, tag):
    """Parst eine siol.net-Startzeit im Format 'H.MM' (keine fuehrende
    Null, Punkt statt Doppelpunkt, z.B. '9.30' oder '14.05') zu einem
    tz-aware UTC-datetime fuer den gegebenen Kalendertag (Europe/
    Ljubljana). None bei jedem Parse-Fehler/unerwarteten Format."""
    if not text:
        return None
    treffer = _ZEIT_PATTERN.match(text)
    if not treffer:
        return None
    stunde, minute = int(treffer.group(1)), int(treffer.group(2))
    if stunde > 23 or minute > 59:
        return None
    try:
        lokal = tag.replace(hour=stunde, minute=minute, second=0, microsecond=0, tzinfo=LJUBLJANA_TZ)
        return lokal.astimezone(timezone.utc)
    except Exception:
        return None


def _hole_events_fuer_kanal_und_tag(site_id, datum):
    """Holt (und cached pro Kanal+Datum) die Liste roher (Startzeit,
    Titel, Kategorie)-Tupel fuer einen Kanal/Tag per HTML-Scraping.
    Leere Liste bei jedem Fehler."""
    datum_str = datum.strftime("%Y%m%d")
    cache_key = (site_id, datum_str)

    if cache_key in _programm_cache:
        return _programm_cache[cache_key]

    url = f"{BASE_URL}/kanal/{site_id}/datum/{datum_str}"

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        rohe_sendungen = []
        for link in soup.find_all("a", href=re.compile(rf"^/kanal/{re.escape(site_id)}/oddaja/")):
            zeit_div = link.find("div", class_="w-[70px]")
            titel_div = link.find("div", class_="font-extrabold")
            if zeit_div is None or titel_div is None:
                continue
            titel = titel_div.get("title") or titel_div.get_text(strip=True)
            kategorie_div = titel_div.find_next_sibling("div")
            kategorie = kategorie_div.get_text(strip=True) if kategorie_div else ""
            rohe_sendungen.append((zeit_div.get_text(strip=True), titel, kategorie))

        _programm_cache[cache_key] = rohe_sendungen
        return rohe_sendungen
    except Exception as e:
        print(f"Siol-EPG: Programmabruf fuer Kanal {site_id} ({datum_str}) fehlgeschlagen ({e}), ueberspringe Tag.")
        _programm_cache[cache_key] = []
        return []


def siol_hole_programme(site_id, tage=2):
    """Holt Programmdaten fuer den gegebenen siol.net-Kanal (site_id)
    fuer `tage` aufeinanderfolgende Tage ab heute (Europe/Ljubljana).
    Liefert eine nach Startzeit sortierte Liste von {"title",
    "beschreibung", "bild", "start", "stop"} - leere Liste bei jedem
    Fehler (Netzwerk, HTTP-Status, unerwartete/fehlende Seitenstruktur).
    Die Seite liefert keine Endzeiten - die Endzeit einer Sendung wird
    aus der Startzeit der naechsten Sendung berechnet (letzte Sendung
    eines Tages endet um Mitternacht), analog zu arena_epg.py."""
    if not site_id:
        return []

    heute = datetime.now(LJUBLJANA_TZ).replace(hour=0, minute=0, second=0, microsecond=0)

    alle_sendungen = []

    for tag_index in range(tage):
        tag = heute + timedelta(days=tag_index)

        try:
            rohe_sendungen = _hole_events_fuer_kanal_und_tag(site_id, tag)
            naechster_tag_mitternacht = (tag + timedelta(days=1)).astimezone(timezone.utc)

            geparste = []
            for zeit_text, titel, kategorie in rohe_sendungen:
                start = _startzeit_parsen(zeit_text, tag)
                if not titel or not start:
                    continue
                geparste.append((start, titel, kategorie))

            geparste.sort(key=lambda s: s[0])

            for i, (start, titel, kategorie) in enumerate(geparste):
                stop = geparste[i + 1][0] if i + 1 < len(geparste) else naechster_tag_mitternacht
                if stop <= start:
                    continue
                alle_sendungen.append({
                    "title": titel,
                    "beschreibung": kategorie,
                    "bild": None,
                    "start": start,
                    "stop": stop,
                })
        except Exception as e:
            print(f"Siol-EPG: Verarbeitung fuer Kanal {site_id} Tag {tag_index} fehlgeschlagen ({e}), ueberspringe Tag.")
            continue

    alle_sendungen.sort(key=lambda s: s["start"])
    return alle_sendungen
