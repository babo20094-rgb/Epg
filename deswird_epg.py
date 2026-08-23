"""Optionale, echte Programmdaten von deswird.org (Deutschland) -
AUTOMATISCH als ERSTE/primaere Quelle in der DE-Kaskade (vor Pluto TV,
tvmovie.de, hoerzu.de, Samsung TV Plus), kein eigenes sender.txt-Praefix
noetig.

Datenquelle ist die frei zugaengliche, loginfreie XMLTV-Datei
"Tempest EPG Generator" (https://deswird.org/iptv/GuideFull.xml.gz) -
EINE komplette Datei mit knapp 800 deutschen Kanaelen UND allen
Sendungen darin (Titel, Sub-Title/Episodentitel, ausfuehrliche
Beschreibung mit Jahr/Staffel/Episode), wird nur EINMAL pro Lauf
geladen und geparst (Modul-weiter Cache), danach werden alle DE-Sender
lokal dagegen gematcht ohne weitere Netzwerk-Aufrufe.

Deckt mehrere Tage im Voraus ab (deutlich mehr als Pluto TV/tvmovie.de/
hoerzu.de/Samsung TV Plus, die nur 1-2 Tage liefern).

Im EPG-Raster soll NUR der Titel (plus ggf. ein kompakter
Episodentitel) erscheinen, keine ausformulierten Magazin-Teaser -
_episodentitel_kompakt() filtert deshalb lange/mehrteilige Sub-Titles
(Semikolon, sehr lang) heraus, bevor sie an den Titel angehaengt
werden. Die volle Beschreibung bleibt unveraendert im <desc>-Feld
(Detailansicht) erhalten, siehe _schreibe_echte_programme() in
generate_epg.py, das ohnehin nie ein eigenes <sub-title>-Tag schreibt.

Im Gegensatz zu den anderen echten EPG-Quellen dieses Repos ist das
eine kleine, nicht-offizielle Drittanbieter-Seite ohne erkennbare
Stabilitaetsgarantie (siehe CLAUDE.md) - degradiert deshalb nach dem
gleichen Zero-Risk-Prinzip an JEDER Stelle graceful auf None/[]/leere
Ergebnisse statt zu werfen: schlaegt der Download, das Parsen oder die
Kanalsuche fehl, bekommt der betroffene Sender in generate_epg.py
einfach die normale, kategoriebasierte generische EPG-Generierung wie
jeder andere Sender - dieses Modul darf einen Lauf niemals zum Absturz
bringen.
"""

import re
from datetime import datetime, timedelta, timezone

import gzip
import xml.etree.ElementTree as ET

import requests

from epg_lib import normalisiere_sendername, normalisiere_sendername_kern, kanal_index_suchen

URL = "https://deswird.org/iptv/GuideFull.xml.gz"

REQUEST_TIMEOUT_SEKUNDEN = 60

EPISODENTITEL_MAX_LAENGE = 60

# Modul-weiter Cache: {"kanaele": [...], "programme": {kanal_id: [...]}}
_daten_cache = None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def _episodentitel_kompakt(untertitel):
    """True, wenn untertitel wie ein kompakter Episodentitel aussieht
    (nicht wie ein ausformulierter Magazin-Teaser mit mehreren Themen,
    z.B. "u.a.: Radfahrer entpuppt sich als Entführer; ..."). Solche
    Teaser sollen NICHT an den Titel angehaengt werden - nur kurze,
    echte Episodentitel."""
    if not untertitel:
        return False
    if len(untertitel) > EPISODENTITEL_MAX_LAENGE:
        return False
    if ";" in untertitel:
        return False
    if untertitel.lower().startswith("u.a"):
        return False
    return True


def _xml_laden():
    """Laedt und parst (und cached) die komplette deswird.org-DE-XMLTV-
    Datei. Gibt {"kanaele": [...], "programme": {id: [...]}} zurueck,
    oder None bei jedem Fehler (Netzwerk, HTTP-Status, kaputtes
    Gzip/XML)."""
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

            untertitel_tag = prog_tag.find("sub-title")
            untertitel = (
                untertitel_tag.text.strip()
                if untertitel_tag is not None and untertitel_tag.text
                else ""
            )
            if _episodentitel_kompakt(untertitel):
                titel = f"{titel}: {untertitel}"

            beschr_tag = prog_tag.find("desc")
            beschreibung = ""
            if beschr_tag is not None and beschr_tag.text:
                beschreibung = re.sub(r"\s+", " ", beschr_tag.text).strip()

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

        print(f"Deswird-EPG: {len(kanaele)} Kanaele, {len(programme)} Kanaele mit Sendungen geladen.")

        daten = {"kanaele": kanaele, "programme": programme}
        _daten_cache = daten
        return daten
    except Exception as e:
        print(f"Deswird-EPG: Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _daten_cache = None
        return None


def _xmltv_zeit_parsen(text):
    """Parst das XMLTV-Zeitformat 'YYYYMMDDHHMMSS +ZZZZ' zu einem
    tz-aware datetime (UTC). None bei Parse-Fehler."""
    try:
        return datetime.strptime(text.strip(), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
    except Exception:
        return None


def _de_id_bevorzugen(bestehende_id, neue_id):
    """deswird.org fuehrt fuer manche Sendernamen (z.B. "Cartoon
    Network") mehrere, unterschiedliche Feeds unter identischem
    Anzeigenamen (nur die Kanal-ID unterscheidet sich, z.B.
    "CartoonNetwork.de" vs. "CartoonNetwork.ch" vs. eine dritte,
    kuerzere ID ohne Laenderkuerzel) - ohne Vorzugsregel wuerde der
    normale Namens-/Kern-Index das als mehrdeutig verwerfen und der
    riskante difflib-Fallback koennte einen komplett falschen,
    aehnlich benannten Kanal treffen (siehe CLAUDE.md: Sky Cinema
    Special/Highlights-Verwechslung). Eine explizit mit ".de"
    gekennzeichnete ID ist fuer diese DE-spezifische Quelle eindeutig
    die richtige Wahl und wird deshalb bevorzugt, statt den Namen ganz
    zu verwerfen."""
    if neue_id.lower().endswith(".de") and not bestehende_id.lower().endswith(".de"):
        return neue_id
    return bestehende_id


def deswird_kanal_finden(kanalname):
    """Sucht den deswird.org-Kanal, der am besten zu kanalname passt -
    erst exakter Abgleich nach normalisiere_sendername(), dann ein
    eindeutiger Kern-Abgleich ohne HD/FHD/UHD/SD, zuletzt unscharfer
    difflib-Abgleich (siehe epg_lib.kanal_index_suchen()). Bei
    mehreren Kanaelen mit identischem (Kern-)Namen wird die explizit
    mit ".de" gekennzeichnete Kanal-ID bevorzugt (siehe
    _de_id_bevorzugen()) statt den Treffer als mehrdeutig zu verwerfen.
    Gibt die Kanal-ID zurueck oder None."""
    daten = _xml_laden()
    if not daten or not daten["kanaele"]:
        return None

    name_index = {}
    for kanal in daten["kanaele"]:
        schluessel = normalisiere_sendername(kanal["name"])
        if not schluessel:
            continue
        if schluessel in name_index:
            name_index[schluessel] = _de_id_bevorzugen(name_index[schluessel], kanal["site_id"])
        else:
            name_index[schluessel] = kanal["site_id"]

    kern_roh = {}
    kern_mehrdeutig = set()
    for kanal in daten["kanaele"]:
        kern = normalisiere_sendername_kern(kanal["name"])
        if not kern:
            continue
        site_id = kanal["site_id"]
        if kern not in kern_roh:
            kern_roh[kern] = site_id
        elif kern_roh[kern] != site_id:
            if site_id.lower().endswith(".de") != kern_roh[kern].lower().endswith(".de"):
                # Genau einer der beiden ist explizit ".de" - eindeutig
                # bevorzugt, keine echte Mehrdeutigkeit.
                kern_roh[kern] = _de_id_bevorzugen(kern_roh[kern], site_id)
            else:
                # Beide oder keiner ".de" - echte Mehrdeutigkeit wie
                # bisher, kein Fallback-Risiko eingehen.
                kern_mehrdeutig.add(kern)
    kern_index = {k: v for k, v in kern_roh.items() if k not in kern_mehrdeutig}

    return kanal_index_suchen(kanalname, name_index, kern_index)


def deswird_hole_programme(site_id, tage=3):
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
