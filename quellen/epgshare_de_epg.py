"""Optionale, echte Programmdaten aus den epgshare01-Sammelfeeds DE1/AT1/CH1
- AUTOMATISCH als Stufe der DE-Kaskade (kein sender.txt-Praefix noetig),
VOR tvmovie.de/hoerzu.de (siehe generate_epg.py).

Hintergrund (Diagnose-Workflow "Diagnose tvmovie-hoerzu", Oktober 2026):
tvmovie.de/hoerzu.de fragen jeden Sender einzeln ab und laufen dabei
regelmaessig in Rate-Limits (429/503, mehrere Minuten Wartezeit pro
Lauf). Die epgshare01-Feeds liefern dieselben Sender als EINE Datei pro
Land (DE1 ~4 MB, AT1 ~4 MB, CH1 ~6 MB, je ca. 5 Tage im Voraus) - nur
EINMAL pro Lauf geladen und geparst (Modul-weiter Cache), danach lokal
gematcht ohne weitere Netzwerk-Aufrufe.

Platzhalter wie "Sendepause" (z.B. 4-Stunden-Bloecke bei Sky-Kanaelen, wenn
kein Spiel laeuft) sind KORREKTE Daten und werden bewusst uebernommen:
tvmovie/hoerzu ordnen z.B. "Sky Sport Bundesliga 3-10" faelschlich dem Kanal
"Bundesliga 1" zu und wuerden dort falsche Spiele einblenden.

Kanalabgleich ABSICHTLICH ohne unscharfen difflib-Abgleich (nur exakter
und eindeutiger Kern-Abgleich plus kleine ALIAS-Tabelle): die Feeds
enthalten viele fremdsprachige/regionale Kanaele (v.a. CH1), bei denen
ein Fuzzy-Treffer leicht den falschen Sender erwischen wuerde.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt ein Download oder
das Parsen fehl, laufen tvmovie.de/hoerzu.de wie bisher weiter - dieses
Modul darf einen Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import gzip
import re
import xml.etree.ElementTree as ET

import threading
import requests
from quellen import _http

from epg_lib import normalisiere_sendername, normalisiere_sendername_kern, kern_index_aufbauen

# Reihenfolge = Prioritaet bei gleichnamigen Kanaelen in mehreren Feeds.
FEEDS = ["DE1", "AT1", "CH1"]
URL = "https://epgshare01.online/epgshare01/epg_ripper_{feed}.xml.gz"

REQUEST_TIMEOUT_SEKUNDEN = 120

# Kanaele mit weniger Sendungen sind Platzhalter/Dummy-Eintraege.
MIN_SENDUNGEN_PRO_KANAL = 10

# Playlist-Name -> epgshare01-Name (jeweils nach normalisiere_sendername()).
ALIAS = {
    "ARD": "DASERSTE",
    "KABEL1": "KABELEINS",
    "RTL2": "RTLZWEI",
    "RTLII": "RTLZWEI",
    # Sky: Playlist-Schreibweise vs. epgshare01-Schreibweise
    "SKYCINEMAHIGHLIGHT": "SKYCINEMAHIGHLIGHTS",
    "SKYSPORTSF1": "SKYSPORTF1",
}

# Modul-weiter Cache: {"kanaele": [{"site_id", "name"}], "programme": {id: [...]}}
_daten_cache = None
# Schuetzt den Erstzugriff auf _daten_cache (siehe _parallel_abrufen() in
# generate_epg.py: sonst wuerden mehrere Threads dieselben Dateien
# gleichzeitig herunterladen).
_daten_cache_lock = threading.Lock()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def _xmltv_zeit_parsen(text):
    """Parst das XMLTV-Zeitformat 'YYYYMMDDHHMMSS +ZZZZ' zu einem
    tz-aware datetime (UTC). None bei Parse-Fehler."""
    try:
        return datetime.strptime(text.strip(), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
    except Exception:
        return None


def _feed_parsen(feed, xml_bytes):
    """Parst EINEN Feed -> (kanaele, programme). site_id = '<FEED>:<kanal_id>'."""
    wurzel = ET.fromstring(xml_bytes)

    programme = {}
    for prog_tag in wurzel.findall("programme"):
        kanal_id = prog_tag.get("channel")
        start = _xmltv_zeit_parsen(prog_tag.get("start") or "")
        stop = _xmltv_zeit_parsen(prog_tag.get("stop") or "")
        if not kanal_id or start is None or stop is None or stop <= start:
            continue

        titel_tag = prog_tag.find("title")
        titel = titel_tag.text.strip() if titel_tag is not None and titel_tag.text else ""
        if not titel:
            continue

        beschr_tag = prog_tag.find("desc")
        beschreibung = beschr_tag.text.strip() if beschr_tag is not None and beschr_tag.text else ""

        icon_tag = prog_tag.find("icon")
        bild = icon_tag.get("src") if icon_tag is not None else None

        programme.setdefault(f"{feed}:{kanal_id}", []).append({
            "title": titel,
            "beschreibung": beschreibung,
            "bild": bild,
            "start": start,
            "stop": stop,
        })

    for eintraege in programme.values():
        eintraege.sort(key=lambda s: s["start"])

    kanaele = []
    for kanal_tag in wurzel.findall("channel"):
        kanal_id = kanal_tag.get("id")
        site_id = f"{feed}:{kanal_id}"
        if not kanal_id or len(programme.get(site_id, [])) < MIN_SENDUNGEN_PRO_KANAL:
            continue
        namen = [d.text.strip() for d in kanal_tag.findall("display-name") if d.text and d.text.strip()]
        # Kanal-ID ohne Laender-Endung (".de"/".at"/".ch") als weiterer Name,
        # z.B. "kabel.eins.de" -> "kabel eins"
        namen.append(re.sub(r"\.(de|at|ch)$", "", kanal_id).replace(".", " "))
        for name in namen:
            kanaele.append({"site_id": site_id, "name": name})

    return kanaele, programme


def _xml_laden():
    """Laedt und parst (und cached) alle epgshare01-Feeds aus FEEDS.
    Gibt {"kanaele": [...], "programme": {id: [...]}} zurueck. Ein
    fehlgeschlagener Feed wird uebersprungen, die anderen bleiben nutzbar;
    Fehlschlaege werden mitgecached (leeres Ergebnis statt Wiederholung
    fuer jeden einzelnen Sender)."""
    global _daten_cache

    if _daten_cache is not None:
        return _daten_cache

    with _daten_cache_lock:
        if _daten_cache is not None:
            return _daten_cache

        kanaele, programme = [], {}
        for feed in FEEDS:
            try:
                response = _http.mit_retry(
                    requests.get, URL.format(feed=feed), headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN
                )
                response.raise_for_status()
                rohbytes = response.content
                try:
                    xml_bytes = gzip.decompress(rohbytes)
                except OSError:
                    xml_bytes = rohbytes

                feed_kanaele, feed_programme = _feed_parsen(feed, xml_bytes)
                kanaele.extend(feed_kanaele)
                programme.update(feed_programme)
                print(f"EpgshareDE-EPG ({feed}): {len({k['site_id'] for k in feed_kanaele})} Kanaele mit Sendungen geladen.")
            except Exception as e:
                print(f"EpgshareDE-EPG ({feed}): Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")

        # Indizes nur EINMAL pro Lauf bauen (nicht bei jeder Kanalsuche neu).
        # Je normalisiertem Namen gewinnt der erste Feed in FEEDS.
        name_index, kern_quelle = {}, {}
        for kanal in kanaele:
            schluessel = normalisiere_sendername(kanal["name"])
            if schluessel and schluessel not in name_index:
                name_index[schluessel] = kanal["site_id"]
                kern_quelle[schluessel] = {"name": kanal["name"], "site_id": kanal["site_id"]}
        # Kern-Index aus den ORIGINAL-Namen (Wortgrenzen fuer HD/SD-Suffixe
        # noetig) der priorisierten Eintraege: je Name genau ein Kanal, damit
        # gleichnamige Kanaele in mehreren Feeds nicht als "mehrdeutig"
        # aus dem Kern-Index fallen.
        kern_index = kern_index_aufbauen(list(kern_quelle.values()), "name", "site_id")

        _daten_cache = {
            "kanaele": kanaele, "programme": programme,
            "name_index": name_index, "kern_index": kern_index,
        }
        return _daten_cache


def epgshare_de_kanal_finden(kanalname):
    """Sucht den epgshare01-Kanal zu kanalname - exakter Abgleich nach
    normalisiere_sendername() (inkl. ALIAS), dann eindeutiger Kern-Abgleich
    ohne HD/FHD/UHD/SD/HEVC. KEIN unscharfer Abgleich. Gibt die site_id
    ('<FEED>:<kanal_id>') zurueck oder None. Bei gleichnamigen Kanaelen in
    mehreren Feeds gewinnt der erste Feed in FEEDS."""
    daten = _xml_laden()
    if not daten or not daten["kanaele"]:
        return None

    name_index = daten["name_index"]
    kern_index = daten["kern_index"]

    # Klammerzusatz der Playlist ignorieren, z.B. "SKY SPORT 10 HD (NUR WAEHREND
    # DER LIVE SPIELE)" -> "SKY SPORT 10 HD".
    kanalname = re.sub(r"\s*\([^)]*\)", "", kanalname).strip()
    exakt = normalisiere_sendername(kanalname)
    kern = normalisiere_sendername_kern(kanalname)
    for schluessel in (exakt, kern):
        schluessel = ALIAS.get(schluessel, schluessel)
        if schluessel in name_index:
            return name_index[schluessel]
    kern = ALIAS.get(kern, kern)
    return kern_index.get(kern) if kern else None


def epgshare_de_hole_programme(site_id, tage=2):
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
