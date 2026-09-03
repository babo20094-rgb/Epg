"""Echte Programmdaten fuer Sport Klub HR (SK 1-12, 4K, Esports, Fight,
Golf) - AUTOMATISCH fuer jeden "HR|SK N"-Sender in sender.txt, als
Ergaenzung zu MojMaxTV (siehe mojmaxtv_epg.py).

Hintergrund: MojMaxTV (die normale HR-Quelle) fuehrt seit September 2026
GAR KEINEN "Sport Klub"-Kanal mehr in der eigenen Kanalliste (nur noch
Arena Sport 1-10 u.ae.) - fuer "HR|SK N" gab es dadurch nur noch den
generischen Kategorietext, kein echtes Programm mehr. sportklub.hr selbst
laedt sein TV-Programm per JS-Bundle nach (nicht direkt per HTTP-Request
scrapbar), daher wird hier stattdessen der bereits fertig aufbereitete,
oeffentliche XMLTV-Spiegel von epgshare01.online verwendet (community-
gepflegt, mehrfach taeglich aktualisiert, Quelle laut eigenem <url>-Tag
ist sportklub.hr selbst) - EINE komplette XMLTV-Datei mit allen 16
Sport-Klub-Kanaelen UND deren Sendungen, wird nur EINMAL pro Lauf
geladen und geparst (Modul-weiter Cache, exakt wie plutotv_epg.py),
danach werden alle "HR|SK N"-Sender lokal dagegen gematcht ohne weitere
Netzwerk-Aufrufe.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt der Download, das
Parsen oder die Kanalsuche fehl, bekommt der betroffene Sender in
generate_epg.py einfach die normale, kategoriebasierte generische
EPG-Generierung wie jeder andere Sender - dieses Modul darf einen Lauf
niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import gzip
import re
import xml.etree.ElementTree as ET

import requests

URL = "https://epgshare01.online/epgshare01/epg_ripper_SPORTKLUB1.xml.gz"

REQUEST_TIMEOUT_SEKUNDEN = 30

# Modul-weiter Cache: {"kanaele": [...], "programme": {kanal_id: [...]}}
_daten_cache = None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# "HR|SK 1".."HR|SK 12" (eigene sender.txt-Konvention, ohne HD/Portals-
# Zusatz) vs. z.B. "SK 1 HD (HR)"/"SK 4 HD HR (Portals)" bei
# epgshare01.online - ein normaler Kern-/Fuzzy-Abgleich waere hier
# gefaehrlich (kurze, fast identische Namen wie "SK 1"/"SK 10"/"SK 11").
# Stattdessen wird die Sender-Nummer explizit aus dem sender.txt-Namen
# extrahiert und exakt gegen die Nummer im epgshare01-Kanalnamen
# verglichen - kein Fehltreffer-Risiko.
_SK_NUMMER_PATTERN = re.compile(r"^SK\s*0*(\d+K?)$", re.IGNORECASE)
_KANAL_NUMMER_PATTERN = re.compile(r"^SK\s*0*(\d+K?)\b", re.IGNORECASE)

# "SK Esports"/"SK Fight"/"SK Golf" (ohne Nummer) - ebenfalls exakter
# Namens-Kern-Vergleich statt Fuzzy.
_SK_WORT_ALIASE = {
    "ESPORTS": "ESPORTS",
    "FIGHT": "FIGHT",
    "GOLF": "GOLF",
}


def _xml_laden():
    """Laedt und parst (und cached) die komplette Sport-Klub-XMLTV-Datei.
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

        print(f"SportKlub-EPG: {len(kanaele)} Kanaele, {len(programme)} Kanaele mit Sendungen geladen.")

        daten = {"kanaele": kanaele, "programme": programme}
        _daten_cache = daten
        return daten
    except Exception as e:
        print(f"SportKlub-EPG: Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _daten_cache = None
        return None


def _xmltv_zeit_parsen(text):
    """Parst das XMLTV-Zeitformat 'YYYYMMDDHHMMSS +ZZZZ' zu einem
    tz-aware datetime (UTC). None bei Parse-Fehler."""
    try:
        return datetime.strptime(text.strip(), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
    except Exception:
        return None


def sportklub_kanal_finden(kanalname):
    """Sucht den Sport-Klub-Kanal, der exakt zur sender.txt-Nummer/zum
    Wort-Alias (SK 1-12/4K/Esports/Fight/Golf) passt. Gibt die Kanal-ID
    zurueck oder None (kein Fehltreffer-Risiko: nur exakter Nummern-/
    Wort-Vergleich, kein Fuzzy-Abgleich)."""
    daten = _xml_laden()
    if not daten or not daten["kanaele"]:
        return None

    name = kanalname.strip()

    ziel_nummer = None
    treffer = _SK_NUMMER_PATTERN.match(name)
    if treffer:
        ziel_nummer = treffer.group(1).upper()
    else:
        wort = re.sub(r"^SK\s+", "", name, flags=re.IGNORECASE).strip().upper()
        ziel_nummer = _SK_WORT_ALIASE.get(wort)

    if not ziel_nummer:
        return None

    for kanal in daten["kanaele"]:
        kanal_treffer = _KANAL_NUMMER_PATTERN.match(kanal["name"].strip())
        if kanal_treffer and kanal_treffer.group(1).upper() == ziel_nummer:
            return kanal["site_id"]
        if ziel_nummer in _SK_WORT_ALIASE.values():
            kanal_wort = re.sub(r"^SK\s+", "", kanal["name"].strip(), flags=re.IGNORECASE)
            kanal_wort = kanal_wort.split(" ")[0].upper() if kanal_wort else ""
            if kanal_wort == ziel_nummer:
                return kanal["site_id"]

    return None


def sportklub_hole_programme(site_id, tage=2):
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
