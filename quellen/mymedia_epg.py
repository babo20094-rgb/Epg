"""Optionale, echte Programmdaten von mymedia.ba/tv-program/ fuer den
Sender "MY TV" (Metropoly Media, Bosnien).

Anders als Telemach/mtel.ba/mts.rs/MojMaxTV/tv-spored.siol.net deckt
diese Seite technisch nur EINEN einzigen, festen Kanal ab (kein
Kanal-Verzeichnis, kein Login) - es gibt daher hier bewusst keine
eigene kanal_finden()-Funktion wie bei den anderen Quellen, sondern nur
mymedia_hole_programme(). Die Zuordnung zum Sender "MY TV" passiert in
generate_epg.py als dritter Fallback nach Telemach und mtel.ba, nur
wenn der Sendername exakt "MY TV" entspricht.

Die Seite liefert pro Tag (Query-Parameter ?epg_day=YYYY-MM-DD) den
kompletten Tagesraster server-seitig gerendert als HTML - jede Sendung
steckt in einem <button class="js-tvsmepg-program-card"> mit den
Attributen data-program-title/-description/-time (Format
"HH:MM – HH:MM"). Wird mit BeautifulSoup geparst statt einer
stabilen JSON-API - dieses Modul ist deshalb prinzipbedingt
anfaelliger fuer Breaking Changes bei einem Website-Redesign als die
anderen Quellen, degradiert aber nach demselben Zero-Risk-Prinzip an
JEDER Stelle graceful auf [] statt zu werfen: schlaegt der Seitenabruf
oder das Parsen fehl, bekommt "MY TV" einfach die normale,
kategoriebasierte generische EPG-Generierung wie jeder andere Sender -
dieses Modul darf einen Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import re

import requests
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

BASE_URL = "https://mymedia.ba/tv-program/"

REQUEST_TIMEOUT_SEKUNDEN = 20

TZ = ZoneInfo("Europe/Sarajevo")

# Modul-weiter Cache pro Tag, damit ein mehrfacher Aufruf im selben
# Lauf nicht wiederholt dieselbe Seite abruft.
_seite_cache = {}


def _seite_holen(tag):
    """Holt (und cached pro Tag) die rohe HTML-Seite fuer den gegebenen
    Tag als BeautifulSoup-Objekt. Gibt bei jedem Fehler None zurueck."""
    schluessel = tag.isoformat()

    if schluessel in _seite_cache:
        return _seite_cache[schluessel]

    try:
        response = requests.get(
            BASE_URL, params={"epg_day": schluessel}, timeout=REQUEST_TIMEOUT_SEKUNDEN
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        _seite_cache[schluessel] = soup
        return soup
    except Exception as e:
        print(f"MyMedia-EPG: Seitenabruf ({schluessel}) fehlgeschlagen ({e}), ueberspringe.")
        _seite_cache[schluessel] = None
        return None


def _zeitspanne_parsen(text):
    """Parst 'HH:MM – HH:MM' (oder mit einfachem Bindestrich) zu
    (start_stunde, start_minute, stop_stunde, stop_minute). None bei
    Parse-Fehler."""
    match = re.match(r"^(\d{1,2}):(\d{2})\s*[–-]\s*(\d{1,2}):(\d{2})$", (text or "").strip())
    if not match:
        return None
    return tuple(int(x) for x in match.groups())


def _tag_programme_parsen(soup, tag):
    ergebnis = []
    for card in soup.select(".js-tvsmepg-program-card"):
        titel = (card.get("data-program-title") or "").strip()
        zeit_text = card.get("data-program-time") or ""
        beschreibung = (card.get("data-program-description") or "").strip()

        if not titel or not zeit_text:
            continue

        zeitspanne = _zeitspanne_parsen(zeit_text)
        if zeitspanne is None:
            continue

        start_h, start_m, stop_h, stop_m = zeitspanne
        start = datetime(tag.year, tag.month, tag.day, start_h, start_m, tzinfo=TZ)
        stop = datetime(tag.year, tag.month, tag.day, stop_h, stop_m, tzinfo=TZ)
        if stop <= start:
            stop += timedelta(days=1)

        ergebnis.append({
            "title": titel,
            "beschreibung": beschreibung,
            "start": start,
            "stop": stop,
        })

    return ergebnis


def mymedia_hole_programme(tage=3):
    """Holt Programmdaten fuer den Sender "MY TV" fuer `tage`
    aufeinanderfolgende Tage ab heute (Europe/Sarajevo). Liefert eine
    nach Startzeit sortierte, deduplizierte Liste von {"title",
    "beschreibung", "bild", "start", "stop"} (UTC, tz-aware) - leere
    Liste bei jedem Fehler (Netzwerk, HTTP-Status, unerwartete HTML-
    Struktur)."""
    heute = datetime.now(TZ).date()

    gesehen = set()
    roh = []
    for i in range(tage):
        tag = heute + timedelta(days=i)
        soup = _seite_holen(tag)
        if soup is None:
            continue
        try:
            for p in _tag_programme_parsen(soup, tag):
                schluessel = (p["title"], p["start"])
                if schluessel in gesehen:
                    continue
                gesehen.add(schluessel)
                roh.append(p)
        except Exception as e:
            print(f"MyMedia-EPG: Parsen fuer {tag} fehlgeschlagen ({e}), ueberspringe Tag.")
            continue

    ergebnis = []
    for p in roh:
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
