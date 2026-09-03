"""Optionale, echte Programmdaten von Pluto TV Deutschland - AUTOMATISCH
als EINZIGE automatische Quelle fuer alle DE-Sender (kein eigenes
sender.txt-Praefix noetig), analog zum vorherigen free-epg.de-DE-Block,
aber mit saubereren, echten Pluto-TV-Kanalnamen statt generischer
Land-Kuerzel.

Datenquelle ist das offene, loginfreie i.mjh.nz/PlutoTV-XMLTV-Bulk-
Projekt (generator-info-name "www.matthuisman.nz", weit verbreitet und
bekannt, z.B. in vielen Kodi-Addons). Wie bei free-epg.de gibt es hier
keine Kanal-fuer-Kanal-API, sondern EINE komplette XMLTV-Datei mit allen
deutschen Pluto-TV-Kanaelen UND allen Sendungen darin - wird nur EINMAL
pro Lauf geladen und geparst (Modul-weiter Cache), danach werden alle
DE-Sender lokal dagegen gematcht ohne weitere Netzwerk-Aufrufe.

Deckt nur ca. 1-2 Tage im Voraus ab (kein mehrtaegiges Datumsraster wie
Telemach/mts.rs), Tage danach sind ohnehin immer generisch.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt der Download, das
Parsen oder die Kanalsuche fehl, bekommt der betroffene Sender in
generate_epg.py einfach die normale, kategoriebasierte generische
EPG-Generierung wie jeder andere Sender - dieses Modul darf einen Lauf
niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import gzip
import xml.etree.ElementTree as ET

import requests

from epg_lib import normalisiere_sendername, kanal_index_suchen, kern_index_aufbauen

URL = "https://i.mjh.nz/PlutoTV/de.xml.gz"

REQUEST_TIMEOUT_SEKUNDEN = 30

# Modul-weiter Cache: {"kanaele": [...], "programme": {kanal_id: [...]}}
_daten_cache = None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def _xml_laden():
    """Laedt und parst (und cached) die komplette PlutoTV-DE-XMLTV-Datei.
    Gibt {"kanaele": [...], "programme": {id: [...]}} zurueck, oder None
    bei jedem Fehler (Netzwerk, HTTP-Status, kaputtes Gzip/XML)."""
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
            start_roh = prog_tag.get("start")
            stop_roh = prog_tag.get("stop")
            if not kanal_id or not start_roh or not stop_roh:
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

        print(f"PlutoTV-EPG: {len(kanaele)} Kanaele, {len(programme)} Kanaele mit Sendungen geladen.")

        daten = {"kanaele": kanaele, "programme": programme}
        _daten_cache = daten
        return daten
    except Exception as e:
        print(f"PlutoTV-EPG: Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        # Fehlschlag wird ebenfalls gecacht (leeres, aber nicht-None
        # Dict statt None) - verhindert, dass bei einem dauerhaften Fehler
        # (Netzwerk down, Host tot) JEDER einzelne Sender in generate_epg.py
        # denselben fehlschlagenden Download erneut versucht.
        _daten_cache = {"kanaele": [], "programme": {}}
        return _daten_cache


def _xmltv_zeit_parsen(text):
    """Parst das XMLTV-Zeitformat 'YYYYMMDDHHMMSS +ZZZZ' zu einem
    tz-aware datetime (UTC). None bei Parse-Fehler."""
    try:
        return datetime.strptime(text.strip(), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
    except Exception:
        return None


def plutotv_kanal_finden(kanalname):
    """Sucht den PlutoTV-Kanal, der am besten zu kanalname passt - erst
    exakter Abgleich nach normalisiere_sendername(), dann ein
    eindeutiger Kern-Abgleich ohne HD/FHD/UHD/SD, zuletzt unscharfer
    difflib-Abgleich (siehe epg_lib.kanal_index_suchen()). Gibt die
    Kanal-ID zurueck oder None."""
    daten = _xml_laden()
    if not daten or not daten["kanaele"]:
        return None

    name_index = {}
    for kanal in daten["kanaele"]:
        schluessel = normalisiere_sendername(kanal["name"])
        if schluessel:
            name_index.setdefault(schluessel, kanal["site_id"])

    kern_index = kern_index_aufbauen(daten["kanaele"], "name", "site_id")

    return kanal_index_suchen(kanalname, name_index, kern_index)


def plutotv_hole_programme(site_id, tage=2):
    """Liefert die bereits geladenen Programmdaten fuer den gegebenen
    Kanal (site_id) aus dem Modul-Cache, begrenzt auf die naechsten
    `tage` Tage ab heute (UTC). Leere Liste bei jedem Fehler oder wenn
    fuer diesen Kanal keine Sendungen vorhanden sind."""
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
        if p["start"].date() in erlaubte_tage or p["stop"].date() in erlaubte_tage
    ]
