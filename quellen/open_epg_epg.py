"""Echte Programmdaten von open-epg.com (oeffentliche, loginfreie
laenderweise XMLTV.GZ-Dateien, z.B. https://www.open-epg.com/files/
croatia.xml.gz) - bewusst NUR fuer eine kleine, feste Whitelist
einzelner Sender eingebaut, die bei ALLEN anderen Quellen (Telemach/
mtel.ba/klix.ba/mts.rs/MojMaxTV/SportKlub/Siol/TvProfil.net/
tvprogramdanas.net/DE-Kaskade) durchgefallen sind (Stand September
2026: "Animal Planet"/"MrezaZG" fuer HR sowie 14 DE/JOYN/PRIME-Sender,
siehe _WHITELIST) - KEIN generisches Matching gegen die volle, mehrere
hundert Kanaele grosse Landesliste, um das Risiko ungewollter Treffer
bei bereits anderweitig abgedeckten Sendern (insbesondere Arena Sport/
Sport Klub) komplett auszuschliessen.

Jede Landes-XMLTV.GZ-Datei wird trotzdem nur EINMAL pro Lauf
heruntergeladen und geparst (gecached) - auch wenn nur ein einzelner
Kanal daraus gebraucht wird, gibt es keinen separaten Download pro
Kanal/Tag wie bei Telemach/mtel.ba.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen - dieses Modul darf einen
Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import gzip
import io
import re
import xml.etree.ElementTree as ET

import requests

from epg_lib import normalisiere_sendername

REQUEST_TIMEOUT_SEKUNDEN = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# Land -> open-epg.com-Dateiname (siehe https://www.open-epg.com/files/).
_LAND_DATEI = {
    "HR": "croatia.xml.gz",
    "BA": "bosnia.xml.gz",
    "DE": "germany.xml.gz",
}

# ENGE Whitelist: normalisierter Sendername -> (Land, open-epg.com-
# Kanal-ID). NUR Sender aufnehmen, die nachweislich bei KEINER anderen
# Quelle echte Daten liefern - siehe Modul-Docstring. Nicht einfach um
# weitere Sender erweitern, ohne das vorher genauso geprueft zu haben
# (sonst droht Doppel-/Fehltreffer-Risiko wie bei einem vollen
# Kanalabgleich).
_WHITELIST = {
    normalisiere_sendername("Animal Planet"): ("HR", "AnimalPlanet.hr"),
    normalisiere_sendername("MrezaZG"): ("HR", "MrezaZG.hr"),
    # DE/JOYN/PRIME - September 2026 geprueft: bei KEINER Stufe der
    # bestehenden DE-Kaskade (deswird.org/Pluto TV/tvmovie.de/hoerzu.de/
    # Joyn-VOD/search.ch/iptv-epg.org, siehe generate_epg.py) und auch
    # nicht bei tvprogramdanas.net gefunden, aber bei open-epg.com/
    # germany.xml.gz mit gut gefuellten Sendeplaenen (25-166 Sendungen).
    normalisiere_sendername("Big Brother Classics"): ("DE", "BigBrotherClassics.de"),
    normalisiere_sendername("Curiosity Now"): ("DE", "CuriosityNow.de"),
    normalisiere_sendername("FIFA+"): ("DE", "FIFAplus.de"),
    normalisiere_sendername("Ladykracher"): ("DE", "Ladykracher.de"),
    normalisiere_sendername("MovieSphere"): ("DE", "MovieSphere.de"),
    normalisiere_sendername("Niederbayern TV Deggendorf-Straubing"): (
        "DE", "NiederbayernTVDeggendorfStraubing.de",
    ),
    normalisiere_sendername("Qello Concerts by Stingray"): ("DE", "QelloConcertsbyStingray.de"),
    normalisiere_sendername("Spiegel TV Konflikte"): ("DE", "SPIEGELTVKonflikte.de"),
    normalisiere_sendername("SWR Baden-Württemberg"): ("DE", "SWRBadenWuerttemberg.de"),
    normalisiere_sendername("SWR Rheinland-Pfalz"): ("DE", "SWRRheinlandPfalz.de"),
    normalisiere_sendername("TemporaTV"): ("DE", "TemporaTV.de"),
    normalisiere_sendername("Terra Mater Wild"): ("DE", "TerraMaterWILD.de"),
    normalisiere_sendername("WDR Köln"): ("DE", "WDRKoeln.de"),
    normalisiere_sendername("XITE Hits"): ("DE", "XITEHits.de"),
}

_datei_cache = {}


def open_epg_kanal_finden(kanalname):
    """Nur ein exakter Abgleich gegen die enge Whitelist oben - gibt bei
    Treffer (land, kanal_id) zurueck, sonst None. Bewusst KEIN Fuzzy-
    Anteil und KEIN Abgleich gegen die volle Landesliste."""
    schluessel = normalisiere_sendername(kanalname)
    if not schluessel:
        return None
    return _WHITELIST.get(schluessel)


def _land_datei_holen(land):
    """Laedt (und cached) die komplette, entpackte XMLTV-Datei fuer
    `land` als ElementTree-Wurzel. None bei jedem Fehler."""
    if land in _datei_cache:
        return _datei_cache[land]

    dateiname = _LAND_DATEI.get(land)
    if not dateiname:
        _datei_cache[land] = None
        return None

    url = f"https://www.open-epg.com/files/{dateiname}"

    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        rohdaten = gzip.GzipFile(fileobj=io.BytesIO(response.content)).read()
        wurzel = ET.fromstring(rohdaten)
        _datei_cache[land] = wurzel
        return wurzel
    except Exception as e:
        print(f"Open-EPG-EPG: Datei fuer Land {land} fehlgeschlagen ({type(e).__name__}), ueberspringe.")
        _datei_cache[land] = None
        return None


def _xmltv_zeit_parsen(text):
    match = re.match(r"^(\d{14})\s*([+-]\d{4})$", (text or "").strip())
    if not match:
        return None
    zeitpunkt = datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
    vorzeichen = 1 if match.group(2)[0] == "+" else -1
    versatz_minuten = vorzeichen * (int(match.group(2)[1:3]) * 60 + int(match.group(2)[3:5]))
    return zeitpunkt.replace(tzinfo=timezone.utc) - timedelta(minutes=versatz_minuten)


def open_epg_hole_programme(land, kanal_id, tage=3):
    """Holt Programmdaten fuer den gegebenen open-epg.com-Kanal
    (kanal_id) aus der gecachten Landes-XMLTV-Datei, beschraenkt auf
    die naechsten `tage` Tage ab heute (UTC). Liefert eine nach
    Startzeit sortierte Liste von {"title", "beschreibung", "bild",
    "start", "stop"} - leere Liste bei jedem Fehler."""
    if not land or not kanal_id:
        return []

    wurzel = _land_datei_holen(land)
    if wurzel is None:
        return []

    grenze = datetime.now(timezone.utc) + timedelta(days=tage)

    ergebnis = []
    try:
        for programme in wurzel.findall("programme"):
            if programme.get("channel") != kanal_id:
                continue
            start = _xmltv_zeit_parsen(programme.get("start", ""))
            stop = _xmltv_zeit_parsen(programme.get("stop", ""))
            if start is None or stop is None or stop <= start:
                continue
            if start > grenze:
                continue
            titel_el = programme.find("title")
            desc_el = programme.find("desc")
            titel = titel_el.text.strip() if titel_el is not None and titel_el.text else ""
            if not titel:
                continue
            ergebnis.append({
                "title": titel,
                "beschreibung": desc_el.text.strip() if desc_el is not None and desc_el.text else "",
                "bild": None,
                "start": start,
                "stop": stop,
            })
    except Exception as e:
        print(f"Open-EPG-EPG: Parsen fuer Kanal {kanal_id} ({land}) fehlgeschlagen ({type(e).__name__}), ueberspringe.")
        return []

    ergebnis.sort(key=lambda s: s["start"])
    return ergebnis
