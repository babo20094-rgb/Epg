"""Echte Programmdaten von tv.aladin.info (oeffentlicher, loginfreier
serbischer TV-Guide-Anbieter mit 84 Kanaelen) - AUTOMATISCH fuer RS/BA/
HR/SI/MK-Sender, als weiterer Fallback NACH tvprogram.rs (siehe deren
Verarbeitungsblock in generate_epg.py). Kein eigenes sender.txt-Praefix
noetig.

Die Kanalsuche nutzt eine im Repo mitgelieferte statische Datei
(aladin_kanalliste.txt, 84 Eintraege, Zeilenformat "<URL-Slug>|<Name>")
- kein Netzwerk-Request fuer die Kanalsuche selbst. Analog zu
tvprogramrs_epg.py NUR exakter Name- oder Kern-Abgleich (HD/FHD/UHD/SD
entfernt), BEWUSST OHNE unscharfen difflib-Fallback - gleiches
Vorsichtsprinzip wie dort, auch wenn bei dieser Quelle im Test kein
konkreter Fehltreffer beobachtet wurde.

WICHTIG (aus dieser Sandbox nicht direkt verifizierbar): tv.aladin.info
blockiert Abrufe aus der Entwickler-Sandbox mit HTTP 403 (aehnlich wie
z.B. PlutoTV, siehe docs/HISTORIE.md - funktioniert dort nachweislich
trotzdem aus dem echten GitHub-Actions-Runner). Der Seitenaufbau wurde
stattdessen anhand von zwei vom Nutzer bereitgestellten echten
Seiten-Snapshots verifiziert: der Uebersichtsseite (/live, ~3h-
Vorschau je Kanal - dafuer NICHT genutzt, zu kurzes Fenster) und der
vollstaendigen Tagesseite fuer "CineStar TV 1"
(tv-program-cinestar-tv-1, volle ~24h-Tabelle mit "Vreme"/Titel-
Spalten, laeuft ueber Mitternacht). Sollte sich der Seitenaufbau
zukuenftig aendern, degradiert dieses Modul wie jede andere Quelle
graceful auf leere Ergebnisse statt zu werfen.

Wird nur EINMAL pro Kanal und Lauf geladen und geparst (Modul-weiter
Cache pro Slug). Degradiert nach dem gleichen Zero-Risk-Prinzip an
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

BASE_URL = "https://tv.aladin.info/{slug}"

REQUEST_TIMEOUT_SEKUNDEN = 20

TZ_BELGRADE = ZoneInfo("Europe/Belgrade")

KANALLISTE_DATEI = os.path.join(os.path.dirname(__file__), "aladin_kanalliste.txt")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_ZEILE_PATTERN = re.compile(
    r'<td class="text-center strong[^"]*">(\d{1,2}):(\d{2})</td>'
    r'<td[^>]*>(?:<span[^>]*></span>\s*)?([^<]*)</td>'
)

# Die Seite liefert manche Sonderzeichen (Serbische Diakritika wie
# š/đ/č/ć/ž) nicht als echtes UTF-8-Zeichen, sondern buchstaeblich als
# JSON-Style-Escape-Sequenz "\uXXXX" im HTML-Text selbst (bestaetigt am
# echten Seiten-Snapshot: "pušten" statt "pušten") - wird hier
# nachtraeglich in das echte Zeichen umgewandelt.
_UNICODE_ESCAPE_PATTERN = re.compile(r"\\u([0-9a-fA-F]{4})")


def _unicode_escapes_aufloesen(text):
    return _UNICODE_ESCAPE_PATTERN.sub(lambda m: chr(int(m.group(1), 16)), text)

_kanalliste_cache = None
_name_index = None
_kern_index = None
_programme_cache = {}


def _kanalliste_laden():
    """Laedt (und cached) die statische Kanalliste aus
    aladin_kanalliste.txt als Liste von {"slug":..., "name":...}. Leere
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
        print(f"Aladin-EPG: Kanalliste konnte nicht gelesen werden ({e}), ueberspringe.")
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


def aladin_kanal_finden(kanalname):
    """Sucht den tv.aladin.info-Kanal, der zu kanalname passt - NUR
    exakter Abgleich nach normalisiere_sendername(), sonst ein
    eindeutiger Kern-Abgleich ohne HD/FHD/UHD/SD (siehe Moduldocstring).
    Gibt das Kanal-Dict {"slug", "name"} zurueck oder None."""
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
        url = BASE_URL.format(slug=kanal["slug"])
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        html = response.text

        heute = datetime.now(TZ_BELGRADE).date()

        rohe_eintraege = []
        vorherige_stunde = None
        tag_offset = 0
        for stunde_str, minute_str, titel in _ZEILE_PATTERN.findall(html):
            titel = _unicode_escapes_aufloesen(titel.strip())
            if not titel:
                continue

            stunde, minute = int(stunde_str), int(minute_str)
            # Die Tabelle beginnt am fruehen Morgen und laeuft ueber
            # Mitternacht bis in den naechsten Kalendertag - ein
            # Ruecksprung der Stunde markiert den Tageswechsel (analog
            # zu tvprogramrs_epg.py).
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
        print(f"Aladin-EPG: Seitenabruf ({kanal.get('slug')}) fehlgeschlagen ({e}), ueberspringe.")
        _programme_cache[cache_key] = []
        return []


def aladin_hole_programme(kanal, tage=1):
    """Liefert die Programmdaten fuer den gegebenen Kanal (Dict aus
    aladin_kanal_finden()). `tage` wird ignoriert (die Quelle liefert
    ohnehin nur den aktuellen Tag). Leere Liste bei jedem Fehler."""
    if not kanal:
        return []
    return _seite_laden(kanal)
