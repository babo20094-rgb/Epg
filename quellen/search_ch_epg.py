"""Optionale, echte Programmdaten von search.ch/tv (Schweiz) - aktuell
NUR fuer "blue Sport 1"/"blue Sport 2" (Swisscom-Sportkanaele) genutzt,
die sonst nirgends echte Programmdaten haben.

Bewusst KEIN automatisches Matching wie bei BA/ME (Telemach/mtel) und
KEIN Fuzzy-Abgleich - nur ein exaktes, festes Mapping von genau diesen
zwei Kanalnamen auf ihre search.ch-Slugs ("tcsport1"/"tcsport2"), da
search.ch generell viele Kanaele fuehrt, aber bisher nur diese zwei fuer
unsere sender.txt relevant sind und ein Fuzzy-Abgleich hier unnoetiges
Fehltreffer-Risiko waere (das immer wiederkehrende Bug-Muster dieser
Session, siehe CLAUDE.md).

search.ch liefert je Kanalseite (https://search.ch/tv/<slug>) in einer
einzigen Anfrage bereits alle aktuell bekannten kommenden Sendungen
(erfahrungsgemaess ca. 3 Tage) inkl. ISO-Startzeitstempel direkt im
href jedes Sendungs-Links - kein Datums-Parsing/keine Paginierung
noetig. Titel + optionaler Untertitel (z.B. "Fussball: Challenge
League" + "Disziplin: FC Winterthur - Neuchatel Xamax FCS, 7.
Spieltag") werden wie bei anderen Quellen zu einem kombinierten Titel
zusammengefuegt - die zentrale Kuerzungslogik (kuerze_beschreibung() in
generate_epg.py) kappt lange Anhaengsel automatisch.

Da hier HTML statt einer stabilen JSON-API geparst wird, ist dieses
Modul prinzipbedingt anfaelliger fuer Breaking Changes bei einem
Website-Redesign als eine reine API-Quelle - degradiert aber nach dem
gleichen Zero-Risk-Prinzip an jeder Stelle graceful auf None/[]/leere
Ergebnisse statt zu werfen.
"""

from datetime import datetime, timedelta

import re

import requests
from zoneinfo import ZoneInfo

BASIS_URL = "https://search.ch/tv/"
REQUEST_TIMEOUT_SEKUNDEN = 20
ZUERICH_TZ = ZoneInfo("Europe/Zurich")

# Festes, exaktes Mapping - kein Fuzzy-Abgleich (siehe Modul-Docstring).
_KANAL_SLUGS = {
    "BLUE SPORT 1": "tcsport1",
    "BLUE SPORT 2": "tcsport2",
}

_QUALITAETS_SUFFIX = re.compile(r"\b(?:HD|FHD|UHD|SD|HEVC|4K|8K)\b", re.IGNORECASE)

# Modul-weiter Cache: jede Kanalseite wird pro Lauf nur einmal geholt.
_seite_cache = {}

_SHOW_MUSTER = re.compile(
    r'href="/tv/[a-z0-9]+/(?P<start>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})-[a-z0-9\-]*"'
    r'\s*class="tv-show-link">.*?'
    r'<span class="tv-show-title">(?P<titel>[^<]*)</span>'
    r'(?:\s*<i class="tv-show-subtitle">(?P<untertitel>[^<]*)</i>)?',
    re.DOTALL,
)


def search_ch_kanal_finden(kanalname):
    """Prueft, ob kanalname (nach Entfernen von Qualitaets-Suffixen wie
    HD/FHD/HEVC) exakt "BLUE SPORT 1"/"BLUE SPORT 2" entspricht - gibt
    dann den search.ch-Slug zurueck, sonst None. Kein Fuzzy-Abgleich."""
    if not kanalname:
        return None
    bereinigt = _QUALITAETS_SUFFIX.sub(" ", kanalname).strip()
    bereinigt = re.sub(r"\s+", " ", bereinigt).upper()
    return _KANAL_SLUGS.get(bereinigt)


def _seite_holen(slug):
    """Holt (und cached pro Slug) die rohe HTML-Seite als Text. Gibt bei
    jedem Fehler None zurueck."""
    if slug in _seite_cache:
        return _seite_cache[slug]

    try:
        response = requests.get(
            BASIS_URL + slug, timeout=REQUEST_TIMEOUT_SEKUNDEN
        )
        response.raise_for_status()
        _seite_cache[slug] = response.text
        return response.text
    except Exception as e:
        print(f"Search.ch-EPG: Seitenabruf ({slug}) fehlgeschlagen ({e}), ueberspringe.")
        _seite_cache[slug] = None
        return None


def search_ch_hole_programme(slug, tage=3):
    """Holt Programmdaten fuer den gegebenen search.ch-Kanal-Slug fuer
    bis zu `tage` Tage (begrenzt durch die auf der Seite tatsaechlich
    verfuegbaren Sendungen). Liefert eine nach Startzeit sortierte Liste
    von {"title", "beschreibung", "start", "stop"} (UTC, tz-aware) - leere
    Liste bei jedem Fehler (Netzwerk, HTTP-Status, unerwartete HTML-
    Struktur)."""
    if not slug:
        return []

    text = _seite_holen(slug)
    if text is None:
        return []

    try:
        heute = datetime.now(ZUERICH_TZ).date()
        grenze = heute + timedelta(days=tage)

        roh = []
        for match in _SHOW_MUSTER.finditer(text):
            try:
                start = datetime.strptime(
                    match.group("start"), "%Y-%m-%dT%H:%M:%S"
                ).replace(tzinfo=ZUERICH_TZ)
            except Exception:
                continue

            if start.date() > grenze:
                continue

            titel = (match.group("titel") or "").strip()
            if not titel:
                continue
            untertitel = (match.group("untertitel") or "").strip()

            roh.append({
                "title": f"{titel}: {untertitel}" if untertitel else titel,
                "start": start,
            })

        roh.sort(key=lambda s: s["start"])

        ergebnis = []
        for index, sendung in enumerate(roh):
            if index + 1 < len(roh):
                stop = roh[index + 1]["start"]
            else:
                tag_start = sendung["start"].replace(hour=0, minute=0, second=0, microsecond=0)
                stop = tag_start + timedelta(days=1)
            ergebnis.append({
                "title": sendung["title"],
                "beschreibung": "",
                "start": sendung["start"].astimezone(ZoneInfo("UTC")),
                "stop": stop.astimezone(ZoneInfo("UTC")),
            })

        return ergebnis
    except Exception as e:
        print(f"Search.ch-EPG: Programmabruf fuer Kanal {slug} fehlgeschlagen ({e}), ueberspringe.")
        return []
