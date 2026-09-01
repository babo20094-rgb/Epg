"""Optionale, echte Programmdaten von den (HTML-gescrapten) Sender-Seiten
von tvpassport.com (US).

Genau wie tvguide_epg.py ist diese Quelle AUSSCHLIESSLICH opt-in ueber das
"TVPASSPORT:"-Praefix in sender.txt - es gibt hier bewusst KEIN
automatisches Matching gegen bestehende sender.txt-Zeilen.

Im Unterschied zu TVGuide.com (eine einzige, feste nationale
Grundaufstellung, siehe tvguide_epg.py) deckt tvpassport.com rund 19.000
einzelne LOKALE US-Sender-Seiten pro Stadt/Call-Sign ab (z. B.
"FOX (KFFX) Yakima, WA") - genau die Art lokaler Affiliate-Sender, die
TVGuide.com's nationale Liste nicht kennt.

Statt diese ~19.000 Seiten bei jedem Lauf live zu crawlen (das waere ein
massiver, unverhaeltnismaessiger Netzwerk-Aufwand), wird eine bereits vom
iptv-org/epg-Projekt selbst gecrawlte, statische Kanalliste
("tvpassport_kanalliste.xml", im Repo-Root neben sender.txt) EINMALIG pro
Lauf lokal geparst und im Speicher gecached - das kostet KEINEN einzigen
Netzwerk-Request, egal wie viele TVPASSPORT:-Zeilen in sender.txt stehen.
Nur der eigentliche Programmabruf (pro tatsaechlich getroffenem Kanal)
macht einen echten HTTP-Request an die Live-Sender-Seite.

Portiert aus dem config.js-Site-Plugin "tvpassport.com" des iptv-org/epg-
Projekts (nur der Programmabruf-/Parsing-Teil; die Kanalliste selbst wird
NICHT live gecrawlt, siehe oben - das extra HEAD-Request-Redirect-Following
des Originals wird bewusst NICHT portiert, ein 404/Redirect ist einfach ein
normaler Fehlschlag wie bei jeder anderen Quelle).

Da hier HTML-Struktur statt einer stabilen JSON-API gescrapt wird, ist
dieses Modul prinzipbedingt anfaelliger fuer Breaking Changes bei einem
Website-Redesign als z. B. Telemach/mtel/mts.rs (genau wie arena_epg.py) -
degradiert aber nach demselben Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt Kanalsuche oder
Programmabruf fehl, bekommt der betroffene Sender in generate_epg.py
einfach die normale, kategoriebasierte generische EPG-Generierung wie
jeder andere Sender - dieses Modul darf einen Lauf niemals zum Absturz
bringen.
"""

import difflib
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from epg_lib import normalisiere_sendername

BASE_URL = "https://www.tvpassport.com/tv-listings/stations"
BILD_BASE_URL = "https://cdn.tvpassport.com/image/show/960x540"

STANDARD_TIMEZONE = "America/New_York"

REQUEST_TIMEOUT_SEKUNDEN = 20

# Die statische Kanalliste liegt im selben Verzeichnis wie dieses Modul
# (Repo-Root), unabhaengig vom aktuellen Arbeitsverzeichnis des Prozesses.
_KANALLISTE_PFAD = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "tvpassport_kanalliste.xml"
)

# Modul-weiter Cache: die statische Kanalliste wird nur einmal pro Lauf
# geparst (reiner lokaler Dateizugriff, kein Netzwerk-Request).
_kanalliste_cache = None


def _lade_statische_kanalliste():
    """Parst (und cached) die im Repo mitgelieferte statische
    tvpassport_kanalliste.xml als Liste von {"site_id":..., "name":...}.
    Leere Liste bei jedem Fehler (Datei fehlt/kaputt) - degradiert
    graceful, auch wenn die Datei normalerweise immer vorhanden ist."""
    global _kanalliste_cache
    if _kanalliste_cache is not None:
        return _kanalliste_cache

    try:
        import xml.etree.ElementTree as ET

        baum = ET.parse(_KANALLISTE_PFAD)
        wurzel = baum.getroot()

        kanaele = []
        for element in wurzel.findall("channel"):
            site_id = element.get("site_id")
            name = (element.text or "").strip()
            if not site_id or not name:
                continue
            kanaele.append({"site_id": site_id, "name": name})

        _kanalliste_cache = kanaele
        return kanaele
    except Exception as e:
        print(f"TVPassport-EPG: Statische Kanalliste ({_KANALLISTE_PFAD}) fehlgeschlagen ({e}), ueberspringe.")
        _kanalliste_cache = []
        return []


def tvpassport_hole_kanalliste():
    """Oeffentlicher Wrapper: liefert die gecachte statische Kanalliste,
    macht KEINEN Netzwerk-Request (reiner lokaler Dateizugriff)."""
    return _lade_statische_kanalliste()


def tvpassport_kanal_finden(kanalname):
    """Sucht den TVPassport-Kanal, der am besten zu kanalname passt - erst
    exakter Abgleich nach normalisiere_sendername(), sonst unscharfer
    difflib-Abgleich (gleiche Vorgehensweise wie die anderen Quellen).
    Gibt die vollstaendige site_id (inkl. "/<numerische-id>") zurueck oder
    None."""
    kanaele = tvpassport_hole_kanalliste()
    if not kanaele:
        return None

    ziel_schluessel = normalisiere_sendername(kanalname)
    if not ziel_schluessel:
        return None

    name_index = {}
    for kanal in kanaele:
        schluessel = normalisiere_sendername(kanal["name"])
        if schluessel:
            name_index.setdefault(schluessel, kanal["site_id"])

    if ziel_schluessel in name_index:
        return name_index[ziel_schluessel]

    aehnliche = difflib.get_close_matches(ziel_schluessel, name_index.keys(), n=1, cutoff=0.72)
    if aehnliche:
        return name_index[aehnliche[0]]

    return None


def _timezone_aus_seite(soup):
    """Liest die ausgewaehlte Option von '#timezone_selector' aus, faellt
    bei Fehlern oder unbekannter IANA-Zone auf America/New_York zurueck."""
    try:
        select = soup.find(id="timezone_selector")
        if select is not None:
            option = select.find("option", selected=True)
            if option is not None and option.get("value"):
                try:
                    return ZoneInfo(option.get("value"))
                except Exception:
                    pass
    except Exception:
        pass
    return ZoneInfo(STANDARD_TIMEZONE)


def _tag_seite_holen(site_id, tag):
    # site_id muss im vollen Format "<slug>/<numerische-id>" uebergeben
    # werden - die Website leitet seit einem Redesign jede URL ohne die
    # numerische ID auf eine generische Platzhalterseite um (identischer
    # Inhalt fuer JEDEN Kanal, statt eines Fehlers/leeren Ergebnisses).
    datum_str = tag.strftime("%Y-%m-%d")
    url = f"{BASE_URL}/{site_id}/{datum_str}"
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"TVPassport-EPG: Seitenabruf ({url}) fehlgeschlagen ({e}), ueberspringe Tag.")
        return None


def _tag_parsen(soup, tag):
    tz = _timezone_aus_seite(soup)

    ergebnis = []
    for item in soup.select(".station-listings .list-group-item"):
        try:
            start_text = item.get("data-st")
            dauer_text = item.get("data-duration")
            if not start_text or not dauer_text:
                continue

            start_lokal = datetime.strptime(start_text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
            dauer_minuten = int(dauer_text)

            start = start_lokal.astimezone(ZoneInfo("UTC"))
            stop = (start_lokal + timedelta(minutes=dauer_minuten)).astimezone(ZoneInfo("UTC"))

            showname = (item.get("data-showname") or "").strip()
            episodetitel = (item.get("data-episodetitle") or "").strip()

            if showname in ("Movie", "Cinéma"):
                titel = episodetitel or showname
            else:
                titel = showname

            if not titel:
                continue

            beschreibung = (item.get("data-description") or "").strip()

            bild_datei = (item.get("data-showpicture") or "").strip()
            bild = f"{BILD_BASE_URL}/{bild_datei}" if bild_datei else None

            ergebnis.append({
                "title": titel,
                "beschreibung": beschreibung,
                "bild": bild,
                "start": start,
                "stop": stop,
            })
        except Exception:
            continue

    return ergebnis


def tvpassport_hole_programme(site_id, tage=2):
    """Holt Programmdaten fuer den gegebenen TVPassport-Kanal (site_id im
    Format "<slug>/<numerische-id>") fuer `tage` aufeinanderfolgende Tage
    ab heute. Liefert eine nach Startzeit sortierte, deduplizierte Liste
    von {"title", "beschreibung", "bild", "start", "stop"} (UTC, tz-aware)
    - leere Liste bei jedem Fehler."""
    if not site_id:
        return []

    alle_sendungen = []
    gesehene = set()

    heute = datetime.now(ZoneInfo("UTC")).date()

    for tag_index in range(tage):
        tag = heute + timedelta(days=tag_index)
        soup = _tag_seite_holen(site_id, tag)
        if soup is None:
            continue

        try:
            sendungen = _tag_parsen(soup, tag)
        except Exception as e:
            print(f"TVPassport-EPG: Parsen fuer '{site_id}' ({tag}) fehlgeschlagen ({e}), ueberspringe Tag.")
            continue

        for p in sendungen:
            schluessel = (p["title"], p["start"], p["stop"])
            if schluessel in gesehene:
                continue
            gesehene.add(schluessel)
            alle_sendungen.append(p)

    alle_sendungen.sort(key=lambda s: s["start"])
    return alle_sendungen
