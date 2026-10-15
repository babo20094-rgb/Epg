"""Echte Programmdaten fuer den Sender "Syfy" (RS) von scifi.rs
(NBCUniversal-EPG-Widget) - AUTOMATISCH fuer jeden RS-Sender, dessen
Name auf "SYFY" passt (mit oder ohne HD/FHD/VIP/RAW-Zusaetzen). Kein
eigenes Praefix noetig, laeuft als weiterer Schritt der RS-Kaskade in
generate_epg.py (nach mts.rs/SportKlub/Arena/RTV.rs).

Die scifi.rs-Single-Page-App laedt ihre Tagesdaten client-seitig direkt
als statische JSON-Datei von CloudFront:
https://d16grqjkf2kebt.cloudfront.net/sci-fi-serbia/DD-MM-YYYY.json
(Datumsformat exakt wie in der URL, gefunden ueber die im JS-Bundle
eingebetteten VITE_CDN_URL/VITE_EPGNAME-Konstanten). Kein API-Key/Auth
noetig, eine Datei pro Kalendertag, kein mehrtaegiger Endpunkt.

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
from zoneinfo import ZoneInfo

BASIS_URL = "https://d16grqjkf2kebt.cloudfront.net/sci-fi-serbia/{datum}.json"

REQUEST_TIMEOUT_SEKUNDEN = 20

TZ_BELGRADE = ZoneInfo("Europe/Belgrade")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_SYFY_PATTERN = re.compile(r"^SYFY\b", re.IGNORECASE)

# Modul-weiter Cache: {"DD-MM-YYYY": [programme...]}
_tag_cache = {}


def _vip_raw_hd_entfernen(name):
    """Entfernt die playlist-eigenen Deko-Marker "VIP"/"RAW"/"HD"/"FHD"
    (auch in hochgestellter Unicode-Schreibweise wie "ⱽᴵᴾ ᴿᴬᵂ" - NFKD
    zerlegt diese zu normalen Buchstaben), analog zu rtv_rs_epg.py."""
    zerlegt = unicodedata.normalize("NFKD", name)
    zerlegt = "".join(z for z in zerlegt if not unicodedata.combining(z))
    return re.sub(r"\bVIP\b|\bRAW\b|\bF?HD\b", " ", zerlegt, flags=re.IGNORECASE).strip()


def scifi_kanal_finden(kanalname):
    """Erkennt "Syfy" (mit beliebigen Whitespace-/HD/FHD/VIP/RAW-
    Zusaetzen) und gibt dafuer ein festes Markersignal zurueck, sonst
    None. Nur EIN Kanal wird von dieser Quelle ueberhaupt gefuehrt,
    daher genuegt ein einfacher Praefix-Vergleich (kein Fuzzy-Abgleich,
    kein Fehltreffer-Risiko)."""
    name = _vip_raw_hd_entfernen(kanalname.strip())
    name = re.sub(r"\s+", " ", name)

    if not _SYFY_PATTERN.match(name):
        return None

    return "sci-fi-serbia"


def _tag_laden(datum):
    """Laedt und parst (und cached) die JSON-Datei fuer genau einen
    Kalendertag (datum als datetime.date). Liefert eine Liste von
    {"title", "beschreibung", "bild", "start", "stop"}-Dicts (UTC),
    oder [] bei jedem Fehler."""
    datum_str = datum.strftime("%d-%m-%Y")
    if datum_str in _tag_cache:
        return _tag_cache[datum_str]

    try:
        url = BASIS_URL.format(datum=datum_str)
        response = _http.mit_retry(requests.get, url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        rohe_sendungen = response.json()

        eintraege = []
        for sendung in rohe_sendungen:
            zeit_treffer = re.match(r"^(\d{1,2}):(\d{2})$", (sendung.get("time") or "").strip())
            titel = (sendung.get("title") or "").strip()
            if not zeit_treffer or not titel:
                continue

            try:
                dauer_minuten = int(sendung.get("duration") or 0)
            except (TypeError, ValueError):
                dauer_minuten = 0
            if dauer_minuten <= 0:
                continue

            synopsis = sendung.get("synopsis")
            if isinstance(synopsis, dict):
                beschreibung = (synopsis.get("_") or "").strip()
            else:
                beschreibung = (synopsis or "").strip()
            if not beschreibung:
                beschreibung = titel

            start_lokal = datetime(
                datum.year, datum.month, datum.day,
                int(zeit_treffer.group(1)), int(zeit_treffer.group(2)),
                tzinfo=TZ_BELGRADE,
            )
            start = start_lokal.astimezone(timezone.utc)
            stop = start + timedelta(minutes=dauer_minuten)

            eintraege.append({
                "title": titel,
                "beschreibung": beschreibung,
                "bild": None,
                "start": start,
                "stop": stop,
            })

        print(f"scifi.rs-EPG ({datum_str}): {len(eintraege)} Sendungen geladen.")
        _tag_cache[datum_str] = eintraege
        return eintraege
    except Exception as e:
        print(f"scifi.rs-EPG ({datum_str}): Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _tag_cache[datum_str] = []
        return []


def scifi_hole_programme(slug, tage=2):
    """Liefert die Programmdaten fuer die naechsten `tage` Kalendertage
    ab heute (Europe/Belgrade). `slug` wird nur als Signatur-Parameter
    mitgefuehrt (analog zu den anderen *_hole_programme()-Funktionen),
    scifi.rs kennt aktuell nur den einen Kanal "sci-fi-serbia". Leere
    Liste bei jedem Fehler."""
    if not slug:
        return []

    heute = datetime.now(TZ_BELGRADE).date()
    programme = []
    for i in range(tage):
        programme.extend(_tag_laden(heute + timedelta(days=i)))
    return programme
