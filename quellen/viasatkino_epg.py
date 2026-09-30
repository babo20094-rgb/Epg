"""Echte Programmdaten fuer "Viasat Kino" (RS, frueher/alias "TV1000")
von viasatkino.rs - AUTOMATISCH fuer jeden RS-Sender, dessen Name auf
"VIASAT KINO" ODER "TV1000" passt (mit oder ohne HD/VIP/RAW-Zusaetzen).
Kein eigenes Praefix noetig. Der Sendername "TV1000" ist bewusst als
Alias mitgefuehrt: es ist historisch derselbe Kanal, nur umbenannt -
sollte in sender.txt versehentlich wieder "TV1000" statt "VIASAT KINO"
auftauchen (Playlist-Rueckfall, Tippfehler, ...), bekommt er trotzdem
automatisch dieselben echten Programmdaten von derselben Quelle.

https://viasatkino.rs/?date=YYYY-MM-DD#tv-program liefert - server-
seitig bereits gerendert - den Tagesplan fuer GENAU DEN EINEN im
Query-Parameter angegebenen Tag, aufgeteilt in vier Tageszeit-Tabs
(JUTRO/PREPODNE/POPODNE/VECE), aber alle vier Tabs stehen bereits
vollstaendig im HTML (nur CSS/JS blendet die inaktiven Tabs aus - kein
eigenes Tab-Handling noetig). Jede Sendung steckt in einem
<div class="schedule-box">...</div> mit Uhrzeit (<li><i class="bi
bi-clock"></i> HH:MM</li>), Titel (<h3><span>...</span></h3>) und
Kurzbeschreibung (<p>...</p>). Die Endzeit steht nirgends im HTML -
sie wird wie bei rtv_rs_epg.py/axn_epg.py aus dem Start der jeweils
naechsten Sendung abgeleitet (letzte Sendung eines Tages: Start der
ersten Sendung des naechsten geladenen Tages, sonst Fallback +2h).

Es wird pro Tag ein eigener Seitenabruf gebraucht (kein Mehrtages-
Sendeplan in einem Request wie bei axntv.rs). Wird pro Lauf nur EINMAL
geladen und geparst (Modul-weiter Cache ueber alle Tage hinweg, analog
zu den anderen *_epg.py-Quellen).

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt Download, Parsen
oder Kanalsuche fehl, bekommt der betroffene Sender in generate_epg.py
einfach die normale, kategoriebasierte generische EPG-Generierung wie
jeder andere Sender - dieses Modul darf einen Lauf niemals zum Absturz
bringen.
"""

from datetime import datetime, timedelta, timezone

import re
import unicodedata

import requests
from quellen import _http
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

BASIS_URL = "https://viasatkino.rs/"

REQUEST_TIMEOUT_SEKUNDEN = 20

TZ_BELGRADE = ZoneInfo("Europe/Belgrade")

# Anzahl der zu ladenden Tage (heute + Folgetage) - die Website bietet
# selbst deutlich mehr Tage an, mehr Tage bedeuten aber mehr Requests
# pro Lauf, daher bewusst knapp gehalten wie bei den anderen Quellen.
_LADE_TAGE = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# "TV1000" ist der historische Vorgaengername desselben Kanals (siehe
# Moduldocstring) - beide Namen werden als Alias erkannt.
_VIASAT_KINO_PATTERN = re.compile(r"^(VIASAT\s*KINO|TV\s*1000)\b", re.IGNORECASE)

# Modul-weiter Cache: None (noch nicht geladen) oder die geladene
# Programmliste - viasatkino.rs fuehrt aktuell nur den einen Kanal.
_programme_cache = None


def _vip_raw_hd_entfernen(name):
    """Entfernt die playlist-eigenen Deko-Marker "VIP"/"RAW"/"HD"/"FHD"
    (auch in hochgestellter Unicode-Schreibweise wie "ⱽᴵᴾ ᴿᴬᵂ" - NFKD
    zerlegt diese zu normalen Buchstaben), analog zu axn_epg.py."""
    zerlegt = unicodedata.normalize("NFKD", name)
    zerlegt = "".join(z for z in zerlegt if not unicodedata.combining(z))
    return re.sub(r"\bVIP\b|\bRAW\b|\bF?HD\b", " ", zerlegt, flags=re.IGNORECASE).strip()


def viasatkino_kanal_finden(kanalname):
    """Erkennt "VIASAT KINO" bzw. den Alias "TV1000" (mit beliebigen
    Whitespace-/HD/FHD/VIP/RAW-Zusaetzen) und gibt dafuer ein festes
    Markersignal zurueck, sonst None. Nur EIN Kanal wird von dieser
    Quelle ueberhaupt gefuehrt, daher genuegt ein einfacher Praefix-
    Vergleich (kein Fuzzy-Abgleich, kein Fehltreffer-Risiko)."""
    name = _vip_raw_hd_entfernen(kanalname.strip())
    name = re.sub(r"\s+", " ", name)

    if not _VIASAT_KINO_PATTERN.match(name):
        return None

    return "kino"


def _text_bereinigen(tag):
    if tag is None:
        return ""
    return re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()


def _tag_laden(tag_datum):
    """Laedt und parst den Tagesplan fuer genau den gegebenen Tag
    (Europe/Belgrade). Liefert eine Liste von {"start_lokal", "titel",
    "beschreibung"}-Dicts, oder [] bei jedem Fehler."""
    try:
        url = f"{BASIS_URL}?date={tag_datum.isoformat()}"
        response = _http.mit_retry(requests.get, url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        container = soup.select_one("#tv-program")
        if container is None:
            return []

        eintraege = []
        for box in container.select("div.schedule-box"):
            zeit_tag = box.select_one("li i.bi-clock")
            if zeit_tag is None:
                continue
            zeile = zeit_tag.parent.get_text(" ", strip=True)
            zeit_treffer = re.search(r"(\d{1,2}):(\d{2})", zeile)
            if not zeit_treffer:
                continue

            titel = _text_bereinigen(box.select_one("h3"))
            if not titel:
                continue

            beschreibung = _text_bereinigen(box.select_one("p"))
            if not beschreibung:
                beschreibung = titel

            start_lokal = datetime(
                tag_datum.year, tag_datum.month, tag_datum.day,
                int(zeit_treffer.group(1)), int(zeit_treffer.group(2)),
                tzinfo=TZ_BELGRADE,
            )
            eintraege.append({
                "start_lokal": start_lokal,
                "titel": titel,
                "beschreibung": beschreibung,
            })

        return eintraege
    except Exception as e:
        print(f"Viasat-Kino-EPG ({tag_datum.isoformat()}): Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        return []


def _laden():
    """Laedt und parst (und cached) die Tagesplaene der naechsten
    `_LADE_TAGE` Tage (Europe/Belgrade). Liefert eine Liste von
    {"title", "beschreibung", "bild", "start", "stop"}-Dicts (UTC),
    oder [] bei jedem Fehler."""
    global _programme_cache
    if _programme_cache is not None:
        return _programme_cache

    heute = datetime.now(TZ_BELGRADE).date()
    rohe_eintraege = []
    for i in range(_LADE_TAGE):
        rohe_eintraege.extend(_tag_laden(heute + timedelta(days=i)))

    rohe_eintraege.sort(key=lambda e: e["start_lokal"])

    programme = []
    for i, eintrag in enumerate(rohe_eintraege):
        start = eintrag["start_lokal"].astimezone(timezone.utc)
        if i + 1 < len(rohe_eintraege):
            stop = rohe_eintraege[i + 1]["start_lokal"].astimezone(timezone.utc)
        else:
            stop = start + timedelta(hours=2)
        if stop <= start:
            continue
        programme.append({
            "title": eintrag["titel"],
            "beschreibung": eintrag["beschreibung"],
            "bild": None,
            "start": start,
            "stop": stop,
        })

    print(f"Viasat-Kino-EPG: {len(programme)} Sendungen geladen.")
    _programme_cache = programme
    return programme


def viasatkino_hole_programme(schluessel, tage=2):
    """Liefert die bereits geladenen Programmdaten, begrenzt auf die
    naechsten `tage` Kalendertage ab heute (Europe/Belgrade).
    `schluessel` wird nur als Signatur-Parameter mitgefuehrt (analog zu
    den anderen *_hole_programme()-Funktionen), viasatkino.rs kennt
    aktuell nur den einen Kanal "kino". Leere Liste bei jedem Fehler."""
    if not schluessel:
        return []

    eintraege = _laden()
    if not eintraege:
        return []

    heute = datetime.now(TZ_BELGRADE).date()
    erlaubte_tage = {heute + timedelta(days=i) for i in range(tage)}

    return [
        p for p in eintraege
        if p["start"].astimezone(TZ_BELGRADE).date() in erlaubte_tage
        or p["stop"].astimezone(TZ_BELGRADE).date() in erlaubte_tage
    ]
