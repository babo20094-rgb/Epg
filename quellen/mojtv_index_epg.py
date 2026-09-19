"""Echte Programmdaten fuer 26 feste HR-Sender von index.hr/info/tv -
AUTOMATISCH fuer jede sender.txt-Zeile, deren (HD/FHD/VIP/RAW-bereinigter)
Name exakt einem der unten gelisteten Kanaele entspricht. Kein eigenes
Praefix noetig.

https://www.index.hr/info/tv?datum=DDMMYYYY&grupa=N spiegelt server-
seitig gerendert dieselben Daten wie mojtv.hr (dessen Original-Website
per Cloudflare auch aus GitHub Actions blockiert wird, siehe
docs/HISTORIE.md) - index.hr selbst ist NICHT geblockt. Die Seite
listet je Abruf GENAU EINEN Kalendertag UND GENAU EINE der 7 festen
Kanal-Gruppen (`grupa=1..7`, siehe `_KANAL_NAMEN` unten - Reihenfolge
und Gruppierung sind auf der Seite fest vorgegeben, keine eigene
Auswahl moeglich). Ein Kanal wird daher ueber (grupa, Index-innerhalb-
der-Gruppe) referenziert.

Exakter Namensabgleich (kein Fuzzy-Abgleich) - die 26 Kanalnamen sind
kurz und mehrdeutig genug (z.B. "RTL" vs. "RTL 2" vs. "RTL KOCKICA" vs.
"RTL ADRIA"), dass ein unscharfer Abgleich hier ein echtes Fehltreffer-
Risiko waere.

Wird gruppen- und tagesweise gecacht (Modul-weiter Cache
{(grupa, tag_offset): [(name, [(zeit, titel), ...]), ...]}), damit
mehrere Sender derselben Gruppe/desselben Tages nur EINEN Netzwerk-
Abruf ausloesen.

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

BASIS_URL = "https://www.index.hr/info/tv"

# Feste Kanal-Gruppen wie auf der Seite vorgegeben (Reihenfolge = Index
# innerhalb der Gruppe, entspricht der Reihenfolge der <div class="channel">
# -Bloecke im HTML).
_KANAL_NAMEN = {
    1: ["HRT 1", "HRT 2", "NOVA TV", "RTL"],
    2: ["DOMA TV", "RTL 2", "RTL KOCKICA", "Z1"],
    3: ["HRT 3", "HRT 4", "CMC", "JABUKA TV"],
    4: ["HBO", "STAR LIFE", "STAR CRIME", "TV 1000"],
    5: ["CINESTAR TV 1", "CINESTAR TV 2", "CINESTAR TV PREMIERE 1", "CINESTAR TV PREMIERE 2"],
    6: ["CINESTAR TV ACTION & THRILLER", "CINESTAR TV FANTASY", "CINESTAR TV COMEDY & FAMILY"],
    7: ["NATIONAL GEOGRAPHIC", "DOKU TV", "DISCOVERY CHANNEL", "VIASAT HISTORY"],
}

# sender.txt-Schreibweise -> Kanal-Name laut index.hr (nur wo abweichend).
_ALIASE = {
    "NATIONAL GEO": "NATIONAL GEOGRAPHIC",
}

REQUEST_TIMEOUT_SEKUNDEN = 20

TZ_ZAGREB = ZoneInfo("Europe/Zagreb")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# Modul-weiter Cache: {(grupa, tag_offset): [(name, [(zeit, titel), ...]), ...]}
_seiten_cache = {}


def _vip_raw_hd_entfernen(name):
    """Entfernt die playlist-eigenen Deko-Marker "VIP"/"RAW"/"HD"/"FHD"
    (auch in hochgestellter Unicode-Schreibweise wie "ⱽᴵᴾ ᴿᴬᵂ" - NFKD
    zerlegt diese zu normalen Buchstaben)."""
    zerlegt = unicodedata.normalize("NFKD", name)
    zerlegt = "".join(z for z in zerlegt if not unicodedata.combining(z))
    return re.sub(r"\bVIP\b|\bRAW\b|\bF?HD\b", " ", zerlegt, flags=re.IGNORECASE).strip()


def mojtv_index_kanal_finden(kanalname):
    """Erkennt einen der 26 festen index.hr-Kanaele per EXAKTEM Namens-
    abgleich (nach VIP/RAW/HD/FHD-Entfernung, Leerzeichen-Normalisierung
    und Grossschreibung) und gibt "<grupa>:<index>" zurueck, sonst
    None."""
    name = _vip_raw_hd_entfernen(kanalname.strip())
    name = re.sub(r"\s+", " ", name).upper()
    name = re.sub(r"\s*&\s*", " & ", name)
    name = _ALIASE.get(name, name)

    for grupa, namen in _KANAL_NAMEN.items():
        if name in namen:
            return f"{grupa}:{namen.index(name)}"

    return None


def _zeit_und_titel_parsen(show_div):
    zeit_tag = show_div.select_one(".time-part")
    titel_tag = show_div.select_one(".data-part .title")
    if not zeit_tag or not titel_tag:
        return None
    zeit_text = re.sub(r"\s+", "", zeit_tag.get_text(strip=True))
    treffer = re.match(r"^(\d{1,2}):(\d{2})$", zeit_text)
    if not treffer:
        return None
    titel = re.sub(r"\s+", " ", titel_tag.get_text(" ", strip=True)).strip()
    if not titel:
        return None
    return int(treffer.group(1)), int(treffer.group(2)), titel


def _seite_laden(grupa, tag_offset):
    """Laedt und parst (und cached) EINE Gruppen-/Tages-Seite. Liefert
    eine Liste von (Kanalname, [(stunde, minute, titel), ...])-Tupeln
    in Gruppen-Reihenfolge, oder [] bei jedem Fehler."""
    cache_schluessel = (grupa, tag_offset)
    if cache_schluessel in _seiten_cache:
        return _seiten_cache[cache_schluessel]

    try:
        tag_datum = datetime.now(TZ_ZAGREB).date() + timedelta(days=tag_offset)
        datum_text = tag_datum.strftime("%d%m%Y")

        response = _http.mit_retry(
            requests.get, BASIS_URL,
            params={"datum": datum_text, "grupa": grupa},
            headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        holder = soup.select_one(".channels-data-holder")
        if holder is None:
            _seiten_cache[cache_schluessel] = []
            return []

        namen = _KANAL_NAMEN.get(grupa, [])
        ergebnis = []
        for i, kanal_div in enumerate(holder.select(".channel")):
            name = namen[i] if i < len(namen) else f"grupa{grupa}_{i}"
            eintraege = []
            for show_div in kanal_div.select(".show"):
                geparst = _zeit_und_titel_parsen(show_div)
                if geparst is not None:
                    eintraege.append(geparst)
            ergebnis.append((name, eintraege))

        _seiten_cache[cache_schluessel] = ergebnis
        return ergebnis
    except Exception as e:
        print(f"index.hr-EPG: Laden/Parsen fehlgeschlagen (Gruppe {grupa}, Tag {tag_offset}: {e}), ueberspringe.")
        _seiten_cache[cache_schluessel] = []
        return []


def mojtv_index_hole_programme(schluessel, tage=2):
    """Liefert die Programmdaten fuer die naechsten `tage` Tage ab heute
    (Europe/Zagreb). Leere Liste bei jedem Fehler."""
    if not schluessel:
        return []

    try:
        grupa_text, index_text = schluessel.split(":")
        grupa, index = int(grupa_text), int(index_text)
    except (ValueError, AttributeError):
        return []

    heute = datetime.now(TZ_ZAGREB).date()

    rohe_eintraege = []
    # Ein Tag zusaetzlich, um die Endzeit der letzten Sendung des
    # angefragten Zeitraums aus dem naechsten (noch folgenden) Eintrag
    # berechnen zu koennen.
    for tag_offset in range(tage + 1):
        kanaele = _seite_laden(grupa, tag_offset)
        if index >= len(kanaele):
            continue
        _, eintraege = kanaele[index]
        tag_datum = heute + timedelta(days=tag_offset)
        for stunde, minute, titel in eintraege:
            start_lokal = datetime(
                tag_datum.year, tag_datum.month, tag_datum.day,
                stunde, minute, tzinfo=TZ_ZAGREB,
            )
            rohe_eintraege.append({"start_lokal": start_lokal, "titel": titel})

    # Nach Startzeit sortieren (jeder Tag ist einzeln chronologisch,
    # aber die Tage selbst werden hier nur angehaengt).
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

    erlaubte_tage = {heute + timedelta(days=i) for i in range(tage)}
    return [
        p for p in programme
        if p["start"].astimezone(TZ_ZAGREB).date() in erlaubte_tage
        or p["stop"].astimezone(TZ_ZAGREB).date() in erlaubte_tage
    ]
