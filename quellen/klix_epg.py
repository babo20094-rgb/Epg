"""Optionale, echte Programmdaten von klix.ba (Bosnien) - AUTOMATISCH als
dritter/vierter Versuch fuer BA-Sender (nach Telemach/mtel.ba/mymedia.ba,
siehe die Verarbeitungsbloecke in generate_epg.py), nur wenn keine der
anderen Quellen fuer diesen Sender etwas gefunden hat.

Oeffentliche, loginfreie JSON-API (`https://api.klix.ba/v1/tvprogram/
<channel_id>?datum=YYYY-MM-DD`), portiert aus dem WebGrab+Plus-Site-
Plugin "klix.ba" (siteini.pack, Bosnia). Die API liefert pro Sendung nur
eine lokale Startzeit ("HH:MM", Europe/Sarajevo) - die Endzeit wird aus
dem Start der naechsten Sendung berechnet (letzte Sendung des Tages
endet um Mitternacht), analog zu arena_epg.py/mymedia_epg.py. Eine
ausfuehrliche Beschreibung gibt es laut Original-Plugin nur ueber einen
zusaetzlichen Detailseiten-Abruf pro Sendung (`link`-Feld) - das wird
hier bewusst NICHT nachgeladen (kein Extra-Request pro Sendung wie bei
tvguide_epg.py/freeview_epg.py), `beschreibung` bleibt daher leer.

Die Kanalsuche nutzt eine im Repo mitgelieferte statische Datei
(`klix_kanalliste.txt`, ~55 Eintraege, aus der Original-Kanalliste des
WebGrab+Plus-Plugins extrahiert, Zeilenformat "<site_id>|<Name>") statt
live zu crawlen - kein Netzwerk-Request fuer die Kanalsuche selbst, nur
der eigentliche Programmabruf fuer tatsaechlich getroffene Kanaele geht
live.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt Kanalsuche oder
Programmabruf fehl, bekommt der betroffene Sender in generate_epg.py
einfach die normale, kategoriebasierte generische EPG-Generierung wie
jeder andere Sender - dieses Modul darf einen Lauf niemals zum Absturz
bringen.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import difflib
import os
import re

import requests

from epg_lib import normalisiere_sendername

URL_VORLAGE = "https://api.klix.ba/v1/tvprogram/{kanal_id}?datum={datum}"

REQUEST_TIMEOUT_SEKUNDEN = 20

SARAJEVO_TZ = ZoneInfo("Europe/Sarajevo")

KANALLISTE_DATEI = os.path.join(os.path.dirname(__file__), "klix_kanalliste.txt")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_kanalliste_cache = None
_tag_cache = {}


def klix_hole_kanalliste():
    """Laedt (und cached) die statische Kanalliste aus
    klix_kanalliste.txt als Liste von {"site_id":..., "name":...}.
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
        print(f"Klix-EPG: Kanalliste konnte nicht gelesen werden ({e}), ueberspringe.")
        _kanalliste_cache = []
        return []


def klix_kanal_finden(kanalname):
    """Sucht den klix.ba-Kanal, der am besten zu kanalname passt - erst
    exakter Abgleich nach normalisiere_sendername(), sonst unscharfer
    difflib-Abgleich. Gibt die site_id zurueck oder None."""
    kanaele = klix_hole_kanalliste()
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


def _zeit_parsen(text):
    match = re.match(r"^(\d{1,2}):(\d{2})$", (text or "").strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _tag_holen(site_id, tag):
    """Holt (und cached pro Kanal/Tag) die rohe JSON-Antwort als Liste
    von dicts. Gibt bei jedem Fehler None zurueck."""
    schluessel = (site_id, tag.isoformat())

    if schluessel in _tag_cache:
        return _tag_cache[schluessel]

    datum_text = tag.strftime("%Y-%m-%d")

    try:
        response = requests.get(
            URL_VORLAGE.format(kanal_id=site_id, datum=datum_text),
            headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        daten = response.json()
        if not isinstance(daten, list):
            daten = []
        _tag_cache[schluessel] = daten
        return daten
    except Exception as e:
        print(f"Klix-EPG: Tagesabruf ({site_id}, {datum_text}) fehlgeschlagen ({e}), ueberspringe.")
        _tag_cache[schluessel] = None
        return None


def _tag_programme_parsen(roh_liste, tag):
    roh = []
    for eintrag in roh_liste:
        if not isinstance(eintrag, dict):
            continue
        zeit = _zeit_parsen(eintrag.get("timeStart"))
        titel = (eintrag.get("title") or "").strip()
        if zeit is None or not titel:
            continue
        stunde, minute = zeit
        start = datetime(tag.year, tag.month, tag.day, stunde, minute, tzinfo=SARAJEVO_TZ)
        roh.append({"title": titel, "start": start})

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
            "beschreibung": "",
            "bild": None,
            "start": sendung["start"],
            "stop": stop,
        })

    return ergebnis


def klix_hole_programme(site_id, tage=3):
    """Holt Programmdaten fuer den gegebenen klix.ba-Kanal (site_id)
    fuer `tage` aufeinanderfolgende Tage ab heute (Europe/Sarajevo).
    Liefert eine nach Startzeit sortierte Liste von {"title",
    "beschreibung", "bild", "start", "stop"} (UTC, tz-aware) - leere
    Liste bei jedem Fehler (Netzwerk, HTTP-Status, unerwartetes JSON)."""
    if site_id is None:
        return []

    heute = datetime.now(SARAJEVO_TZ).date()

    alle = []
    for i in range(tage):
        tag = heute + timedelta(days=i)
        roh_liste = _tag_holen(site_id, tag)
        if roh_liste is None:
            continue
        try:
            alle.extend(_tag_programme_parsen(roh_liste, tag))
        except Exception as e:
            print(f"Klix-EPG: Parsen fuer Kanal {site_id} Tag {tag} fehlgeschlagen ({e}), ueberspringe Tag.")
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
