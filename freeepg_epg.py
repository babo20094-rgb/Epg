"""Optionale, echte Programmdaten von free-epg.de - AUTOMATISCH als
LETZTER Fallback fuer BA-Sender (nach Telemach/mtel.ba/mymedia.ba/
mojtv.hr, siehe die Verarbeitungsbloecke in generate_epg.py), nur wenn
keine der anderen Quellen fuer diesen Sender etwas gefunden hat.

free-epg.de ("FreeEPG/2") ist ein kostenloses, offenes XMLTV-Bulk-
EPG-Projekt (kein Login, keine kommerzielle Rytec-Weiterverteilung wie
die abgelehnten ricxepg.nl/kodi-unlimited-support.de-Mirrors - die
Datei selbst weist sich im generator-info-url-Attribut als
"https://free-epg.de" aus). Anders als alle anderen Quellen dieses
Repos ist das kein Kanal-fuer-Kanal-API-Abruf, sondern EINE komplette
XMLTV-Datei pro Land mit allen Kanaelen UND allen Sendungen darin -
wird deshalb nur EINMAL pro Lauf komplett geladen und geparst
(Modul-weiter Cache), danach werden alle BA-Sender lokal dagegen
gematcht ohne weitere Netzwerk-Aufrufe.

Bewusst nur fuer BA eingebaut (nicht automatisch fuer alle Laender,
die free-epg.de anbietet) - der Nutzer hat das explizit so gewuenscht.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle
graceful auf None/[]/leere Ergebnisse statt zu werfen: schlaegt der
Download, das Parsen oder die Kanalsuche fehl, bekommt der betroffene
Sender in generate_epg.py einfach die normale, kategoriebasierte
generische EPG-Generierung wie jeder andere Sender - dieses Modul darf
einen Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import difflib
import gzip
import re
import xml.etree.ElementTree as ET

import requests

from epg_lib import normalisiere_sendername

URL_VORLAGE = "https://free-epg.de/api/epg/{land}.xml.gz"

REQUEST_TIMEOUT_SEKUNDEN = 30

# Modul-weiter Cache pro Land: {"kanaele": [...], "programme": {kanal_id: [...]}}
_daten_cache = {}


def _xml_laden(land):
    """Laedt und parst (und cached pro Land) die komplette free-epg.de-
    XMLTV-Datei. Gibt {"kanaele": [...], "programme": {id: [...]}}
    zurueck, oder None bei jedem Fehler (Netzwerk, HTTP-Status, kaputtes
    Gzip/XML)."""
    if land in _daten_cache:
        return _daten_cache[land]

    try:
        response = requests.get(
            URL_VORLAGE.format(land=land), timeout=REQUEST_TIMEOUT_SEKUNDEN
        )
        response.raise_for_status()
        rohbytes = response.content

        try:
            xml_bytes = gzip.decompress(rohbytes)
        except OSError:
            # Server liefert evtl. bereits entpackten Klartext (z.B.
            # wenn Content-Encoding: gzip schon von requests entpackt
            # wurde, oder die Datei entgegen der .gz-Endung kein
            # echtes Gzip ist).
            xml_bytes = rohbytes

        wurzel = ET.fromstring(xml_bytes)

        kanaele = []
        for kanal_tag in wurzel.findall("channel"):
            kanal_id = kanal_tag.get("id")
            name_tag = kanal_tag.find("display-name")
            name = name_tag.text.strip() if name_tag is not None and name_tag.text else ""
            if not kanal_id or not name:
                continue
            # Manche Eintraege haben ein Land-Praefix im Anzeigenamen
            # ("DE - WDR" statt "WDR") - das verfaelscht sonst den
            # Namensabgleich (z.B. wuerde "DDR" faelschlich auf
            # "DE - WDR" matchen, weil das "DE" im Praefix die
            # Aehnlichkeit erhoeht), deshalb hier entfernen.
            name = re.sub(r"^[A-Z]{2}\s*-\s*", "", name)
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

        daten = {"kanaele": kanaele, "programme": programme}
        _daten_cache[land] = daten
        return daten
    except Exception as e:
        print(f"FreeEPG-EPG: Laden/Parsen ({land}) fehlgeschlagen ({e}), ueberspringe.")
        _daten_cache[land] = None
        return None


def _xmltv_zeit_parsen(text):
    """Parst das XMLTV-Zeitformat 'YYYYMMDDHHMMSS +ZZZZ' zu einem
    tz-aware datetime (UTC). None bei Parse-Fehler."""
    try:
        return datetime.strptime(text.strip(), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
    except Exception:
        return None


# Kurze Namen (z.B. "K3", "TV1") duerfen NICHT per Teilstring-Abgleich
# matchen - sonst wuerde z.B. "TV1" in praktisch jedem laengeren
# Kanalnamen wie "TV18" oder "ETV1" stecken und zu Fehltreffern fuehren.
MIN_TEILSTRING_LAENGE = 5


def freeepg_kanal_finden(kanalname, land="ba"):
    """Sucht den free-epg.de-Kanal, der am besten zu kanalname passt, in
    drei Stufen: (1) exakter Abgleich nach normalisiere_sendername(),
    (2) Teilstring-Abgleich (ein Name steckt komplett im anderen, z.B.
    weil free-epg.de oder sender.txt Zusaetze wie "HD"/"FHD"/Ortsnamen
    fuehrt, die der jeweils andere nicht hat) - nur ab
    MIN_TEILSTRING_LAENGE Zeichen, um triviale Kurz-Treffer zu
    vermeiden, bei mehreren Kandidaten gewinnt der mit der geringsten
    Laengendifferenz, (3) unscharfer difflib-Abgleich wie bei den
    anderen Quellen. Gibt die Kanal-ID zurueck oder None."""
    daten = _xml_laden(land)
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

    if ziel_schluessel in name_index:
        return name_index[ziel_schluessel]

    if len(ziel_schluessel) >= MIN_TEILSTRING_LAENGE:
        kandidaten = []
        for schluessel, site_id in name_index.items():
            if len(schluessel) < MIN_TEILSTRING_LAENGE:
                continue
            if ziel_schluessel in schluessel or schluessel in ziel_schluessel:
                kandidaten.append((abs(len(schluessel) - len(ziel_schluessel)), site_id))
        if kandidaten:
            kandidaten.sort(key=lambda k: k[0])
            return kandidaten[0][1]

    aehnliche = difflib.get_close_matches(ziel_schluessel, name_index.keys(), n=1, cutoff=0.72)
    if aehnliche:
        return name_index[aehnliche[0]]

    return None


def freeepg_hole_programme(site_id, land="ba", tage=3):
    """Liefert die bereits geladenen Programmdaten fuer den gegebenen
    Kanal (site_id) aus dem Modul-Cache, begrenzt auf die naechsten
    `tage` Tage ab heute (UTC). Leere Liste bei jedem Fehler oder wenn
    fuer diesen Kanal keine Sendungen vorhanden sind."""
    if site_id is None:
        return []

    daten = _xml_laden(land)
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
