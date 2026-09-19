"""Programmdaten fuer "TV Dugaplus" (BA) von tvdugaplus.com -
AUTOMATISCH fuer jeden BA-Sender, dessen Name auf "TV DUGA(-)?PLUS"
passt (mit oder ohne HD/FHD/VIP/RAW-Zusaetzen). Kein eigenes Praefix
noetig.

WICHTIG - andere Datenqualitaet als die uebrigen echten Quellen:
https://www.tvdugaplus.com/o-nama/programska-sema/ liefert KEINEN
tagesaktuellen Sendeplan, sondern einen STATISCHEN, woechentlich
IDENTISCH WIEDERKEHRENDEN Rahmenplan (ein Abschnitt pro Wochentag -
"Ponedeljak".."Nedelja" -, derselbe Plan gilt jede Woche). Die meisten
Zeitbloecke sind ohnehin nur generisches "Muzički program"
(Musikprogramm) ohne eigenen Titel - nur eine Handvoll fester Sendungen
pro Tag (z.B. "Jutarnji program", "Izbor za hit dana") haben einen
eigenen Namen. Der Mehrwert gegenueber der generischen Platzhalter-EPG
ist entsprechend gering, aber echt (Nutzerentscheidung, September
2026).

Wird nur EINMAL pro Lauf geladen und geparst (Modul-weiter Cache) und
dann auf die angefragten Kalendertage projiziert (derselbe
Wochentags-Abschnitt gilt fuer jede Kalenderwoche).

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

BASIS_URL = "https://www.tvdugaplus.com/o-nama/programska-sema/"

REQUEST_TIMEOUT_SEKUNDEN = 20

TZ_SARAJEVO = ZoneInfo("Europe/Sarajevo")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_TVDUGAPLUS_PATTERN = re.compile(r"^TV\s*DUGA\s*-?\s*PLUS\b", re.IGNORECASE)

# Wochentagsname (wie auf der Seite) -> datetime.weekday()-Index
# (Montag=0..Sonntag=6).
_WOCHENTAGE = {
    "PONEDELJAK": 0,
    "UTORAK": 1,
    "SREDA": 2,
    "CETVRTAK": 3,
    "ČETVRTAK": 3,
    "PETAK": 4,
    "SUBOTA": 5,
    "NEDELJA": 6,
}

# Modul-weiter Cache: {wochentag_index: [(stunde, minute, titel), ...]}
_wochenplan_cache = None


def _vip_raw_hd_entfernen(name):
    """Entfernt die playlist-eigenen Deko-Marker "VIP"/"RAW"/"HD"/"FHD"
    (auch in hochgestellter Unicode-Schreibweise wie "ⱽᴵᴾ ᴿᴬᵂ" - NFKD
    zerlegt diese zu normalen Buchstaben)."""
    zerlegt = unicodedata.normalize("NFKD", name)
    zerlegt = "".join(z for z in zerlegt if not unicodedata.combining(z))
    return re.sub(r"\bVIP\b|\bRAW\b|\bF?HD\b", " ", zerlegt, flags=re.IGNORECASE).strip()


def tvdugaplus_kanal_finden(kanalname):
    """Erkennt "TV Duga(-)Plus" (mit beliebigen Whitespace-/HD/FHD/VIP/
    RAW-Zusaetzen, mit oder ohne Bindestrich/Leerzeichen zwischen
    "Duga" und "Plus") und gibt dafuer ein festes Markersignal zurueck,
    sonst None. Nur EIN Kanal wird von dieser Quelle gefuehrt, daher
    genuegt ein einfacher Praefix-Vergleich."""
    name = _vip_raw_hd_entfernen(kanalname.strip())
    name = re.sub(r"\s+", " ", name)

    if not _TVDUGAPLUS_PATTERN.match(name):
        return None

    return "tvdugaplus"


def _zeit_und_titel_parsen(p_tag):
    text = re.sub(r"\s+", " ", p_tag.get_text(" ", strip=True)).strip()
    treffer = re.match(r"^(\d{1,2}):(\d{2})\s*(.*)$", text)
    if not treffer:
        return None
    stunde, minute = int(treffer.group(1)), int(treffer.group(2))
    titel = treffer.group(3).strip().rstrip(",").strip()
    if not titel:
        return None
    return stunde, minute, titel


def _wochenplan_laden():
    """Laedt und parst (und cached) den statischen Wochenplan. Liefert
    ein Dict {wochentag_index: [(stunde, minute, titel), ...]} (nach
    Uhrzeit sortiert), oder {} bei jedem Fehler."""
    global _wochenplan_cache
    if _wochenplan_cache is not None:
        return _wochenplan_cache

    try:
        response = _http.mit_retry(requests.get, BASIS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        container = soup.select_one(".entry-content")

        plan = {}
        aktueller_tag = None
        if container:
            for kind in container.find_all(["h4", "p"], recursive=False):
                if kind.name == "h4":
                    ueberschrift = re.sub(r"\s+", "", kind.get_text(strip=True)).upper()
                    aktueller_tag = _WOCHENTAGE.get(ueberschrift)
                    continue
                if aktueller_tag is None:
                    continue
                geparst = _zeit_und_titel_parsen(kind)
                if geparst is None:
                    continue
                plan.setdefault(aktueller_tag, []).append(geparst)

        for tag_index in plan:
            plan[tag_index].sort(key=lambda e: (e[0], e[1]))

        gesamt = sum(len(v) for v in plan.values())
        print(f"TVDugaplus-EPG: {gesamt} Sendungen im Wochenplan geladen ({len(plan)} Wochentage).")
        _wochenplan_cache = plan
        return plan
    except Exception as e:
        print(f"TVDugaplus-EPG: Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _wochenplan_cache = {}
        return {}


def tvdugaplus_hole_programme(slug, tage=2):
    """Projiziert den statischen Wochenplan auf die naechsten `tage`
    Kalendertage ab heute (Europe/Sarajevo) und liefert eine Liste von
    {"title", "beschreibung", "bild", "start", "stop"}-Dicts (UTC).
    Leere Liste bei jedem Fehler oder wenn der Wochenplan leer ist."""
    if not slug:
        return []

    plan = _wochenplan_laden()
    if not plan:
        return []

    heute = datetime.now(TZ_SARAJEVO).date()

    rohe_eintraege = []
    # Ein Tag zusaetzlich, um die Endzeit der letzten Sendung des
    # angefragten Zeitraums aus dem naechsten (noch folgenden) Eintrag
    # berechnen zu koennen.
    for i in range(tage + 1):
        tag_datum = heute + timedelta(days=i)
        eintraege = plan.get(tag_datum.weekday(), [])
        for stunde, minute, titel in eintraege:
            start_lokal = datetime(
                tag_datum.year, tag_datum.month, tag_datum.day,
                stunde, minute, tzinfo=TZ_SARAJEVO,
            )
            rohe_eintraege.append({"start_lokal": start_lokal, "titel": titel})

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
        if p["start"].astimezone(TZ_SARAJEVO).date() in erlaubte_tage
        or p["stop"].astimezone(TZ_SARAJEVO).date() in erlaubte_tage
    ]
