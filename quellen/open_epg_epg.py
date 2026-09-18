"""Echte Programmdaten von oeffentlichen, loginfreien laenderweisen
XMLTV.GZ-Sammel-Dateien verschiedener Anbieter (open-epg.com,
epgshare01.online) - bewusst NUR fuer eine kleine, feste Whitelist
einzelner Sender eingebaut, die bei ALLEN anderen Quellen (Telemach/
mtel.ba/klix.ba/mts.rs/MojMaxTV/SportKlub/Siol/TvProfil.net/
tvprogramdanas.net/DE-Kaskade) durchgefallen sind (Stand September
2026: "Animal Planet"/"MrezaZG" fuer HR, 14 DE/JOYN/PRIME-Sender sowie
18 RS-Sender, siehe _WHITELIST) - KEIN generisches Matching gegen die
volle, mehrere hundert Kanaele grosse Landesliste, um das Risiko
ungewollter Treffer bei bereits anderweitig abgedeckten Sendern
(insbesondere Arena Sport/Sport Klub/Arena Premium) komplett
auszuschliessen.

Jedes Land ist auf eine volle URL gemappt (_LAND_URL) statt auf einen
festen Anbieter - dadurch koennen unterschiedliche Laender bei
unterschiedlichen Anbietern liegen, je nachdem, wo die jeweils
ergiebigste Datei gefunden wurde (z.B. HR/DE bei open-epg.com, RS bei
epgshare01.online, das fuer RS deutlich mehr Sender abdeckt).

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
from quellen import _http

from epg_lib import normalisiere_sendername

REQUEST_TIMEOUT_SEKUNDEN = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# Land -> volle URL der jeweiligen laenderweisen XMLTV.GZ-Sammel-Datei.
_LAND_URL = {
    "HR": "https://www.open-epg.com/files/croatia.xml.gz",
    "DE": "https://www.open-epg.com/files/germany.xml.gz",
    # epgshare01.online statt open-epg.com: deckt fuer RS deutlich mehr
    # (18 statt 8) sonst nirgends abgedeckte Sender ab (SBB-Quelle,
    # epg.sbb.rs) - siehe Modul-Docstring.
    "RS": "https://epgshare01.online/epgshare01/epg_ripper_RS1.xml.gz",
    # BA: open-epg.com/bosnia.xml.gz brachte 0 Treffer (September 2026
    # geprueft) - stattdessen epgshare01.online/epg_ripper_BA1.xml.gz
    # (Telemach-BA-Mirror, 254 Kanaele), daraus per Display-Name-
    # Abgleich (nicht erfundene IDs) zwei echte Treffer verifiziert.
    "BA": "https://epgshare01.online/epgshare01/epg_ripper_BA1.xml.gz",
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
    # RS - September 2026 geprueft: bei KEINER Stufe der bestehenden
    # RS-Kaskade (mts.rs) und auch nicht bei TvProfil.net/
    # tvprogramdanas.net gefunden, aber bei epgshare01.online/
    # epg_ripper_RS1.xml.gz (SBB-Quelle) mit gut gefuellten
    # Sendeplaenen (53-172 Sendungen). "Arena Premium"-Kanaele in
    # derselben Datei bewusst NICHT aufgenommen (gehoeren zur
    # Arena-Sport-Markenfamilie, die unangetastet bleiben soll).
    normalisiere_sendername("AMC HD"): ("RS", "AMC.HD.(RS).rs"),
    normalisiere_sendername("Animal Planet HD"): ("RS", "Animal.Planet.HD.(RS).rs"),
    normalisiere_sendername("E! Entertainment"): ("RS", "E!.Entertainment.(RS).rs"),
    normalisiere_sendername("Happy"): ("RS", "Happy.(RS).rs"),
    normalisiere_sendername("HBO 2 HD"): ("RS", "HBO.2.HD.(RS).rs"),
    normalisiere_sendername("HBO 3 HD"): ("RS", "HBO.3.HD.(RS).rs"),
    normalisiere_sendername("IDJKids HD"): ("RS", "IDJKids.HD.(RS).rs"),
    normalisiere_sendername("K::CN 1"): ("RS", "K::CN.1.rs"),
    normalisiere_sendername("Lov i Ribolov"): ("RS", "Lov.i.Ribolov.(RS).rs"),
    normalisiere_sendername("Premier League TV"): ("RS", "Premier.League.TV.rs"),
    normalisiere_sendername("Prva plus"): ("RS", "Prva.plus.(RS).rs"),
    normalisiere_sendername("RTS 1 HD"): ("RS", "RTS.1.HD.rs"),
    normalisiere_sendername("RTS 2 HD"): ("RS", "RTS.2.HD.rs"),
    normalisiere_sendername("RTS 3 HD"): ("RS", "RTS.3.HD.rs"),
    normalisiere_sendername("Sandzak TV"): ("RS", "Sandzak.TV.rs"),
    normalisiere_sendername("Star"): ("RS", "Star.rs"),
    normalisiere_sendername("STAR HD"): ("RS", "STAR.HD.(RS).rs"),
    normalisiere_sendername("LFCTV"): ("RS", "LFCTV.rs"),
    # "NOVA BH BACKUP" (BA) - eigener sender.txt-Name, NICHT identisch
    # mit "NOVA BH" (das laeuft schon ueber Telemach) - in derselben
    # RS1-Datei als "Nova BH HD (BIH)" gefunden, 137 Sendungen, bei
    # keiner anderen Quelle abgedeckt.
    normalisiere_sendername("NOVA BH BACKUP"): ("RS", "Nova.BH.HD.(BIH).rs"),
    # BA - September 2026 per Display-Name-Abgleich in epg_ripper_BA1.xml.gz
    # gefunden (168 Sendungen), bei keiner anderen Quelle abgedeckt.
    normalisiere_sendername("N1 BH"): ("BA", "N1.HD.(BH)/(BIH).ba"),
    normalisiere_sendername("N1 BH HD"): ("BA", "N1.HD.(BH)/(BIH).ba"),
    # "Hayat 2" (echte Sendung "7plus", Hayat-TV-Talkshow) = Hayat Plus.
    normalisiere_sendername("Hayat Plus"): ("BA", "Hayat.2.ba"),
    # "RTV HIT" (Inhalt bestaetigt Brcko-Bezug) = Hit TV/Hit Brcko -
    # alle drei sender.txt-Schreibweisen abdecken.
    normalisiere_sendername("Hit TV"): ("BA", "RTV.HIT.ba"),
    normalisiere_sendername("Hit Brcko"): ("BA", "RTV.HIT.ba"),
    normalisiere_sendername("Hit Televizija Brcko"): ("BA", "RTV.HIT.ba"),
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

    url = _LAND_URL.get(land)
    if not url:
        _datei_cache[land] = None
        return None

    try:
        response = _http.mit_retry(requests.get, url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
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
