"""Echte Programmdaten fuer MY TV (Metropoly Media, Sarajevo) von
mymedia.ba/tv-program/ - AUTOMATISCH fuer jeden Sender, dessen Name
"MY TV" ODER "MY TV BHT" entspricht (beide Schreibweisen sind in
sender.txt vertreten - dieselbe reale Station, nur unterschiedlicher
Playlist-Name; mit oder ohne HD/VIP/RAW-Zusaetze). Kein eigenes
Praefix noetig.

War von September 2026 bis zu einer erneuten Pruefung dauerhaft aus
generate_epg.py entfernt (siehe docs/HISTORIE.md, "Samsung TV Plus und
mymedia.ba dauerhaft entfernt") - die Seite lief damals auf einem neuen
Plugin ("neoepg") und zeigte fuer "MY TV" an mehreren Tagen nur einen
"Keine Sendungen"-Leerzustand. Erneut live geprueft: die Seite laeuft
inzwischen auf einem WEITEREN neuen Plugin ("tvschedule-epg") und
liefert jetzt echte, gut gefuellte Tagesplaene mit Start-UND-Endzeit
direkt als HTML-data-Attribute (`data-program-title`,
`data-program-description`, `data-program-time="HH:MM – HH:MM"`) - kein
Endzeit-Schaetzen aus der naechsten Sendung noetig wie bei den meisten
anderen Quellen.

Echte Kalenderdaten (URL-Parameter `?epg_day=YYYY-MM-DD`), keine
wiederkehrende Wochenvorlage wie bei vikom_epg.py/blagovesti_epg.py -
jeder Tag wird einzeln abgerufen und gecacht. Sendungen mit dem Titel
"Kraj" ("Ende") sind ein reiner Sendeschluss-/Fuellplatzhalter (laeuft
typischerweise von kurz vor Mitternacht bis zum naechsten Sendestart am
Morgen) und werden uebersprungen, analog zu den Werbeblock-Filtern in
vikom_epg.py.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt Download oder
Parsen fehl, bekommt der betroffene Sender in generate_epg.py einfach
die normale, kategoriebasierte generische EPG-Generierung wie jeder
andere Sender - dieses Modul darf einen Lauf niemals zum Absturz
bringen.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import html
import re

import requests

from epg_lib import normalisiere_sendername

URL_VORLAGE = "https://mymedia.ba/tv-program/?epg_day={datum}"

REQUEST_TIMEOUT_SEKUNDEN = 20

SARAJEVO_TZ = ZoneInfo("Europe/Sarajevo")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# Enge Whitelist: normalisierter Sendername -> Treffer. Es gibt bei
# mymedia.ba nur diesen einen Kanal, daher reicht ein reiner
# Namensvergleich (kein Kanalverzeichnis noetig).
_WHITELIST = {normalisiere_sendername("My Tv"), normalisiere_sendername("My Tv Bht")}

# Grenzt den Daten-Ausschnitt auf die eigentliche Tagesliste ein (nicht
# die separate "coming"-Vorschau weiter oben auf derselben Seite, die
# dieselben Sendungen ein zweites Mal als data-Attribute enthaelt).
_SCHEDULE_START_MARKER = "tvschedule-epg__cp-schedule"
_SCHEDULE_END_MARKER = "tvschedule-epg__cp-weekbar"

_EINTRAG_RE = re.compile(
    r'data-program-title="([^"]*)" data-program-description="([^"]*)".*?'
    r'data-program-time="([^"]*)"',
    re.DOTALL,
)

_ZEIT_RE = re.compile(r"^(\d{1,2}):(\d{2})\s*[–-]\s*(\d{1,2}):(\d{2})$")

_tag_cache = {}


def mymedia_kanal_treffer(sendername):
    """Nur ein exakter Abgleich gegen die enge Whitelist oben (True/
    False) - kein Netzwerk-Request, reiner Namensvergleich."""
    schluessel = normalisiere_sendername(sendername)
    return bool(schluessel) and schluessel in _WHITELIST


def _text_bereinigen(text):
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def _tag_holen(tag):
    """Holt (und cached) die rohe Sendungsliste fuer einen Kalendertag
    als Liste von {"title", "beschreibung", "start_std", "start_min",
    "stop_std", "stop_min"}. None bei jedem Fehler."""
    schluessel = tag.isoformat()
    if schluessel in _tag_cache:
        return _tag_cache[schluessel]

    try:
        response = requests.get(
            URL_VORLAGE.format(datum=schluessel), headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        text = response.text

        start_idx = text.find(_SCHEDULE_START_MARKER)
        end_idx = text.find(_SCHEDULE_END_MARKER, start_idx) if start_idx != -1 else -1
        if start_idx == -1:
            _tag_cache[schluessel] = []
            return []
        abschnitt = text[start_idx:end_idx] if end_idx != -1 else text[start_idx:]

        eintraege = []
        for titel_html, opis_html, zeit_text in _EINTRAG_RE.findall(abschnitt):
            titel = _text_bereinigen(titel_html)
            if not titel or titel.lower() == "kraj":
                continue
            zeit_match = _ZEIT_RE.match((zeit_text or "").strip())
            if not zeit_match:
                continue
            start_std, start_min, stop_std, stop_min = (int(x) for x in zeit_match.groups())
            eintraege.append({
                "title": titel,
                "beschreibung": _text_bereinigen(opis_html),
                "start_std": start_std, "start_min": start_min,
                "stop_std": stop_std, "stop_min": stop_min,
            })

        _tag_cache[schluessel] = eintraege
        return eintraege
    except Exception as e:
        print(f"Mymedia-EPG: Abruf ({schluessel}) fehlgeschlagen ({e}), ueberspringe.")
        _tag_cache[schluessel] = None
        return None


def mymedia_hole_programme(tage=3):
    """Holt Programmdaten fuer MY TV fuer `tage` aufeinanderfolgende
    Tage ab heute (Europe/Sarajevo). Liefert eine nach Startzeit
    sortierte Liste von {"title", "beschreibung", "bild", "start",
    "stop"} (tz-aware) - leere Liste bei jedem Fehler."""
    heute = datetime.now(SARAJEVO_TZ).date()

    ergebnis = []
    for i in range(tage):
        tag = heute + timedelta(days=i)
        eintraege = _tag_holen(tag)
        if not eintraege:
            continue

        for eintrag in eintraege:
            start = datetime(
                tag.year, tag.month, tag.day,
                eintrag["start_std"], eintrag["start_min"], tzinfo=SARAJEVO_TZ,
            )
            stop = datetime(
                tag.year, tag.month, tag.day,
                eintrag["stop_std"], eintrag["stop_min"], tzinfo=SARAJEVO_TZ,
            )
            if stop <= start:
                stop += timedelta(days=1)
            ergebnis.append({
                "title": eintrag["title"],
                "beschreibung": eintrag["beschreibung"],
                "bild": None,
                "start": start,
                "stop": stop,
            })

    ergebnis.sort(key=lambda s: s["start"])
    return ergebnis
