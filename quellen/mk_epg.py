"""Echte Programmdaten fuer Nordmazedonien (Land "MK" in sender.txt) -
AUTOMATISCH fuer jeden ganz normal eingetragenen "MK|..."-Sender, kein
eigenes Praefix noetig (gleiches Prinzip wie der BA/ME-Telemach- bzw.
RS-mts.rs-Autoabgleich).

Hintergrund: Fuer Mazedonien gab es lange keine bekannte, tatsaechlich
erreichbare echte EPG-Quelle (MaxTV GO/spectar.tv tot, A1s eigene
"Xplore TV"-API unter epggw.a1.mk existiert zwar, ist aber per IP
gesperrt - siehe Recherche-Notizen). iptv-epg.org stellt unter
https://iptv-epg.org/files/epg-mk.xml eine oeffentliche, loginfreie
XMLTV-Sammeldatei mit allen mazedonischen Kanaelen bereit (109 Kanaele,
~16.000 Sendungen, ~6 Tage Vorschau) - live verifiziert (u.a. MRT 1 mit
echten, plausiblen Titeln/Staffel-Episode-Angaben in mazedonischer
Sprache).

Die Datei wird EINMAL pro Lauf komplett geladen und geparst (Modul-
weiter Cache, gleiches Muster wie plutotv_epg.py/sportklub_epg.py),
danach werden alle "MK|..."-Sender lokal dagegen gematcht ohne weitere
Netzwerk-Aufrufe. Kanalzuordnung nutzt sowohl die (meist lateinische)
Kanal-ID als auch den Anzeigenamen (nach Entfernen des "MK - "-Praefix)
als Kandidaten - viele Anzeigenamen sind kyrillisch (z.B. "MK - МРТ 1"),
die eigene sender.txt nutzt aber lateinische Namen ("MK|MRT 1"); die
Kanal-ID ("MRT1.mk") ist in diesen Faellen die verwertbare lateinische
Variante. Erst exakter Abgleich nach normalisiere_sendername(), dann
ein Kern-Abgleich ohne HD/FHD/UHD/SD, zuletzt ein unscharfer difflib-
Abgleich (gleiche Vorgehensweise wie bei allen anderen automatischen
Quellen in diesem Projekt).

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

from epg_lib import normalisiere_sendername, normalisiere_sendername_kern

URL = "https://iptv-epg.org/files/epg-mk.xml"

REQUEST_TIMEOUT_SEKUNDEN = 30

# Modul-weiter Cache: {"kanaele": [...], "programme": {kanal_id: [...]}}
_daten_cache = None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_MK_PRAEFIX = re.compile(r"^MK\s*-\s*", re.IGNORECASE)


def _xml_laden():
    """Laedt und parst (und cached) die komplette mazedonische XMLTV-
    Sammeldatei. Gibt {"kanaele": [...], "programme": {id: [...]}}
    zurueck - bei jedem Fehler (Netzwerk, HTTP-Status, kaputtes XML) ein
    leeres, aber nicht-None Dict (verhindert wiederholte Download-
    Versuche bei einem dauerhaften Fehler, siehe sportklub_epg.py)."""
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

        print(f"MK-EPG: {len(kanaele)} Kanaele, {len(programme)} Kanaele mit Sendungen geladen.")

        daten = {"kanaele": kanaele, "programme": programme}
        _daten_cache = daten
        return daten
    except Exception as e:
        print(f"MK-EPG: Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _daten_cache = {"kanaele": [], "programme": {}}
        return _daten_cache


def _xmltv_zeit_parsen(text):
    """Parst das XMLTV-Zeitformat 'YYYYMMDDHHMMSS +ZZZZ' zu einem
    tz-aware datetime (UTC). None bei Parse-Fehler."""
    try:
        return datetime.strptime(text.strip(), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
    except Exception:
        return None


def mk_kanal_finden(kanalname):
    """Sucht den iptv-epg.org-Kanal, der am besten zu kanalname passt.
    Jeder Quell-Kanal liefert bis zu zwei Namens-Kandidaten fuer den
    Index: die (meist lateinische) Kanal-ID ohne ".mk"-Endung und den
    Anzeigenamen ohne "MK - "-Praefix (oft kyrillisch - normalisiere_
    sendername() liefert dafuer einen leeren Schluessel und wird beim
    Indexaufbau uebersprungen, kein Fehltreffer-Risiko). Erst exakter
    Abgleich, dann Kern-Abgleich ohne HD/FHD/UHD/SD, zuletzt unscharfer
    difflib-Abgleich (cutoff 0.72). Gibt die Kanal-ID zurueck oder
    None."""
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
        kandidaten = [_MK_PRAEFIX.sub("", kanal["name"])]
        id_ohne_endung = re.sub(r"\.mk$", "", kanal["site_id"], flags=re.IGNORECASE)
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
        return name_index[aehnliche[0]]

    return None


def mk_hole_programme(site_id, tage=3):
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
