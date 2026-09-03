"""Echte Programmdaten fuer Joyns eigene, thematische "ODC"-VOD-Kanaele
(z.B. "Ancient Aliens", "DMAX Macher", "Derrick", "Charmed") - als
zusaetzlicher, letzter Versuch in der DE-Kaskade (siehe generate_epg.py),
NACH deswird.org/Pluto TV/tvmovie.de/hoerzu.de/Samsung TV Plus.

Hintergrund: Viele sender.txt-Zeilen unter den Laendern DE/JOYN/PRIME/WOW
sind genau diese Art durchnummerierter Themen-/Serien-"Sender" (deutsch
synchronisierte Serien/Doku-Kanaele, die rund um die Uhr eine feste Serie
zeigen) - deswird.org & Co. fuehren nur die "grossen" TV-Sender, nicht
diese Nischenkanaele. Joyn selbst bietet dafuer ein eigenes VOD-EPG an
("ODC" = "On Demand Channel"), das ueber denselben community-gepflegten
Drittanbieter-Host (kodi-unlimited-support.de) wie samsungtv_epg.py als
fertige XMLTV-Datei bereitsteht (~100 Kanaele).

Genau wie plutotv_epg.py/sportklub_epg.py wird die komplette XMLTV-Datei
nur EINMAL pro Lauf geladen und geparst (Modul-weiter Cache), danach
lokal gematcht ohne weitere Netzwerk-Aufrufe. Kanalzuordnung laeuft
bewusst NUR ueber einen exakten Namensabgleich (normalisiere_sendername(),
kein Fuzzy-Anteil) - die Kanalnamen sind kurze, spezifische Serien-/
Sendungstitel (z.B. "Charmed"), bei denen ein unscharfer Abgleich zu
schnell auf einen unpassenden anderen Kanal matchen wuerde.

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

from epg_lib import normalisiere_sendername

URL = "https://kodi-unlimited-support.de/iptv/epg/joyn_vod_de_guide.xml.gz"

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
    """Laedt und parst (und cached) die komplette Joyn-VOD-XMLTV-Datei.
    Gibt {"kanaele": [...], "programme": {id: [...]}} zurueck - auch bei
    jedem Fehler (Netzwerk, HTTP-Status, kaputtes Gzip/XML), dann als
    leeres, aber nicht-None Ergebnis (kein erneuter Download-Versuch bei
    jedem einzelnen Sender)."""
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

        print(f"Joyn-VOD-EPG: {len(kanaele)} Kanaele, {len(programme)} Kanaele mit Sendungen geladen.")

        daten = {"kanaele": kanaele, "programme": programme}
        _daten_cache = daten
        return daten
    except Exception as e:
        print(f"Joyn-VOD-EPG: Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _daten_cache = {"kanaele": [], "programme": {}}
        return _daten_cache


def _xmltv_zeit_parsen(text):
    """Parst das XMLTV-Zeitformat 'YYYYMMDDHHMMSS +ZZZZ' zu einem
    tz-aware datetime (UTC). None bei Parse-Fehler."""
    try:
        return datetime.strptime(text.strip(), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
    except Exception:
        return None


def joyn_vod_kanal_finden(kanalname):
    """Sucht den Joyn-VOD-Kanal per EXAKTEM Namensabgleich (nach
    normalisiere_sendername(), kein Fuzzy-Anteil - die Kanalnamen sind
    kurze, spezifische Serien-/Sendungstitel, bei denen ein unscharfer
    Abgleich zu schnell falsch matchen wuerde). Gibt die Kanal-ID zurueck
    oder None."""
    daten = _xml_laden()
    if not daten or not daten["kanaele"]:
        return None

    ziel_schluessel = normalisiere_sendername(kanalname)
    if not ziel_schluessel:
        return None

    name_index = {}
    for kanal in daten["kanaele"]:
        schluessel = normalisiere_sendername(kanal["name"])
        if schluessel:
            name_index.setdefault(schluessel, kanal["site_id"])

    return name_index.get(ziel_schluessel)


def joyn_vod_hole_programme(site_id, tage=2):
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
