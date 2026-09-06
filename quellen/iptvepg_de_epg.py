"""Echte Programmdaten fuer Deutschland (Land "DE"/"JOYN"/"PRIME"/"WOW"
in sender.txt) - SIEBTER und letzter Fallback der DE-Kaskade, nach
deswird.org/Pluto TV/tvmovie.de/hoerzu.de/Joyn-VOD/search.ch. Kein
eigenes Praefix noetig.

iptv-epg.org stellt unter https://iptv-epg.org/files/epg-de.xml eine
oeffentliche, loginfreie XMLTV-Sammeldatei mit deutschen Kanaelen
bereit (438 Kanaele) - live gegen die bestehende DE-Kaskade abgeglichen
und dabei u.a. gefunden: BR HD, alle 10 WDR-Lokalstudios (Aachen,
Bielefeld, Bonn, Dortmund, Duisburg, Duesseldorf, Essen, Muenster,
Siegen, Wuppertal), MDR Sachsen/Sachsen-Anhalt/Thueringen, NDR Hamburg/
Mecklenburg-Vorpommern/Schleswig-Holstein, rbb Berlin/Brandenburg,
SWR BW, DF1, Nitro, Zee One, Sat.1 Bayern, TVA Ostbayern, Oberpfalz TV,
TV Mainfranken/Oberfranken, tv.ingolstadt, MS Golf 1/2, ClipMyHorse.TV,
GEO DE, Artflix - keiner dieser Sender war zuvor durch die bestehende
DE-Kaskade abgedeckt (deswird.org kennt fuer WDR/NDR/MDR/SWR/RBB/BR/HR
nur den bundesweiten Sammelkanal, kein Regionalstudio).

Die Datei wird EINMAL pro Lauf komplett geladen und geparst (Modul-
weiter Cache, gleiches Muster wie plutotv_epg.py/mk_epg.py), danach
werden alle DE/JOYN/PRIME/WOW-Sender lokal dagegen gematcht ohne
weitere Netzwerk-Aufrufe. Kanalzuordnung nutzt sowohl die Kanal-ID
(ohne ".de"-Endung) als auch den Anzeigenamen (nach Entfernen des
"DE - "-Praefix) als Kandidaten, erst exakter Abgleich nach
normalisiere_sendername(), dann ein Kern-Abgleich ohne HD/FHD/UHD/SD,
zuletzt ein unscharfer difflib-Abgleich (gleiche Vorgehensweise wie bei
allen anderen automatischen Quellen in diesem Projekt).

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

URL = "https://iptv-epg.org/files/epg-de.xml"

REQUEST_TIMEOUT_SEKUNDEN = 45

# Modul-weiter Cache: {"kanaele": [...], "programme": {kanal_id: [...]}}
_daten_cache = None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_DE_PRAEFIX = re.compile(r"^DE\s*-\s*", re.IGNORECASE)


def _xml_laden():
    """Laedt und parst (und cached) die komplette deutsche XMLTV-
    Sammeldatei. Gibt {"kanaele": [...], "programme": {id: [...]}}
    zurueck - bei jedem Fehler (Netzwerk, HTTP-Status, kaputtes XML) ein
    leeres, aber nicht-None Dict (verhindert wiederholte Download-
    Versuche bei einem dauerhaften Fehler)."""
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

        kanaele = []
        programme = {}

        kontext = ET.iterparse(__import__("io").BytesIO(xml_bytes), events=("end",))
        for _, elem in kontext:
            if elem.tag == "channel":
                kanal_id = elem.get("id")
                name_tag = elem.find("display-name")
                name = name_tag.text.strip() if name_tag is not None and name_tag.text else ""
                if kanal_id:
                    kanaele.append({"site_id": kanal_id, "name": name})
                elem.clear()
            elif elem.tag == "programme":
                kanal_id = elem.get("channel")
                start_roh = elem.get("start")
                stop_roh = elem.get("stop")
                if kanal_id and start_roh and stop_roh:
                    start = _xmltv_zeit_parsen(start_roh)
                    stop = _xmltv_zeit_parsen(stop_roh)
                    titel_tag = elem.find("title")
                    titel = titel_tag.text.strip() if titel_tag is not None and titel_tag.text else ""
                    if start is not None and stop is not None and titel:
                        beschr_tag = elem.find("desc")
                        beschreibung = beschr_tag.text.strip() if beschr_tag is not None and beschr_tag.text else ""
                        icon_tag = elem.find("icon")
                        bild = icon_tag.get("src") if icon_tag is not None else None
                        programme.setdefault(kanal_id, []).append({
                            "title": titel,
                            "beschreibung": beschreibung,
                            "bild": bild,
                            "start": start,
                            "stop": stop,
                        })
                elem.clear()

        for eintraege in programme.values():
            eintraege.sort(key=lambda s: s["start"])

        print(f"IPTV-EPG.org-DE-EPG: {len(kanaele)} Kanaele, {len(programme)} Kanaele mit Sendungen geladen.")

        daten = {"kanaele": kanaele, "programme": programme}
        _daten_cache = daten
        return daten
    except Exception as e:
        print(f"IPTV-EPG.org-DE-EPG: Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _daten_cache = {"kanaele": [], "programme": {}}
        return _daten_cache


def _xmltv_zeit_parsen(text):
    """Parst das XMLTV-Zeitformat 'YYYYMMDDHHMMSS +ZZZZ' zu einem
    tz-aware datetime (UTC). None bei Parse-Fehler."""
    try:
        return datetime.strptime(text.strip(), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
    except Exception:
        return None


def iptvepg_de_kanal_finden(kanalname):
    """Sucht den iptv-epg.org-Kanal, der am besten zu kanalname passt.
    Jeder Quell-Kanal liefert bis zu zwei Namens-Kandidaten fuer den
    Index: die Kanal-ID ohne ".de"-Endung und den Anzeigenamen ohne
    "DE - "-Praefix. Erst exakter Abgleich, dann Kern-Abgleich ohne
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
        kandidaten = [_DE_PRAEFIX.sub("", kanal["name"])]
        id_ohne_endung = re.sub(r"\.de$", "", kanal["site_id"], flags=re.IGNORECASE)
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


def iptvepg_de_hole_programme(site_id, tage=2):
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
