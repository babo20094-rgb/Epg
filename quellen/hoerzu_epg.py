"""Optionale, echte Programmdaten von hoerzu.de (Deutschland/Oesterreich) -
AUTOMATISCH als dritter Versuch fuer DE-Sender (nach Pluto TV und
tvmovie.de, siehe die Verarbeitungsbloecke in generate_epg.py), nur wenn
keine der beiden anderen Quellen fuer diesen Sender etwas gefunden hat.

Jede Kanalseite (`hoerzu.de/tv-programm/<slug>/`) enthaelt direkt
serverseitig gerendert einen JSON-LD-Block (schema.org "BroadcastEvent")
mit dem kompletten Tagesraster (~20-40 Sendungen, ca. 24 Stunden ab dem
aktuellen Zeitpunkt) - kein Login, kein JavaScript/AJAX-Nachladen noetig
wie bei manch anderer Balkan-Quelle. Ein Datums-Query-Parameter wird von
der Seite ignoriert (immer nur der aktuelle Tag), es gibt daher bewusst
kein mehrtaegiges Datumsraster wie bei Telemach/mts.rs - Tage danach sind
ohnehin immer generisch.

Die Kanalsuche nutzt eine im Repo mitgelieferte statische Datei
(`hoerzu_kanalliste.txt`, ~170 Eintraege, aus der WebGrab+Plus-Kanalliste
fuer hoerzu.de extrahiert, Zeilenformat "<slug>|<Name>") statt live zu
crawlen - kein Netzwerk-Request fuer die Kanalsuche selbst, nur der
eigentliche Programmabruf fuer tatsaechlich getroffene Kanaele geht live.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt Kanalsuche,
Seitenabruf oder das Parsen des JSON-LD-Blocks fehl, bekommt der
betroffene Sender in generate_epg.py einfach die normale,
kategoriebasierte generische EPG-Generierung wie jeder andere Sender -
dieses Modul darf einen Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timezone

import difflib
import json
import os
import re

import requests

from epg_lib import normalisiere_sendername

BASE_URL = "https://www.hoerzu.de/tv-programm"

REQUEST_TIMEOUT_SEKUNDEN = 20

KANALLISTE_DATEI = os.path.join(os.path.dirname(__file__), "hoerzu_kanalliste.txt")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

JSON_LD_MUSTER = re.compile(
    r'\[\{"@context":"https://schema\.org","@type":"BroadcastEvent".*?\}\]',
    re.S,
)

_kanalliste_cache = None
_seite_cache = {}


def hoerzu_hole_kanalliste():
    """Laedt (und cached) die statische Kanalliste aus
    hoerzu_kanalliste.txt als Liste von {"slug":..., "name":...}. Leere
    Liste bei jedem Fehler (Datei fehlt, unlesbar, leer)."""
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
                slug, name = zeile.split("|", 1)
                if not slug.strip() or not name.strip():
                    continue
                kanaele.append({"slug": slug.strip(), "name": name.strip()})
        _kanalliste_cache = kanaele
        return kanaele
    except Exception as e:
        print(f"Hoerzu-EPG: Kanalliste konnte nicht gelesen werden ({e}), ueberspringe.")
        _kanalliste_cache = []
        return []


def hoerzu_kanal_finden(kanalname):
    """Sucht den hoerzu.de-Kanal, der am besten zu kanalname passt - erst
    exakter Abgleich nach normalisiere_sendername(), sonst unscharfer
    difflib-Abgleich. Gibt den Slug zurueck oder None."""
    kanaele = hoerzu_hole_kanalliste()
    if not kanaele:
        return None

    ziel_schluessel = normalisiere_sendername(kanalname)
    if not ziel_schluessel:
        return None

    name_index = {}
    for kanal in kanaele:
        schluessel = normalisiere_sendername(kanal["name"])
        if schluessel:
            name_index.setdefault(schluessel, kanal["slug"])

    if ziel_schluessel in name_index:
        return name_index[ziel_schluessel]

    aehnliche = difflib.get_close_matches(ziel_schluessel, name_index.keys(), n=1, cutoff=0.72)
    if aehnliche:
        return name_index[aehnliche[0]]

    return None


def _seite_holen(slug):
    """Holt (und cached pro Kanal) die rohe HTML-Seite. Gibt bei jedem
    Fehler None zurueck."""
    if slug in _seite_cache:
        return _seite_cache[slug]

    try:
        response = requests.get(
            f"{BASE_URL}/{slug}/", headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        _seite_cache[slug] = response.text
        return response.text
    except Exception as e:
        print(f"Hoerzu-EPG: Seitenabruf ({slug}) fehlgeschlagen ({e}), ueberspringe.")
        _seite_cache[slug] = None
        return None


def _zeit_parsen(text):
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _programme_parsen(html):
    match = JSON_LD_MUSTER.search(html)
    if not match:
        return []

    daten = json.loads(match.group(0))
    if not isinstance(daten, list):
        return []

    ergebnis = []
    for eintrag in daten:
        if not isinstance(eintrag, dict):
            continue
        titel = (eintrag.get("name") or "").strip()
        start = _zeit_parsen(eintrag.get("startDate") or "")
        stop = _zeit_parsen(eintrag.get("endDate") or "")
        if not titel or start is None or stop is None or stop <= start:
            continue
        ergebnis.append({
            "title": titel,
            "beschreibung": (eintrag.get("description") or "").strip(),
            "bild": None,
            "start": start.astimezone(timezone.utc),
            "stop": stop.astimezone(timezone.utc),
        })

    return ergebnis


def hoerzu_hole_programme(slug):
    """Holt Programmdaten fuer den gegebenen hoerzu.de-Kanal (Slug).
    Liefert eine nach Startzeit sortierte Liste von {"title",
    "beschreibung", "bild", "start", "stop"} (UTC, tz-aware) - leere
    Liste bei jedem Fehler (Netzwerk, HTTP-Status, fehlender/kaputter
    JSON-LD-Block). Deckt nur den aktuellen Tag ab (~24 Stunden), die
    Website ignoriert Datums-Parameter."""
    if not slug:
        return []

    html = _seite_holen(slug)
    if html is None:
        return []

    try:
        ergebnis = _programme_parsen(html)
    except Exception as e:
        print(f"Hoerzu-EPG: Parsen fuer Kanal '{slug}' fehlgeschlagen ({e}), ueberspringe.")
        return []

    ergebnis.sort(key=lambda s: s["start"])
    return ergebnis
