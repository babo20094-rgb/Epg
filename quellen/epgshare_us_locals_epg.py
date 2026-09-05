"""Echte Programmdaten fuer US-LOKALSENDER (Call-Sign-Affiliates) ueber
den community-gepflegten XMLTV-Mirror epgshare01.online
(epg_ripper_US_LOCALS1.xml.gz, Quelle laut eigenem <url>-Tag: tmsapi.com/
Gracenote).

Ergaenzt tvpassport_epg.py (unsere bisherige Quelle fuer die "CITY|"-
Sendergruppe, HTML-Scraping) um eine zweite, stabilere JSON/XML-basierte
Quelle mit ~4.400 US-Lokalsendern - deckt teils Call-Signs ab, die bei
tvpassport.com keinen Haupt-Affiliate-Eintrag haben, und liefert
zuverlaessigere Daten (keine HTML-Struktur-Abhaengigkeit wie bei
tvpassport.com).

Kanalzuordnung laeuft wie bei tvpassport_kanal_finden_callsign() NUR ueber
einen exakten Call-Sign-Abgleich (kein Fuzzy-Abgleich) - epgshare01 fuehrt
pro Call-Sign meist mehrere Subkanaele (z.B. "WPRI-DT" als Hauptkanal,
"WPRI-DT2"/"WPRI-DT3" als eigene Subkanaele mit komplett anderem
Programm). Nur die Endungen "-DT" oder der blanke Call-Sign (ohne jeden
Zusatz) gelten als Hauptkanal - Endungen mit Ziffer (-DT2, -DT3) oder
anderer Technik-Kuerzel (-LD/-CD, Low-Power/Class-A) werden bewusst NICHT
als Fallback akzeptiert, um keinen falschen Subkanal zu treffen.

Genau wie bei plutotv_epg.py/sportklub_epg.py/epgshare_us_epg.py wird die
komplette XMLTV-Datei (~60 MB gepackt) nur EINMAL pro Lauf geladen und
lokal gematcht, kein API-Aufruf pro Kanal.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen - dieses Modul darf einen
Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import gzip
import re
import xml.etree.ElementTree as ET

import requests

URL = "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz"

REQUEST_TIMEOUT_SEKUNDEN = 60

# Modul-weiter Cache: {"kanaele": [...], "programme": {kanal_id: [...]}}
_daten_cache = None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_CALLSIGN_PATTERN = re.compile(r"\b([KW][A-Z0-9]{2,4})\b")


def _xml_laden():
    """Laedt und parst (und cached) die komplette epgshare01-US-LOCALS1-
    XMLTV-Datei. Gibt {"kanaele": [...], "programme": {id: [...]}} zurueck,
    oder ein leeres (aber nicht-None) Dict bei jedem Fehler (Netzwerk,
    HTTP-Status, kaputtes Gzip/XML)."""
    global _daten_cache

    if _daten_cache is not None:
        return _daten_cache

    try:
        response = requests.get(URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        rohbytes = response.content

        try:
            xml_bytes = gzip.decompress(rohbytes)
        except OSError:
            xml_bytes = rohbytes

        wurzel = ET.fromstring(xml_bytes)

        kanaele = []
        for kanal_tag in wurzel.findall("channel"):
            kanal_id = kanal_tag.get("id")
            name_tag = kanal_tag.find("display-name")
            name = name_tag.text.strip() if name_tag is not None and name_tag.text else ""
            if not kanal_id or not name:
                continue
            kanaele.append({"site_id": kanal_id, "name": name})

        programme = {}
        for prog_tag in wurzel.findall("programme"):
            kanal_id = prog_tag.get("channel")
            if not kanal_id:
                continue

            start_roh = prog_tag.get("start")
            stop_roh = prog_tag.get("stop")
            if not start_roh or not stop_roh:
                continue

            start = _xmltv_zeit_parsen(start_roh)
            stop = _xmltv_zeit_parsen(stop_roh)
            if start is None or stop is None:
                continue

            titel_tag = prog_tag.find("title")
            titel = titel_tag.text.strip() if titel_tag is not None and titel_tag.text else ""
            if not titel:
                continue

            beschr_tag = prog_tag.find("desc")
            beschreibung = beschr_tag.text.strip() if beschr_tag is not None and beschr_tag.text else ""

            icon_tag = prog_tag.find("icon")
            bild = icon_tag.get("src") if icon_tag is not None else None

            programme.setdefault(kanal_id, []).append({
                "title": titel,
                "beschreibung": beschreibung,
                "bild": bild,
                "start": start,
                "stop": stop,
            })

        for eintraege in programme.values():
            eintraege.sort(key=lambda s: s["start"])

        print(f"EpgshareUS-Locals-EPG: {len(kanaele)} Kanaele, {len(programme)} Kanaele mit Sendungen geladen.")

        daten = {"kanaele": kanaele, "programme": programme}
        _daten_cache = daten
        return daten
    except Exception as e:
        print(f"EpgshareUS-Locals-EPG: Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _daten_cache = {"kanaele": [], "programme": {}}
        return _daten_cache


def _xmltv_zeit_parsen(text):
    """Parst das XMLTV-Zeitformat 'YYYYMMDDHHMMSS +ZZZZ' zu einem
    tz-aware datetime (UTC). None bei Parse-Fehler."""
    try:
        return datetime.strptime(text.strip(), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
    except Exception:
        return None


def epgshare_us_locals_kanal_finden(kanalname):
    """Sucht den epgshare01-US-LOCALS1-Kanal ausschliesslich ueber einen
    EXAKTEN Call-Sign-Abgleich (kein Fuzzy-Abgleich) - fuer die "CITY|"-
    Sendergruppe. Akzeptiert nur den Hauptkanal (Call-Sign gefolgt von
    "-DT" oder ganz ohne Zusatz) - Subkanaele mit Ziffer-Suffix (-DT2,
    -DT3) oder anderer Technik-Kennung (-LD/-CD) werden bewusst NICHT
    als Fallback akzeptiert, um keinen inhaltlich anderen Subkanal zu
    treffen. Gibt die site_id zurueck oder None."""
    treffer = _CALLSIGN_PATTERN.search(kanalname.upper())
    if not treffer:
        return None
    callsign = treffer.group(1)

    daten = _xml_laden()
    if not daten or not daten["kanaele"]:
        return None

    name_index = {kanal["name"].upper(): kanal["site_id"] for kanal in daten["kanaele"]}

    for kandidat in (f"{callsign}-DT", callsign):
        if kandidat in name_index:
            return name_index[kandidat]

    return None


def epgshare_us_locals_hole_programme(site_id, tage=2):
    """Liefert die bereits geladenen Programmdaten fuer den gegebenen
    Kanal (site_id) aus dem Modul-Cache, begrenzt auf die naechsten
    `tage` Tage ab heute (UTC). Leere Liste bei jedem Fehler oder wenn
    keine Sendungen vorhanden sind."""
    if site_id is None:
        return []

    daten = _xml_laden()
    if not daten:
        return []

    eintraege = daten["programme"].get(site_id, [])
    if not eintraege:
        return []

    heute = datetime.now(timezone.utc).date()
    erlaubte_tage = {heute + timedelta(days=i) for i in range(tage)}

    return [
        p for p in eintraege
        if (p["start"].date() in erlaubte_tage or p["stop"].date() in erlaubte_tage)
    ]
