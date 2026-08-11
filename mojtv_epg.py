"""Optionale, echte Programmdaten von mojtv.hr fuer HR/BA/RS/SI/ME
("Cg")-Sender - AUTOMATISCH fuer jeden ganz normal eingetragenen
Sender mit einem dieser Laender, gleiches Prinzip wie der BA/ME-
Telemach-Autoabgleich, aber als vierte/letzte Fallback-Quelle NACH
Telemach/mtel.ba/mts.rs/MojMaxTV/tv-spored.siol.net (siehe die
jeweiligen Verarbeitungsbloecke in generate_epg.py) - nur wenn die
laenderspezifische Hauptquelle nichts gefunden hat.

Die Kanalsuche nutzt eine im Repo mitgelieferte statische Datei
(`mojtv_kanalliste.txt`, ca. 190 Eintraege, Zeilenformat "<id>|<Name>")
statt live alle Kategorie-Seiten von mojtv.hr zu crawlen - das kostet
keinen einzigen Netzwerk-Request fuer die Kanalsuche selbst, nur der
eigentliche Programmabruf fuer tatsaechlich getroffene Kanaele geht
live. Die Datei deckt die Kategorien Hrvatski/Sportski/Dokumentarni/
Glazbeni/Djecji/Informativni/Zabavni/BiH/Slovenski/Srpski/Cg ab und
sollte gelegentlich manuell aktualisiert werden, falls mojtv.hr neue
Kanaele listet - das passiert hier nicht automatisch.

Programmabruf: pro Kanal/Tag wird `kanal.aspx?datum=DD.M.YYYY&id=<ID>`
einzeln abgerufen (HTML-Scraping mit BeautifulSoup, keine stabile
JSON-API) und liefert nur Startzeiten - die Endzeit einer Sendung wird
aus der Startzeit der naechsten Sendung berechnet (letzte Sendung des
Tages endet um Mitternacht), analog zu arena_epg.py/mymedia_epg.py.

Da hier HTML-Struktur statt einer stabilen JSON-API gescrapt wird, ist
dieses Modul prinzipbedingt anfaelliger fuer Breaking Changes bei einem
Website-Redesign als Telemach/mtel/mts.rs - degradiert aber nach
derselben Zero-Risk-Garantie an JEDER Stelle graceful auf None/[]
statt zu werfen: schlaegt Kanalsuche oder Programmabruf fehl, bekommt
der betroffene Sender in generate_epg.py einfach die normale,
kategoriebasierte generische EPG-Generierung wie jeder andere Sender -
dieses Modul darf einen Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import difflib
import os
import re

import requests
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

from epg_lib import normalisiere_sendername

BASE_URL = "https://mojtv.hr/m2/tv-program/kanal.aspx"

REQUEST_TIMEOUT_SEKUNDEN = 20

TZ = ZoneInfo("Europe/Zagreb")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "hr-HR,hr;q=0.9,de-DE,de;q=0.8,en-US;q=0.7,en;q=0.6",
    "Referer": "https://mojtv.hr/m2/tv-program/",
}

KANALLISTE_DATEI = os.path.join(os.path.dirname(__file__), "mojtv_kanalliste.txt")

# Modul-weite Caches: die statische Kanalliste wird nur einmal
# eingelesen, die rohe geparste Tages-Seite pro Kanal/Tag nur einmal
# pro Lauf abgerufen.
_kanalliste_cache = None
_seite_cache = {}


def mojtv_hole_kanalliste():
    """Laedt (und cached) die statische Kanalliste aus
    mojtv_kanalliste.txt als Liste von {"site_id":..., "name":...}.
    Leere Liste bei jedem Fehler (Datei fehlt, unlesbar, leer)."""
    global _kanalliste_cache

    if _kanalliste_cache is not None:
        return _kanalliste_cache

    try:
        kanaele = []
        with open(KANALLISTE_DATEI, encoding="utf-8") as f:
            for zeile in f:
                zeile = zeile.strip()
                if not zeile or "|" not in zeile:
                    continue
                site_id, name = zeile.split("|", 1)
                if not site_id.strip().isdigit() or not name.strip():
                    continue
                kanaele.append({"site_id": site_id.strip(), "name": name.strip()})
        _kanalliste_cache = kanaele
        return kanaele
    except Exception as e:
        print(f"MojTV-EPG: Kanalliste konnte nicht gelesen werden ({e}), ueberspringe.")
        _kanalliste_cache = []
        return []


def mojtv_kanal_finden(kanalname):
    """Sucht den mojtv.hr-Kanal, der am besten zu kanalname passt -
    erst exakter Abgleich nach normalisiere_sendername(), sonst
    unscharfer difflib-Abgleich (gleiche Vorgehensweise wie
    telemach_kanal_finden()/mtel_kanal_finden()). Gibt die site_id
    (als String) zurueck oder None."""
    kanaele = mojtv_hole_kanalliste()
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


def _seite_holen(site_id, tag):
    """Holt (und cached pro Kanal/Tag) die rohe HTML-Seite als
    BeautifulSoup-Objekt. Gibt bei jedem Fehler None zurueck."""
    schluessel = (site_id, tag.isoformat())

    if schluessel in _seite_cache:
        return _seite_cache[schluessel]

    datum_text = f"{tag.day}.{tag.month}.{tag.year}"

    try:
        response = requests.get(
            BASE_URL, params={"datum": datum_text, "id": site_id},
            headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        _seite_cache[schluessel] = soup
        return soup
    except Exception as e:
        print(f"MojTV-EPG: Seitenabruf ({site_id}, {datum_text}) fehlgeschlagen ({e}), ueberspringe.")
        _seite_cache[schluessel] = None
        return None


def _zeit_parsen(text):
    match = re.match(r"^(\d{1,2}):(\d{2})$", (text or "").strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _tag_programme_parsen(soup, tag):
    roh = []
    for li in soup.select("li"):
        zeit_tag = li.select_one(".show-time b")
        anker = li.find("a")
        if zeit_tag is None or anker is None:
            continue

        zeit = _zeit_parsen(zeit_tag.get_text(strip=True))
        if zeit is None:
            continue
        stunde, minute = zeit

        aeusserer_span = anker.find("span")
        if aeusserer_span is None:
            continue

        titel_tag = aeusserer_span.find("b")
        titel = titel_tag.get_text(strip=True) if titel_tag else ""
        if not titel:
            continue

        beschr_span = aeusserer_span.find("span")
        beschreibung = beschr_span.get_text(strip=True) if beschr_span else ""

        start = datetime(tag.year, tag.month, tag.day, stunde, minute, tzinfo=TZ)
        roh.append({"title": titel, "beschreibung": beschreibung, "start": start})

    roh.sort(key=lambda s: s["start"])

    ergebnis = []
    for index, sendung in enumerate(roh):
        if index + 1 < len(roh):
            stop = roh[index + 1]["start"]
        else:
            tag_start = sendung["start"].replace(hour=0, minute=0, second=0, microsecond=0)
            stop = tag_start + timedelta(days=1)
        if stop <= sendung["start"]:
            continue
        ergebnis.append({
            "title": sendung["title"],
            "beschreibung": sendung["beschreibung"],
            "start": sendung["start"],
            "stop": stop,
        })

    return ergebnis


def mojtv_hole_programme(site_id, tage=3):
    """Holt Programmdaten fuer den gegebenen mojtv.hr-Kanal (site_id)
    fuer `tage` aufeinanderfolgende Tage ab heute (Europe/Zagreb).
    Liefert eine nach Startzeit sortierte Liste von {"title",
    "beschreibung", "bild", "start", "stop"} (UTC, tz-aware) - leere
    Liste bei jedem Fehler (Netzwerk, HTTP-Status, unerwartete HTML-
    Struktur)."""
    if site_id is None:
        return []

    heute = datetime.now(TZ).date()

    alle = []
    for i in range(tage):
        tag = heute + timedelta(days=i)
        soup = _seite_holen(site_id, tag)
        if soup is None:
            continue
        try:
            alle.extend(_tag_programme_parsen(soup, tag))
        except Exception as e:
            print(f"MojTV-EPG: Parsen fuer Kanal {site_id} Tag {tag} fehlgeschlagen ({e}), ueberspringe Tag.")
            continue

    ergebnis = []
    for p in alle:
        try:
            ergebnis.append({
                "title": p["title"],
                "beschreibung": p.get("beschreibung") or "",
                "bild": None,
                "start": p["start"].astimezone(timezone.utc),
                "stop": p["stop"].astimezone(timezone.utc),
            })
        except Exception:
            continue

    ergebnis.sort(key=lambda s: s["start"])
    return ergebnis
