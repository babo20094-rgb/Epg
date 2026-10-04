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
import threading
import xml.etree.ElementTree as ET

import requests
from quellen import _http

URL = "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz"

REQUEST_TIMEOUT_SEKUNDEN = 60

# Modul-weiter Cache: {"kanaele": [...], "programme": {kanal_id: [...]}}
_daten_cache = None
# Schuetzt den Erstzugriff auf _daten_cache: wird diese Quelle aus
# mehreren Threads gleichzeitig angefragt (siehe _parallel_abrufen() in
# generate_epg.py), wuerden ohne diese Sperre ALLE Threads gleichzeitig
# "noch nicht geladen" sehen und die ~60-MB-Datei jeder fuer sich parallel
# herunterladen, statt dass nur einer laedt und die anderen warten -
# September 2026 als vermutliche Ursache mehrerer externer Workflow-
# Abbrueche identifiziert (siehe docs/HISTORIE.md).
_daten_cache_lock = threading.Lock()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_CALLSIGN_PATTERN = re.compile(r"\b([KW][A-Z0-9]{2,4})\b")


_HAUPTKANAL_NAME = re.compile(r"^[KW][A-Z0-9]{2,4}(-DT)?$")
_PROGRAMM_BLOCK = re.compile(rb'<programme [^>]*?channel="([^"]*)"[^>]*>.*?</programme>', re.S)


def _kanaele_aus_kopf(wurzel):
    kanaele = []
    for kanal_tag in wurzel.findall("channel"):
        kanal_id = kanal_tag.get("id")
        name_tag = kanal_tag.find("display-name")
        name = name_tag.text.strip() if name_tag is not None and name_tag.text else ""
        if not kanal_id or not name:
            continue
        kanaele.append({"site_id": kanal_id, "name": name})
    return kanaele


def _programm_parsen(prog_tag):
    """Ein <programme>-Element -> Sendungs-Dict oder None."""
    start_roh = prog_tag.get("start")
    stop_roh = prog_tag.get("stop")
    if not start_roh or not stop_roh:
        return None
    start = _xmltv_zeit_parsen(start_roh)
    stop = _xmltv_zeit_parsen(stop_roh)
    if start is None or stop is None:
        return None
    titel_tag = prog_tag.find("title")
    titel = titel_tag.text.strip() if titel_tag is not None and titel_tag.text else ""
    if not titel:
        return None
    beschr_tag = prog_tag.find("desc")
    beschreibung = beschr_tag.text.strip() if beschr_tag is not None and beschr_tag.text else ""
    icon_tag = prog_tag.find("icon")
    bild = icon_tag.get("src") if icon_tag is not None else None
    return {"title": titel, "beschreibung": beschreibung, "bild": bild, "start": start, "stop": stop}


def _xml_laden():
    """Laedt und parst (und cached) die komplette epgshare01-US-LOCALS1-
    XMLTV-Datei. Gibt {"kanaele": [...], "programme": {id: [...]}} zurueck,
    oder ein leeres (aber nicht-None) Dict bei jedem Fehler (Netzwerk,
    HTTP-Status, kaputtes Gzip/XML)."""
    global _daten_cache

    if _daten_cache is not None:
        return _daten_cache

    with _daten_cache_lock:
        # Erneut pruefen: ein anderer Thread koennte das Laden bereits
        # erledigt haben, waehrend dieser Thread auf die Sperre wartete.
        if _daten_cache is not None:
            return _daten_cache

        try:
            response = _http.mit_retry(requests.get, URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
            response.raise_for_status()
            rohbytes = response.content

            try:
                xml_bytes = gzip.decompress(rohbytes)
            except OSError:
                xml_bytes = rohbytes

            # Die entpackte Datei ist ~540 MB gross (557.000 Sendungen fuer
            # 4.456 Kanaele). Alles per ET zu parsen kostete ~75 s CPU im
            # gemeinsamen Interpreter (Run 959: 648 s Wanduhr, andere
            # Threads standen derweil). Benoetigt werden nur Kanaele, die
            # epgshare_us_locals_kanal_finden() treffen kann (Call-Sign
            # bzw. Call-Sign-DT) - nur deren Sendungen werden geparst.
            kanaele = []
            programme = {}
            gefiltert = False
            roh_bloecke = {}
            erstes_prog = xml_bytes.find(b"<programme")
            if erstes_prog > 0:
                kopf = ET.fromstring(xml_bytes[:erstes_prog] + b"</tv>")
                kanaele = _kanaele_aus_kopf(kopf)
                brauchbar = {k["site_id"] for k in kanaele if _HAUPTKANAL_NAME.match(k["name"].upper())}
                for treffer in _PROGRAMM_BLOCK.finditer(xml_bytes, erstes_prog):
                    kanal_id = treffer.group(1).decode("utf-8", "replace")
                    if kanal_id not in brauchbar:
                        continue
                    gefiltert = True
                    # Rohbloecke nur merken; geparst wird erst bei Bedarf
                    # (epgshare_us_locals_hole_programme), also nur fuer die
                    # tatsaechlich angefragten Kanaele.
                    roh_bloecke.setdefault(kanal_id, []).append(treffer.group(0))

            if not gefiltert:
                # Fallback (Dateiformat unerwartet / nichts gefunden): wie
                # frueher komplett per ET parsen.
                wurzel = ET.fromstring(xml_bytes)
                kanaele = _kanaele_aus_kopf(wurzel)
                programme = {}
                for prog_tag in wurzel.findall("programme"):
                    kanal_id = prog_tag.get("channel")
                    eintrag = _programm_parsen(prog_tag) if kanal_id else None
                    if eintrag is not None:
                        programme.setdefault(kanal_id, []).append(eintrag)

            for eintraege in programme.values():
                eintraege.sort(key=lambda s: s["start"])

            print(f"EpgshareUS-Locals-EPG: {len(kanaele)} Kanaele, {len(roh_bloecke) if gefiltert else len(programme)} Kanaele mit Sendungen geladen.")

            daten = {"kanaele": kanaele, "programme": programme, "roh": roh_bloecke}
            _daten_cache = daten
            return daten
        except Exception as e:
            print(f"EpgshareUS-Locals-EPG: Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
            _daten_cache = {"kanaele": [], "programme": {}, "roh": {}}
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

    eintraege = daten["programme"].get(site_id)
    if eintraege is None:
        with _daten_cache_lock:
            eintraege = daten["programme"].get(site_id)
            if eintraege is None:
                eintraege = []
                for block in daten.get("roh", {}).get(site_id, []):
                    eintrag = _programm_parsen(ET.fromstring(block))
                    if eintrag is not None:
                        eintraege.append(eintrag)
                eintraege.sort(key=lambda s: s["start"])
                daten["programme"][site_id] = eintraege
    if not eintraege:
        return []

    heute = datetime.now(timezone.utc).date()
    erlaubte_tage = {heute + timedelta(days=i) for i in range(tage)}

    return [
        p for p in eintraege
        if (p["start"].date() in erlaubte_tage or p["stop"].date() in erlaubte_tage)
    ]
