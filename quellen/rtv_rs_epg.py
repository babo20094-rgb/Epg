"""Echte Programmdaten fuer RT Vojvodina 1/2 (oeffentlicher Sender aus
Novi Sad, Serbien) von www.rtv.rs - AUTOMATISCH fuer jeden RS-Sender,
dessen Name auf "RT VOJVODINA 1/2" bzw. "RTV VOJVODINA 1/2" passt (mit
oder ohne HD/VIP/RAW-Zusaetze). Kein eigenes Praefix noetig.

Die "/satnica"-Unterseite von rtv.rs (z.B.
rtv.rs/sr_lat/program/prvi-program/satnica) liefert - im Unterschied zur
normalen Programmseite, die nur ein kurzes "naechste Sendungen"-Fenster
zeigt - EINEN mehrtaegigen Tagesplan mit einem <li data-date="..."> pro
Tag und je einem zugehoerigen Tab-Panel mit Uhrzeit+Titel pro Sendung.
Wird nur EINMAL pro Kanal und Lauf geladen und geparst (Modul-weiter
Cache pro Slug, analog zu sportklub_epg.py).

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

BASIS_URL = "https://www.rtv.rs/sr_lat/program/{slug}/satnica"

REQUEST_TIMEOUT_SEKUNDEN = 20

TZ_BELGRADE = ZoneInfo("Europe/Belgrade")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# Kanal-Nummer (1 oder 2) -> URL-Slug bei rtv.rs.
_SLUGS = {
    "1": "prvi-program",
    "2": "drugi-program",
}

_NUMMER_PATTERN = re.compile(
    r"^RTV?\s+VOJVODINA\s*0*([12])\b", re.IGNORECASE
)

# Modul-weiter Cache: {slug: [programme...]}
_programme_cache = {}


def _vip_raw_entfernen(name):
    """Entfernt die playlist-eigenen Deko-Marker "VIP"/"RAW" (auch in
    hochgestellter Unicode-Schreibweise wie "ⱽᴵᴾ ᴿᴬᵂ" - NFKD zerlegt
    diese zu normalen Buchstaben), analog zu sportklub_epg.py."""
    zerlegt = unicodedata.normalize("NFKD", name)
    zerlegt = "".join(z for z in zerlegt if not unicodedata.combining(z))
    return re.sub(r"\bVIP\b|\bRAW\b|\bHD\b", " ", zerlegt, flags=re.IGNORECASE).strip()


def rtv_rs_kanal_finden(kanalname):
    """Erkennt "RT VOJVODINA 1/2" bzw. "RTV VOJVODINA 1/2" (mit
    beliebigen Whitespace-/HD/VIP/RAW-Zusaetzen) und liefert den
    passenden rtv.rs-Slug zurueck, sonst None. Exakter Nummern-
    Vergleich, kein Fuzzy-Abgleich (kein Fehltreffer-Risiko)."""
    name = _vip_raw_entfernen(kanalname.strip())
    name = re.sub(r"\s+", " ", name)

    treffer = _NUMMER_PATTERN.match(name)
    if not treffer:
        return None

    return _SLUGS.get(treffer.group(1))


def _titel_und_beschreibung(show_tag):
    """Extrahiert Titel (ohne die eingebettete <span class="titleExtension">)
    und volle Beschreibung (Titel + Extension) aus einem psItemShow-Tag."""
    extension_tag = show_tag.find("span", class_="titleExtension")
    extension_text = extension_tag.get_text(strip=True) if extension_tag else ""
    if extension_tag is not None:
        extension_tag.extract()

    titel = show_tag.get_text(strip=True)
    if not titel:
        return "", ""

    if extension_text:
        extension_text = extension_text.lstrip(",").strip()
        beschreibung = f"{titel}: {extension_text}" if extension_text else titel
    else:
        beschreibung = titel

    return titel, beschreibung


def _satnica_laden(slug):
    """Laedt und parst (und cached) den kompletten mehrtaegigen
    Tagesplan fuer den gegebenen Slug. Liefert eine Liste von
    {"title", "beschreibung", "bild", "start", "stop"}-Dicts (UTC),
    oder [] bei jedem Fehler."""
    if slug in _programme_cache:
        return _programme_cache[slug]

    try:
        url = BASIS_URL.format(slug=slug)
        response = _http.mit_retry(requests.get, url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        rohe_eintraege = []
        for tab in soup.select("li.nav-item[data-date]"):
            datum_roh = (tab.get("data-date") or "").strip().rstrip(".")
            link = tab.find("a")
            if not link:
                continue
            ziel = (link.get("href") or "").lstrip("#")
            if not ziel:
                continue
            panel = soup.find(id=ziel)
            if not panel:
                continue

            teile = datum_roh.split(".")
            if len(teile) != 3:
                continue
            try:
                tag, monat, jahr = (int(t.strip()) for t in teile)
            except ValueError:
                continue

            for item in panel.select("div.psItem"):
                zeit_tag = item.find("div", class_="psItemTime")
                show_tag = item.find("div", class_="psItemShow")
                if not zeit_tag or not show_tag:
                    continue

                zeit_treffer = re.match(r"^(\d{1,2}):(\d{2})$", zeit_tag.get_text(strip=True))
                if not zeit_treffer:
                    continue

                titel, beschreibung = _titel_und_beschreibung(show_tag)
                if not titel:
                    continue

                start_lokal = datetime(
                    jahr, monat, tag,
                    int(zeit_treffer.group(1)), int(zeit_treffer.group(2)),
                    tzinfo=TZ_BELGRADE,
                )
                rohe_eintraege.append({
                    "start_lokal": start_lokal,
                    "titel": titel,
                    "beschreibung": beschreibung,
                })

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
                "beschreibung": eintrag["beschreibung"],
                "bild": None,
                "start": start,
                "stop": stop,
            })

        print(f"RTV.rs-EPG ({slug}): {len(programme)} Sendungen geladen.")
        _programme_cache[slug] = programme
        return programme
    except Exception as e:
        print(f"RTV.rs-EPG ({slug}): Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _programme_cache[slug] = []
        return []


def rtv_rs_hole_programme(slug, tage=2):
    """Liefert die bereits geladenen Programmdaten fuer den gegebenen
    Slug, begrenzt auf die naechsten `tage` Tage ab heute (UTC). Leere
    Liste bei jedem Fehler oder wenn keine Sendungen vorhanden sind."""
    if not slug:
        return []

    eintraege = _satnica_laden(slug)
    if not eintraege:
        return []

    heute = datetime.now(timezone.utc).date()
    erlaubte_tage = {heute + timedelta(days=i) for i in range(tage)}

    return [
        p for p in eintraege
        if p["start"].date() in erlaubte_tage or p["stop"].date() in erlaubte_tage
    ]
