"""Echte Programmdaten fuer US-KABELNETZWERKE (nicht lokale Sender) ueber
den community-gepflegten XMLTV-Mirror epgshare01.online.

Hintergrund: TVGuide.com (tvguide_epg.py) deckt nur eine feste, kleine
nationale Grundaufstellung ab (~153 Kanaele, ueberwiegend die grossen
Broadcast-Networks) und tvpassport.com (tvpassport_epg.py) fuehrt
ueberwiegend LOKALE US-Sender pro Stadt/Call-Sign - beide Quellen decken
nationale KABELnetzwerke (A&E, FX, TCM, Nat Geo, TNT West, ...) kaum ab.
Von 198 in "US| ENTERTAINMENT" per TVGUIDE:-Praefix eingetragenen
Sendern fanden 135 dort keinen Treffer.

epgshare01.online/epg_ripper_US2.xml.gz (Quelle laut eigenem <url>-Tag:
Gracenote/tmsapi + tvpassport gemischt) fuehrt dagegen genau diese
nationalen Kabelnetzwerke inkl. echter Sendungsdaten (Titel, Beschreibung,
Jahr, Kategorie) - live verifiziert fuer TCM, Nat Geo, Nat Geo Wild,
Court TV, GSN, Travel Channel, USA Network, TNT/TBS/truTV/Syfy/HGTV/FX
(jeweils inkl. "(Pacific)"-Westfeed-Variante), Paramount Network u.a.

Kanalzuordnung laeuft bewusst NUR ueber exakten Namensabgleich (nach
normalisiere_sendername()) PLUS eine kleine, manuell verifizierte
Alias-Tabelle fuer Sender, deren sender.txt-Name vom epgshare01-
Anzeigenamen abweicht (z.B. "TCM HD" -> "Turner Classic Movies HD",
"NAT GEO HD" -> "National Geographic HD", "TNT WEST HD" -> "TNT HD
(Pacific)") - KEIN Fuzzy-/difflib-Abgleich, da bei ähnlich benannten,
aber inhaltlich komplett verschiedenen US-Kabelnetzwerken (siehe z.B.
den TCM/TSC-Fehltreffer bei tvpassport.com in dieser Session) ein
unscharfer Abgleich ein hohes Risiko fuer falsche Programmdaten hat.

Genau wie bei plutotv_epg.py/sportklub_epg.py/magenta_myteam_epg.py wird
die komplette XMLTV-Datei (~6 MB gepackt) nur EINMAL pro Lauf geladen und
lokal gematcht, kein API-Aufruf pro Kanal.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen - dieses Modul darf einen
Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import gzip
import re
import xml.etree.ElementTree as ET

import requests

from epg_lib import normalisiere_sendername

URL = "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz"

REQUEST_TIMEOUT_SEKUNDEN = 60

# Modul-weiter Cache: {"kanaele": [...], "programme": {kanal_id: [...]}}
_daten_cache = None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# Manuell verifizierte Alias-Aufloesung: sender.txt-Name (normalisiert)
# -> exakter epgshare01-Anzeigename. Jeder Eintrag wurde einzeln live
# gegen den echten Sendernamen geprueft (siehe CLAUDE.md), bevor er hier
# aufgenommen wurde - kein automatisches/geratenes Mapping.
_ALIAS = {
    "TCM HD": "Turner Classic Movies HD",
    "NAT GEO HD": "National Geographic HD",
    "NAT GEO WILD HD": "National Geographic Wild HD",
    "PARAMOUNT HD": "Paramount Network HD",
    "COURT TV HD": "Court TV",
    "GSN HD": "Game Show Network HD",
    "HSN": "Home Shopping Network",
    "OUTSIDE TV HD": "Outside Television HD",
    "STORY TV": "Story",
    "PIXL HD": "PixL",
    "EWTN CATHOLIC": "EWTN - Eternal Word Television Network HD",
    "FUSE MUSIC HD": "Fuse HD",
    "LAFF TV HD": "Laff",
    "LAFF TV  HD": "Laff",
    "LAW AND CRIME HD": "Law and Crime",
    "EL REY REBEL HD": "El Rey Network",
    "SPACE CITY HD": "Space City Home Network HD",
    "TBN": "Trinity Broadcasting Network HD",
    "TRAVEL CHANNEL HD": "The Travel Channel HD",
    # West-Feed-Sender: epgshare01 fuehrt die Westkueste-Variante unter
    # "(Pacific)" statt "WEST" - einzeln verifiziert, kein generisches
    # WEST->Pacific-Pattern (zu riskant, da nicht jeder Sender eine
    # Pacific-Variante hat).
    "BRAVO WEST HD": "Bravo (Pacific)",
    "DISCOVERY CHANNEL WEST": "The Discovery Channel HD (Pacific)",
    "FX WEST HD": "FX HD (Pacific)",
    "FXX WEST HD": "FXX HD (Pacific)",
    "HGTV WEST HD": "Home and Garden Television HD (Pacific)",
    "SYFY WEST HD": "Syfy HD (Pacific)",
    "TBS WEST HD": "TBS HD (Pacific)",
    "TLC WEST": "TLC HD (Pacific)",
    "TNT WEST HD": "TNT HD (Pacific)",
    "TRAVEL CHANNEL WEST HD": "The Travel Channel HD (Pacific)",
    "TRUTV WEST HD": "truTV HD (Pacific)",
    "USA NETWORK WEST HD": "USA Network HD (Pacific)",
}
_ALIAS_NORMALISIERT = {
    normalisiere_sendername(k): v for k, v in _ALIAS.items()
}


def _xml_laden():
    """Laedt und parst (und cached) die komplette epgshare01-US2-XMLTV-
    Datei. Gibt {"kanaele": [...], "programme": {id: [...]}} zurueck,
    oder ein leeres (aber nicht-None) Dict bei jedem Fehler (Netzwerk,
    HTTP-Status, kaputtes Gzip/XML) - verhindert wiederholte Download-
    Versuche bei dauerhaftem Fehler (siehe magenta_myteam_epg.py)."""
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
            if not kanal_id:
                continue

            start_roh = prog_tag.get("start")
            stop_roh = prog_tag.get("stop")
            if not start_roh or not stop_roh:
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

        print(f"EpgshareUS-EPG: {len(kanaele)} Kanaele, {len(programme)} Kanaele mit Sendungen geladen.")

        daten = {"kanaele": kanaele, "programme": programme}
        _daten_cache = daten
        return daten
    except Exception as e:
        print(f"EpgshareUS-EPG: Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _daten_cache = {"kanaele": [], "programme": {}}
        return _daten_cache


def _xmltv_zeit_parsen(text):
    """Parst das XMLTV-Zeitformat 'YYYYMMDDHHMMSS +ZZZZ' zu einem
    tz-aware datetime (UTC). None bei Parse-Fehler."""
    try:
        return datetime.strptime(text.strip(), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
    except Exception:
        return None


def epgshare_us_kanal_finden(kanalname):
    """Sucht den epgshare01-US2-Kanal, der zu kanalname passt - erst
    exakter Abgleich nach normalisiere_sendername(), dann die manuell
    verifizierte Alias-Tabelle (_ALIAS). KEIN Fuzzy-/difflib-Abgleich
    (siehe Modul-Docstring - zu hohes Fehltreffer-Risiko bei aehnlich
    benannten, aber verschiedenen US-Kabelnetzwerken). Gibt die
    site_id zurueck oder None."""
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

    if ziel_schluessel in name_index:
        return name_index[ziel_schluessel]

    alias_ziel = _ALIAS_NORMALISIERT.get(ziel_schluessel)
    if alias_ziel:
        alias_schluessel = normalisiere_sendername(alias_ziel)
        if alias_schluessel in name_index:
            return name_index[alias_schluessel]

    return None


def epgshare_us_hole_programme(site_id, tage=2):
    """Liefert die bereits geladenen Programmdaten fuer den gegebenen
    Kanal (site_id) aus dem Modul-Cache, begrenzt auf die naechsten
    `tage` Tage ab heute (UTC). Leere Liste bei jedem Fehler oder wenn
    keine Sendungen vorhanden sind."""
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
        if (p["start"].date() in erlaubte_tage or p["stop"].date() in erlaubte_tage)
    ]
