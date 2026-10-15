"""Echte Programmdaten fuer "AXN Adria" (RS) von axntv.rs/program-tv/ -
AUTOMATISCH fuer jeden RS-Sender, dessen Name auf "AXN ADRIA" passt (mit
oder ohne HD/FHD/VIP/RAW-Zusaetzen). Kein eigenes Praefix noetig, laeuft
als weiterer Schritt der RS-Kaskade in generate_epg.py.

https://axntv.rs/program-tv/ liefert - server-seitig bereits gerendert -
den KOMPLETTEN 14-Tage-Sendeplan in EINEM Seitenabruf: pro Tag ein
<div class="day" id="YYYY-MM-DD_SRP">...</div> mit den einzelnen
Sendungen darin (<div class="program hNN">...</div>, NN = Dauer in
Minuten - direkt aus der CSS-Klasse ablesbar, kein Ableiten aus der
naechsten Sendung noetig).

WICHTIG: die Seite bettet ZWEI komplett unabhaengige Sendeplaene mit
IDENTISCHEN Tages-IDs ein (Kollision auf Website-Seite, kein Fehler
hier) - "AXN Adria" im Container <div id="AXNtimeline"> und "AXN Spin"
im separaten <div id="AXN_spintimeline"> weiter unten auf derselben
Seite. Es wird deshalb GEZIELT nur innerhalb von #AXNtimeline gesucht
(bs4 .find(id=...) faende sonst nur das erste, mehrdeutige Match).
AXN Spin wird hier bewusst NICHT mitgenommen, da der Seiteninhalt dort
inhaltlich nicht zu einem AXN-Spin-Sendeplan passt (Lifestyle-/Immobilien-
Titel statt der erwarteten Action-Serien) - ungeklaerte Divergenz auf
Website-Seite, deshalb ausgeklammert, bis das separat verifiziert ist.

Wird nur EINMAL pro Lauf geladen und geparst (Modul-weiter Cache).

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen - dieses Modul darf einen
Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import re
import unicodedata

import requests
from quellen import _http
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

BASIS_URL = "https://axntv.rs/program-tv/"

REQUEST_TIMEOUT_SEKUNDEN = 20

TZ_BELGRADE = ZoneInfo("Europe/Belgrade")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_AXN_ADRIA_PATTERN = re.compile(r"^AXN\s*ADRIA\b", re.IGNORECASE)

_TAG_ID_PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2})_SRP$")
_DAUER_KLASSE_PATTERN = re.compile(r"^h(\d+)$")

# Modul-weiter Cache: [] (leer bis zum ersten Laden) oder die geladene
# Programmliste - "axntv.rs" kennt aktuell nur den einen Kanal.
_programme_cache = None


def _vip_raw_hd_entfernen(name):
    """Entfernt die playlist-eigenen Deko-Marker "VIP"/"RAW"/"HD"/"FHD"
    (auch in hochgestellter Unicode-Schreibweise wie "ⱽᴵᴾ ᴿᴬᵂ" - NFKD
    zerlegt diese zu normalen Buchstaben), analog zu rtv_rs_epg.py."""
    zerlegt = unicodedata.normalize("NFKD", name)
    zerlegt = "".join(z for z in zerlegt if not unicodedata.combining(z))
    return re.sub(r"\bVIP\b|\bRAW\b|\bF?HD\b", " ", zerlegt, flags=re.IGNORECASE).strip()


def axn_kanal_finden(kanalname):
    """Erkennt "AXN Adria" (mit beliebigen Whitespace-/HD/FHD/VIP/RAW-
    Zusaetzen) und gibt dafuer ein festes Markersignal zurueck, sonst
    None. Nur EIN Kanal wird von dieser Quelle ueberhaupt gefuehrt,
    daher genuegt ein einfacher Praefix-Vergleich (kein Fuzzy-Abgleich,
    kein Fehltreffer-Risiko). Bewusst NICHT fuer blosses "AXN" (ohne
    "Adria") oder "AXN Spin" - das sind andere, eigenstaendige Kanaele."""
    name = _vip_raw_hd_entfernen(kanalname.strip())
    name = re.sub(r"\s+", " ", name)

    if not _AXN_ADRIA_PATTERN.match(name):
        return None

    return "adria"


def _dauer_minuten(css_klassen):
    for klasse in css_klassen:
        treffer = _DAUER_KLASSE_PATTERN.match(klasse)
        if treffer:
            return int(treffer.group(1))
    return None


def _laden():
    """Laedt und parst (und cached) den kompletten Sendeplan von
    axntv.rs/program-tv/ (nur der #AXNtimeline-Container, siehe
    Moduldocstring). Liefert eine Liste von {"title", "beschreibung",
    "bild", "start", "stop"}-Dicts (UTC), oder [] bei jedem Fehler."""
    global _programme_cache
    if _programme_cache is not None:
        return _programme_cache

    try:
        response = _http.mit_retry(requests.get, BASIS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        container = soup.select_one("#AXNtimeline")
        if container is None:
            print("AXN-Adria-EPG: #AXNtimeline nicht gefunden, ueberspringe.")
            _programme_cache = []
            return []

        programme = []
        for tag_div in container.select("div.day"):
            tag_treffer = _TAG_ID_PATTERN.match(tag_div.get("id") or "")
            if not tag_treffer:
                continue
            tag_datum = datetime(
                int(tag_treffer.group(1)), int(tag_treffer.group(2)), int(tag_treffer.group(3))
            ).date()

            for sendung_div in tag_div.select("div.program"):
                dauer_minuten = _dauer_minuten(sendung_div.get("class") or [])
                zeit_tag = sendung_div.select_one(".time")
                titel_tag = sendung_div.select_one(".title")
                if not dauer_minuten or not zeit_tag or not titel_tag:
                    continue

                zeit_treffer = re.match(r"^(\d{1,2}):(\d{2})$", zeit_tag.get_text(strip=True))
                titel = re.sub(r"\s+", " ", titel_tag.get_text(" ", strip=True)).strip()
                if not zeit_treffer or not titel:
                    continue

                desc_tag = sendung_div.select_one(".desc")
                beschreibung = desc_tag.get_text(" ", strip=True).strip() if desc_tag else ""
                if not beschreibung:
                    beschreibung = titel

                start_lokal = datetime(
                    tag_datum.year, tag_datum.month, tag_datum.day,
                    int(zeit_treffer.group(1)), int(zeit_treffer.group(2)),
                    tzinfo=TZ_BELGRADE,
                )
                start = start_lokal.astimezone(timezone.utc)
                stop = start + timedelta(minutes=dauer_minuten)

                programme.append({
                    "title": titel,
                    "beschreibung": beschreibung,
                    "bild": None,
                    "start": start,
                    "stop": stop,
                })

        print(f"AXN-Adria-EPG: {len(programme)} Sendungen geladen.")
        _programme_cache = programme
        return programme
    except Exception as e:
        print(f"AXN-Adria-EPG: Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _programme_cache = []
        return []


def axn_hole_programme(schluessel, tage=2):
    """Liefert die Programmdaten fuer die naechsten `tage` Kalendertage
    ab heute (Europe/Belgrade). `schluessel` wird nur als Signatur-
    Parameter mitgefuehrt (analog zu den anderen *_hole_programme()-
    Funktionen), axntv.rs kennt aktuell nur den einen Kanal "adria".
    Leere Liste bei jedem Fehler."""
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
