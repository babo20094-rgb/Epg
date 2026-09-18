"""Optionale, echte Programmdaten von tvprogramdanas.net (EXYU-Portal:
HR/RS/BA/MNG/MO/SI/MK-Sender sowie diverse internationale Pay-TV-Kanaele
wie HBO/Cinemax/Pink*/CineStar/FilmBox). AUTOMATISCH als letzter
Fallback-Versuch nach den jeweiligen laenderspezifischen Kaskaden in
generate_epg.py, nur wenn keine der anderen Quellen fuer diesen Sender
etwas gefunden hat.

Bewusst OHNE Arena-Sport- und Sport-Klub-Kanaele (siehe
tvprogramdanas_kanalliste.txt-Erzeugung) - diese laufen bereits stabil
ueber arena_epg.py/sportklub_epg.py und sollen nicht angefasst werden.

Die Sender-Detailseite (https://tvprogramdanas.net/<slug>) liefert pro
Aufruf OHNE JavaScript/Klick serverseitig gerendert bis zu drei Tage
(heute/morgen/uebermorgen) als separate "schedule-tab"-Bloecke im HTML -
ein einzelner GET-Request reicht, keine weiteren Klicks/Requests noetig.
Nicht jeder Kanal hat fuer alle drei Tage Daten (oft nur "heute"
vollstaendig) - fehlende/leere Tage werden einfach uebersprungen.

Die Kanalsuche nutzt eine im Repo mitgelieferte statische Datei
(tvprogramdanas_kanalliste.txt, "<slug>|<Name>", aus allen Kategorien der
Seite exportiert) statt live zu crawlen - kein Netzwerk-Request fuer die
Kanalsuche selbst, nur der eigentliche Programmabruf fuer tatsaechlich
getroffene Kanaele geht live.

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
import html
import os
import re

import threading
import requests
from quellen import _http

from epg_lib import normalisiere_sendername

URL_VORLAGE = "https://www.tvprogramdanas.net/{slug}"

REQUEST_TIMEOUT_SEKUNDEN = 20

BALKAN_TZ = ZoneInfo("Europe/Sarajevo")

KANALLISTE_DATEI = os.path.join(os.path.dirname(__file__), "tvprogramdanas_kanalliste.txt")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_TIMELINE_MUSTER = re.compile(
    r'<span class="time"[^>]*>\s*([^<]+?)\s*</span>\s*'
    r'<span class="duration"[^>]*>[^<]*</span>.*?'
    r'<h3 class="program-name"[^>]*>\s*([^<]*?)\s*</h3>\s*'
    r'<p class="program-desc"[^>]*>\s*(.*?)\s*</p>',
    re.S,
)

_TAG_BLOCK_MUSTER = re.compile(r'<div id="schedule-(\d{4}-\d{2}-\d{2})" class="schedule-tab"')

_kanalliste_cache = None
# Schuetzt den Erstzugriff auf _kanalliste_cache: bei gleichzeitigem Zugriff aus
# mehreren Threads (siehe _parallel_abrufen() in generate_epg.py)
# wuerden ohne diese Sperre alle Threads gleichzeitig "noch nicht
# geladen" sehen und dieselbe Datei jeder fuer sich parallel
# herunterladen, statt dass nur einer laedt und die anderen warten.
_kanalliste_cache_lock = threading.Lock()
_seiten_cache = {}

# Explizite Sperre fuer ARENA-SPORT-/SPORT-KLUB-Kanaele (analog zu
# _ARENA_SPORT_GUARD/_SPORT_KLUB_GUARD in mts_epg.py): diese laufen
# bereits stabil ueber arena_epg.py/sportklub_epg.py und sollen NICHT
# angefasst werden. Die Kanalliste selbst enthaelt zwar bereits keine
# "Arena Sport"/"Sport Klub"-Eintraege (siehe Erzeugung der Datei), aber
# ein unscharfer Treffer koennte sonst faelschlich auf einen aehnlich
# benannten Kanal wie "Arena Esport" ausweichen - der Guard verhindert
# das unabhaengig vom Inhalt der Kanalliste.
_ARENA_SPORT_GUARD = re.compile(r"^ARENA\s*SPORT\b", re.IGNORECASE)
_SPORT_KLUB_GUARD = re.compile(r"^SPORT\s*KLUB\b", re.IGNORECASE)
# "SK N"/"SK Esports"/"SK Fight"/"SK Golf" (eigene sender.txt-Konvention
# fuer Sport Klub, siehe sportklub_epg.py) - dieselbe Sperre wie fuer
# "SPORT KLUB" ausgeschrieben, sonst wuerde z.B. "SK 1" hier faelschlich
# auf den gleichnamigen tvprogramdanas.net-Kanal "SK 1" matchen, obwohl
# das inhaltlich Sport Klub 1 ist (eigene, bereits laufende Quelle).
_SK_KURZFORM_GUARD = re.compile(
    r"^SK\s*(?:0*\d+K?\s*(?:HD|FHD|SD|UHD|HEVC)?|HD|FHD|SD|UHD|HEVC|ESPORTS|FIGHT|GOLF)\s*$",
    re.IGNORECASE,
)


def tvprogramdanas_hole_kanalliste():
    """Laedt (und cached) die statische Kanalliste aus
    tvprogramdanas_kanalliste.txt als Liste von {"slug":..., "name":...}.
    Leere Liste bei jedem Fehler (Datei fehlt, unlesbar, leer)."""
    global _kanalliste_cache

    if _kanalliste_cache is not None:
        return _kanalliste_cache

    with _kanalliste_cache_lock:
        # Erneut pruefen: ein anderer Thread koennte das Laden
        # bereits erledigt haben, waehrend dieser Thread auf die
        # Sperre wartete.
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
            print(f"TvProgramDanas-EPG: Kanalliste konnte nicht gelesen werden ({e}), ueberspringe.")
            _kanalliste_cache = []
            return []

def tvprogramdanas_kanal_finden(kanalname):
    """Sucht den tvprogramdanas.net-Kanal, der am besten zu kanalname
    passt - erst exakter Abgleich nach normalisiere_sendername(), sonst
    unscharfer difflib-Abgleich. Gibt den Slug zurueck oder None."""
    kanaele = tvprogramdanas_hole_kanalliste()
    if not kanaele:
        return None

    if _ARENA_SPORT_GUARD.match(kanalname.strip()):
        return None

    if _SPORT_KLUB_GUARD.match(kanalname.strip()):
        return None

    if _SK_KURZFORM_GUARD.match(kanalname.strip()):
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

    aehnliche = difflib.get_close_matches(ziel_schluessel, name_index.keys(), n=1, cutoff=0.85)
    if aehnliche:
        return name_index[aehnliche[0]]

    return None


def _zeit_parsen(text):
    match = re.match(r"^(\d{1,2}):(\d{2})$", (text or "").strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _seite_holen(slug):
    """Holt (und cached pro Kanal) den rohen HTML-Text der
    Sender-Detailseite. Gibt bei jedem Fehler None zurueck."""
    if slug in _seiten_cache:
        return _seiten_cache[slug]

    try:
        response = _http.mit_retry(requests.get, 
            URL_VORLAGE.format(slug=slug), headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        text = response.text
        _seiten_cache[slug] = text
        return text
    except Exception as e:
        print(f"TvProgramDanas-EPG: Seitenabruf ({slug}) fehlgeschlagen ({e}), ueberspringe.")
        _seiten_cache[slug] = None
        return None


def _tag_programme_parsen(block_text, tag):
    roh = []
    for zeit_text, titel_roh, beschreibung_roh in _TIMELINE_MUSTER.findall(block_text):
        zeit = _zeit_parsen(zeit_text)
        titel = html.unescape(titel_roh).strip()
        if zeit is None or not titel:
            continue
        stunde, minute = zeit
        start = datetime(tag.year, tag.month, tag.day, stunde, minute, tzinfo=BALKAN_TZ)
        beschreibung = html.unescape(re.sub(r"<[^>]+>", "", beschreibung_roh)).strip()
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
            "bild": None,
            "start": sendung["start"],
            "stop": stop,
        })

    return ergebnis


def tvprogramdanas_hole_programme(slug, tage=3):
    """Holt Programmdaten fuer den gegebenen tvprogramdanas.net-Kanal
    (slug) fuer bis zu `tage` Tage ab heute (Europe/Sarajevo) - ein
    einzelner Seitenabruf liefert alle verfuegbaren Tage auf einmal.
    Liefert eine nach Startzeit sortierte Liste von {"title",
    "beschreibung", "bild", "start", "stop"} (UTC, tz-aware) - leere
    Liste bei jedem Fehler (Netzwerk, HTTP-Status, kein Treffer)."""
    if not slug:
        return []

    text = _seite_holen(slug)
    if not text:
        return []

    heute = datetime.now(BALKAN_TZ).date()
    erlaubte_tage = {(heute + timedelta(days=i)).isoformat() for i in range(tage)}

    positionen = list(_TAG_BLOCK_MUSTER.finditer(text))

    alle = []
    for index, treffer in enumerate(positionen):
        datum_text = treffer.group(1)
        if datum_text not in erlaubte_tage:
            continue
        block_start = treffer.end()
        block_ende = positionen[index + 1].start() if index + 1 < len(positionen) else len(text)
        block_text = text[block_start:block_ende]
        try:
            tag = datetime.strptime(datum_text, "%Y-%m-%d").date()
            alle.extend(_tag_programme_parsen(block_text, tag))
        except Exception as e:
            print(f"TvProgramDanas-EPG: Parsen fuer Kanal {slug} Tag {datum_text} fehlgeschlagen ({e}), ueberspringe Tag.")
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
