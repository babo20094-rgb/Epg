"""Echte Programmdaten von tvprogram.rs (oeffentlicher, loginfreier
serbischer TV-Guide mit 91 Kanaelen) - AUTOMATISCH fuer RS/BA/HR/SI/MK-
Sender, als zusaetzlicher Fallback NACH den jeweiligen Haupt-Quellen
(Telemach/mts.rs/MojMaxTV/Siol/tvprofil.net - siehe deren
Verarbeitungsbloecke in generate_epg.py). Kein eigenes sender.txt-
Praefix noetig.

Die Kanalsuche nutzt eine im Repo mitgelieferte statische Datei
(tvprogramrs_kanalliste.txt, 91 Eintraege, Zeilenformat
"<numerische ID>|<URL-Slug>|<Name>") - kein Netzwerk-Request fuer die
Kanalsuche selbst. WICHTIG: nur EXAKTER Name- oder Kern-Abgleich (HD/
FHD/UHD/SD-Suffixe entfernt), BEWUSST OHNE unscharfen difflib-Fallback
(anders als die meisten anderen *_kanal_finden()-Funktionen dieses
Repos) - ein erster Testlauf des unscharfen Abgleichs gegen alle RS/BA/
HR/SI/MK-Sender ergab mehrere eindeutige Fehltreffer (u.a. "DISNEY
CHANNEL"/"DISCOVERY CHANNEL"/"STAR CHANNEL" -> faelschlich
"history-channel", "FOOD NETWORK" -> faelschlich "cartoon-network",
"NASA TV" -> faelschlich der serbische Sender "Naša" ueber den Kern-
Praefix "NASA"), lieber weniger, aber garantiert richtige Treffer.

Jede Kanalseite (tvprogram.rs/<slug>-tv-program-danas.<id>.html)
enthaelt serverseitig gerendert eine Liste aus Zeit+Titel-Paaren fuer
NUR den aktuellen Tag ("danas" = "heute") - es gibt keine "sutra"
(morgen)-Variante, ein Datums-Parameter wird nicht unterstuetzt (die
falsche numerische ID in der URL liefert ebenfalls HTTP 200, aber eine
KOMPLETT LEERE Sendungsliste statt eines Fehlers - deshalb ist die
korrekte ID zwingend, nicht nur der Slug). Manche Zeitpunkte sind mit
dem Platzhaltertext "No information" belegt (echte Datenluecke der
Quelle selbst, kein Parsing-Fehler) und werden beim Parsen uebersprungen.

Wird nur EINMAL pro Kanal und Lauf geladen und geparst (Modul-weiter
Cache pro Slug/ID). Degradiert nach dem gleichen Zero-Risk-Prinzip an
JEDER Stelle graceful auf None/[]/leere Ergebnisse statt zu werfen:
schlaegt Download oder Parsen fehl, bekommt der betroffene Sender in
generate_epg.py einfach die normale, kategoriebasierte generische
EPG-Generierung wie jeder andere Sender - dieses Modul darf einen Lauf
niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import os
import re

import requests
from zoneinfo import ZoneInfo

from epg_lib import normalisiere_sendername, normalisiere_sendername_kern

BASE_URL = "https://www.tvprogram.rs/{slug}-tv-program-danas.{id}.html"

REQUEST_TIMEOUT_SEKUNDEN = 20

TZ_BELGRADE = ZoneInfo("Europe/Belgrade")

KANALLISTE_DATEI = os.path.join(os.path.dirname(__file__), "tvprogramrs_kanalliste.txt")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_BLOCK_PATTERN = re.compile(r'<ul class="tv-serije-lista-inner clearfix">(.*?)</ul>', re.S)
_ZEIT_PATTERN = re.compile(r'satnica">(\d{1,2}):(\d{2})</span>')
_TITEL_PATTERN = re.compile(r'<p>(?:<a[^>]*>)?([^<]*)')

_kanalliste_cache = None
_name_index = None
_kern_index = None
_programme_cache = {}


def _kanalliste_laden():
    """Laedt (und cached) die statische Kanalliste aus
    tvprogramrs_kanalliste.txt als Liste von {"id":..., "slug":...,
    "name":...}. Leere Liste bei jedem Fehler (Datei fehlt, unlesbar,
    leer)."""
    global _kanalliste_cache

    if _kanalliste_cache is not None:
        return _kanalliste_cache

    try:
        kanaele = []
        with open(KANALLISTE_DATEI, encoding="utf-8") as f:
            for zeile in f:
                zeile = zeile.strip()
                if not zeile or zeile.count("|") != 2:
                    continue
                id_, slug, name = zeile.split("|")
                if not id_.strip() or not slug.strip() or not name.strip():
                    continue
                kanaele.append({"id": id_.strip(), "slug": slug.strip(), "name": name.strip()})
        _kanalliste_cache = kanaele
        return kanaele
    except Exception as e:
        print(f"TvProgramRS-EPG: Kanalliste konnte nicht gelesen werden ({e}), ueberspringe.")
        _kanalliste_cache = []
        return []


def _indizes_aufbauen():
    global _name_index, _kern_index
    if _name_index is not None:
        return

    kanaele = _kanalliste_laden()
    _name_index = {}
    kern_roh = {}
    kern_mehrdeutig = set()
    for kanal in kanaele:
        schluessel = normalisiere_sendername(kanal["name"])
        if schluessel:
            _name_index.setdefault(schluessel, kanal)

        kern = normalisiere_sendername_kern(kanal["name"])
        if not kern:
            continue
        if kern not in kern_roh:
            kern_roh[kern] = kanal
        elif kern_roh[kern]["slug"] != kanal["slug"]:
            kern_mehrdeutig.add(kern)
    _kern_index = {k: v for k, v in kern_roh.items() if k not in kern_mehrdeutig}


def tvprogramrs_kanal_finden(kanalname):
    """Sucht den tvprogram.rs-Kanal, der zu kanalname passt - NUR
    exakter Abgleich nach normalisiere_sendername(), sonst ein
    eindeutiger Kern-Abgleich ohne HD/FHD/UHD/SD (siehe Moduldocstring,
    warum hier BEWUSST kein unscharfer Fallback verwendet wird). Gibt
    das Kanal-Dict {"id", "slug", "name"} zurueck oder None."""
    _indizes_aufbauen()
    if not _name_index:
        return None

    ziel = normalisiere_sendername(kanalname)
    if not ziel:
        return None
    if ziel in _name_index:
        return _name_index[ziel]

    kern = normalisiere_sendername_kern(kanalname)
    if kern and kern in _kern_index:
        return _kern_index[kern]

    return None


def _seite_laden(kanal):
    """Laedt (und cached pro Kanal/Lauf) die geparste Sendungsliste
    fuer einen Kanal. Leere Liste bei jedem Fehler."""
    cache_key = kanal["slug"]
    if cache_key in _programme_cache:
        return _programme_cache[cache_key]

    try:
        url = BASE_URL.format(slug=kanal["slug"], id=kanal["id"])
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        html = response.text

        heute = datetime.now(TZ_BELGRADE).date()

        rohe_eintraege = []
        vorherige_stunde = None
        tag_offset = 0
        for block in _BLOCK_PATTERN.findall(html):
            zeit_treffer = _ZEIT_PATTERN.search(block)
            titel_treffer = _TITEL_PATTERN.search(block)
            if not zeit_treffer or not titel_treffer:
                continue
            titel = titel_treffer.group(1).strip()
            if not titel or titel.lower() == "no information":
                continue

            stunde, minute = int(zeit_treffer.group(1)), int(zeit_treffer.group(2))
            # Die Liste beginnt am fruehen Morgen und laeuft ueber
            # Mitternacht bis in den naechsten Kalendertag - ein
            # Ruecksprung der Stunde (z.B. von 23:xx auf 00:xx) markiert
            # den Tageswechsel.
            if vorherige_stunde is not None and stunde < vorherige_stunde:
                tag_offset += 1
            vorherige_stunde = stunde

            datum = heute + timedelta(days=tag_offset)
            start_lokal = datetime(
                datum.year, datum.month, datum.day, stunde, minute, tzinfo=TZ_BELGRADE,
            )
            rohe_eintraege.append({"start_lokal": start_lokal, "titel": titel})

        rohe_eintraege.sort(key=lambda e: e["start_lokal"])

        programme = []
        for i, eintrag in enumerate(rohe_eintraege):
            start = eintrag["start_lokal"].astimezone(timezone.utc)
            if i + 1 < len(rohe_eintraege):
                stop = rohe_eintraege[i + 1]["start_lokal"].astimezone(timezone.utc)
            else:
                stop = start + timedelta(hours=1)
            if stop <= start:
                continue
            programme.append({
                "title": eintrag["titel"],
                "beschreibung": eintrag["titel"],
                "bild": None,
                "start": start,
                "stop": stop,
            })

        _programme_cache[cache_key] = programme
        return programme
    except Exception as e:
        print(f"TvProgramRS-EPG: Seitenabruf ({kanal.get('slug')}) fehlgeschlagen ({e}), ueberspringe.")
        _programme_cache[cache_key] = []
        return []


def tvprogramrs_hole_programme(kanal, tage=1):
    """Liefert die Programmdaten fuer den gegebenen Kanal (Dict aus
    tvprogramrs_kanal_finden()). `tage` wird ignoriert (> 1 sinnlos, die
    Quelle liefert ohnehin nur den aktuellen Tag). Leere Liste bei
    jedem Fehler."""
    if not kanal:
        return []
    return _seite_laden(kanal)
