"""Echte Programmdaten fuer Montenegro (Land "MO"/"MNG"/"ME"/"CG" in
sender.txt) - AUTOMATISCH als LETZTER Fallback nach Telemach/klix.ba/
MagentaTV ME (siehe magentatv_me_epg.py), kein eigenes Praefix noetig.

iptv-epg.org stellt unter https://iptv-epg.org/files/epg-me.xml eine
oeffentliche, loginfreie XMLTV-Sammeldatei mit allen montenegrinischen
Kanaelen bereit (212 Kanaele, ~45.000 Sendungen, ~6 Tage Vorschau) -
live verifiziert: alle 212 Kanaele mit aktuellen Sendungen, u.a. der
oeffentlich-rechtliche Nationalsender "RTCG 1"/"RTCG 2". Deckt sich
zum grossen Teil bereits mit MagentaTV ME, ergaenzt aber ca. 8 sonst
ungedeckte Sender (z.B. "Gradska TV", "MNEsport 1/3", "TV Pobeda").

Exakt dasselbe Muster wie mk_epg.py (gleicher Anbieter, gleiches
Dateiformat, nur "epg-me.xml" statt "epg-mk.xml" und "ME - "-Praefix
statt "MK - "). Wird EINMAL pro Lauf komplett geladen und geparst
(Modul-weiter Cache), danach werden alle Sender lokal dagegen
gematcht ohne weitere Netzwerk-Aufrufe.

Degradiert an JEDER Stelle graceful auf None/[]/leere Ergebnisse statt
zu werfen: schlaegt Download, Parsen oder Kanalsuche fehl, bekommt der
betroffene Sender in generate_epg.py einfach die normale, kategorie-
basierte generische EPG-Generierung wie jeder andere Sender - dieses
Modul darf einen Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import difflib
import gzip
import re
import xml.etree.ElementTree as ET

import requests
from quellen import _http

from epg_lib import normalisiere_sendername, normalisiere_sendername_kern

URL = "https://iptv-epg.org/files/epg-me.xml"

REQUEST_TIMEOUT_SEKUNDEN = 30

# Modul-weiter Cache: {"kanaele": [...], "programme": {kanal_id: [...]}}
_daten_cache = None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_ME_PRAEFIX = re.compile(r"^ME\s*-\s*", re.IGNORECASE)


def _xml_laden():
    """Laedt und parst (und cached) die komplette montenegrinische
    XMLTV-Sammeldatei. Gibt {"kanaele": [...], "programme": {id: [...]}}
    zurueck - bei jedem Fehler (Netzwerk, HTTP-Status, kaputtes XML) ein
    leeres, aber nicht-None Dict (verhindert wiederholte Download-
    Versuche bei einem dauerhaften Fehler, siehe mk_epg.py)."""
    global _daten_cache

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

        wurzel = ET.fromstring(xml_bytes)

        kanaele = []
        for kanal_tag in wurzel.findall("channel"):
            kanal_id = kanal_tag.get("id")
            name_tag = kanal_tag.find("display-name")
            name = name_tag.text.strip() if name_tag is not None and name_tag.text else ""
            if not kanal_id:
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
            if not titel or titel.strip().lower() == "no data":
                # Manche Kanaele liefern in dieser Quelle selbst nur den
                # Platzhalter-Titel "No Data" statt echter Sendungen -
                # das ist kein echter Programminhalt, wird uebersprungen
                # (Sender faellt dann auf den naechsten Fallback zurueck).
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

        print(f"ME-EPG: {len(kanaele)} Kanaele, {len(programme)} Kanaele mit Sendungen geladen.")

        daten = {"kanaele": kanaele, "programme": programme}
        _daten_cache = daten
        return daten
    except Exception as e:
        print(f"ME-EPG: Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _daten_cache = {"kanaele": [], "programme": {}}
        return _daten_cache


def _xmltv_zeit_parsen(text):
    """Parst das XMLTV-Zeitformat 'YYYYMMDDHHMMSS +ZZZZ' zu einem
    tz-aware datetime (UTC). None bei Parse-Fehler."""
    try:
        return datetime.strptime(text.strip(), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
    except Exception:
        return None


def me_kanal_finden(kanalname):
    """Sucht den iptv-epg.org-Kanal, der am besten zu kanalname passt.
    Jeder Quell-Kanal liefert bis zu zwei Namens-Kandidaten fuer den
    Index: die Kanal-ID ohne ".me"-Endung und den Anzeigenamen ohne
    "ME - "-Praefix. Erst exakter Abgleich, dann Kern-Abgleich ohne
    HD/FHD/UHD/SD, zuletzt unscharfer difflib-Abgleich (cutoff 0.72).
    Gibt die Kanal-ID zurueck oder None."""
    daten = _xml_laden()
    if not daten or not daten["kanaele"]:
        return None

    ziel_schluessel = normalisiere_sendername(kanalname)
    if not ziel_schluessel:
        return None

    name_index = {}
    kern_index = {}
    kern_mehrdeutig = set()
    for kanal in daten["kanaele"]:
        kandidaten = [_ME_PRAEFIX.sub("", kanal["name"])]
        id_ohne_endung = re.sub(r"\.me$", "", kanal["site_id"], flags=re.IGNORECASE)
        kandidaten.append(id_ohne_endung)

        for kandidat in kandidaten:
            schluessel = normalisiere_sendername(kandidat)
            if schluessel:
                name_index.setdefault(schluessel, kanal["site_id"])

            kern = normalisiere_sendername_kern(kandidat)
            if kern:
                if kern in kern_index and kern_index[kern] != kanal["site_id"]:
                    kern_mehrdeutig.add(kern)
                kern_index.setdefault(kern, kanal["site_id"])

    if ziel_schluessel in name_index:
        return name_index[ziel_schluessel]

    ziel_kern = normalisiere_sendername_kern(kanalname)
    if ziel_kern and ziel_kern in kern_index and ziel_kern not in kern_mehrdeutig:
        return kern_index[ziel_kern]

    aehnliche = difflib.get_close_matches(ziel_schluessel, name_index.keys(), n=1, cutoff=0.72)
    if aehnliche:
        treffer = aehnliche[0]
        # Sehr kurze Sendernamen sind fuer den reinen Aehnlichkeits-
        # Score zu riskant (siehe mk_epg.py-Praezedenzfall "K3"/"SK3") -
        # ein echtes Kurzform-Match bleibt aber erlaubt, wenn der kurze
        # Name ein reiner Praefix des Treffers ist (oder umgekehrt).
        if len(ziel_schluessel) <= 3 and not (
            treffer.startswith(ziel_schluessel) or ziel_schluessel.startswith(treffer)
        ):
            return None
        return name_index[treffer]

    return None


def me_hole_programme(site_id, tage=3):
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
