"""Echte Programmdaten fuer "Pickbox" (RS) UND "Pickbox TV" (HR) von
pickbox.tv - AUTOMATISCH fuer jeden RS/HR-Sender, dessen Name auf
"PICKBOX" passt (mit oder ohne HD/FHD/VIP/RAW-Zusaetzen); der Name-
Zusatz "TV" waehlt den HR-Kanal-Slug (beide Kanaele laufen auf
derselben Website, nur unter verschiedenen Sprach-Pfaden). Kein
eigenes Praefix noetig.

https://pickbox.tv/{sr,hr}/raspored/ liefert - server-seitig bereits
gerendert - einen kompletten mehrtaegigen Sendeplan in EINEM
Seitenabruf: ein Tages-Umschalter (`.epg-days-holders`, je ein Datum)
plus ein gleich langer Satz direkter Kind-<div>s unter
`.epg-content-information` (JS-Slider-Slides, aber im HTML bereits
alle vorhanden), jeder mit den Sendungen (`.epg-article-item-holder`)
genau dieses einen Tages. Sendezeiten sind lokale Belgrader Zeit,
Sendetage laufen von 06:00 bis 05:5x Uhr des naechsten Kalendertags
(TV-Sendetag-Konvention) - ein Mitternachts-Ueberlauf wird erkannt,
wenn die Uhrzeit gegenueber der vorherigen Sendung "zurueckspringt".

Endzeit wird aus dem Start der naechsten Sendung berechnet (letzte
Sendung des gesamten Zeitraums endet 1h nach ihrem Start), analog zu
klix_epg.py/arena_epg.py.

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

BASIS_URL = "https://pickbox.tv/{sprachpfad}/raspored/"

# Sendername-Praefix-Schluessel -> pickbox.tv-Sprachpfad.
_SPRACHPFADE = {
    "rs": "sr",
    "hr": "hr",
}

REQUEST_TIMEOUT_SEKUNDEN = 20

TZ_BELGRADE = ZoneInfo("Europe/Belgrade")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# "Pickbox TV" (HR) muss VOR dem allgemeinen "Pickbox"-Muster (RS)
# geprueft werden, sonst wuerde es faelschlich als RS erkannt.
_PICKBOX_HR_PATTERN = re.compile(r"^PICKBOX\s*TV\b", re.IGNORECASE)
_PICKBOX_PATTERN = re.compile(r"^PICKBOX\b", re.IGNORECASE)

# Modul-weiter Cache je Sprachpfad-Schluessel: {"rs": [...], "hr": [...]}
_programme_cache = {}


def _vip_raw_hd_entfernen(name):
    """Entfernt die playlist-eigenen Deko-Marker "VIP"/"RAW"/"HD"/"FHD"
    (auch in hochgestellter Unicode-Schreibweise wie "ⱽᴵᴾ ᴿᴬᵂ" - NFKD
    zerlegt diese zu normalen Buchstaben)."""
    zerlegt = unicodedata.normalize("NFKD", name)
    zerlegt = "".join(z for z in zerlegt if not unicodedata.combining(z))
    return re.sub(r"\bVIP\b|\bRAW\b|\bF?HD\b", " ", zerlegt, flags=re.IGNORECASE).strip()


def pickbox_kanal_finden(kanalname):
    """Erkennt "Pickbox" (RS) bzw. "Pickbox TV" (HR) (mit beliebigen
    Whitespace-/HD/FHD/VIP/RAW-Zusaetzen) und gibt den passenden
    Schluessel ("rs"/"hr") zurueck, sonst None. Einfacher Praefix-
    Vergleich (kein Fuzzy-Abgleich, kein Fehltreffer-Risiko)."""
    name = _vip_raw_hd_entfernen(kanalname.strip())
    name = re.sub(r"\s+", " ", name)

    if _PICKBOX_HR_PATTERN.match(name):
        return "hr"
    if _PICKBOX_PATTERN.match(name):
        return "rs"

    return None


def _text_bereinigen(tag):
    if tag is None:
        return ""
    return re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()


def _seite_laden(schluessel):
    """Laedt und parst (und cached) den mehrtaegigen Sendeplan fuer den
    gegebenen Sprachpfad-Schluessel ("rs"/"hr"). Liefert eine Liste von
    {"title", "beschreibung", "bild", "start", "stop"}-Dicts (UTC),
    oder [] bei jedem Fehler."""
    if schluessel in _programme_cache:
        return _programme_cache[schluessel]

    sprachpfad = _SPRACHPFADE.get(schluessel)
    if not sprachpfad:
        return []

    try:
        url = BASIS_URL.format(sprachpfad=sprachpfad)
        response = _http.mit_retry(requests.get, url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        tage_daten = []
        for holder in soup.select(".epg-days-holders"):
            span = holder.find("span")
            datum_text = _text_bereinigen(span)
            teile = datum_text.split(".")
            if len(teile) != 3:
                continue
            try:
                tag, monat, jahr = (int(t.strip()) for t in teile)
            except ValueError:
                continue
            tage_daten.append(datetime(jahr, monat, tag, tzinfo=TZ_BELGRADE))

        inhalt = soup.select_one(".epg-content-information")
        tage_divs = inhalt.find_all("div", recursive=False) if inhalt else []

        rohe_eintraege = []
        aktuelles_datum = None
        for tag_datum, tag_div in zip(tage_daten, tage_divs):
            aktuelles_datum = tag_datum
            letzte_zeit_minuten = None
            for item in tag_div.select(".epg-article-item-holder"):
                zeit_span = item.select_one(".time-epg-holder span")
                titel_tag = item.select_one(".epg-local-title")
                original_tag = item.select_one(".epg-original-title")
                if not zeit_span or not titel_tag:
                    continue

                zeit_treffer = re.match(r"^(\d{1,2}):(\d{2})$", _text_bereinigen(zeit_span))
                titel = _text_bereinigen(titel_tag)
                if not zeit_treffer or not titel:
                    continue

                stunde, minute = int(zeit_treffer.group(1)), int(zeit_treffer.group(2))
                zeit_minuten = stunde * 60 + minute
                if letzte_zeit_minuten is not None and zeit_minuten < letzte_zeit_minuten:
                    aktuelles_datum = aktuelles_datum + timedelta(days=1)
                letzte_zeit_minuten = zeit_minuten

                start_lokal = aktuelles_datum.replace(hour=stunde, minute=minute, second=0, microsecond=0)
                original = _text_bereinigen(original_tag)
                beschreibung = f"{titel}: {original}" if original and original != titel else titel

                rohe_eintraege.append({
                    "start_lokal": start_lokal,
                    "titel": titel,
                    "beschreibung": beschreibung,
                })

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
                "beschreibung": eintrag["beschreibung"],
                "bild": None,
                "start": start,
                "stop": stop,
            })

        print(f"Pickbox-EPG ({sprachpfad}): {len(programme)} Sendungen geladen.")
        _programme_cache[schluessel] = programme
        return programme
    except Exception as e:
        print(f"Pickbox-EPG ({sprachpfad}): Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _programme_cache[schluessel] = []
        return []


def pickbox_hole_programme(schluessel, tage=2):
    """Liefert die bereits geladenen Programmdaten fuer die naechsten
    `tage` Tage ab heute (Europe/Belgrade). Leere Liste bei jedem
    Fehler."""
    if not schluessel:
        return []

    eintraege = _seite_laden(schluessel)
    if not eintraege:
        return []

    heute = datetime.now(TZ_BELGRADE).date()
    erlaubte_tage = {heute + timedelta(days=i) for i in range(tage)}

    return [
        p for p in eintraege
        if p["start"].astimezone(TZ_BELGRADE).date() in erlaubte_tage
        or p["stop"].astimezone(TZ_BELGRADE).date() in erlaubte_tage
    ]
