"""Optionale, echte Programmdaten von vikom.tv (Vikom Radio Televizija,
Banja Luka) - eine einzelne, feste HTML-Seite pro Wochentag
(`https://vikom.tv/program.php?media=tv&dan=<0-6>`), keine JSON-API und
kein Login noetig.

Anders als die anderen BA-Quellen (Telemach/mtel.ba/klix.ba) gibt es hier
nur EINEN Sender (Vikom TV selbst), keine Kanalsuche noetig. Die Seite
zeigt ausserdem keine echten Kalenderdaten, sondern einen fest
wiederkehrenden WOCHENPLAN pro Wochentag (Reiter "Srijeda"/"Četvrtak"/...)
- pro Wochentag wird daher nur EINMAL pro Lauf abgerufen und gecached
(7 Requests insgesamt reichen fuer beliebig viele Tage im Voraus, das
Wochenschema wiederholt sich einfach).

Sendungen ohne feste Uhrzeit (Platzhalter "*****" fuer Musik/Telešop-
Fuellprogramm) sowie reine Werbeblöcke ("MARKETING n", "TELEŠOP") werden
uebersprungen, da sie keine sinnvolle EPG-Information liefern
(Datenmuell, siehe docs/HISTORIE.md-Regel dazu). Die Endzeit einer
Sendung wird aus dem Start der naechsten Sendung berechnet, die letzte
Sendung des Tages endet um Mitternacht - analog zu klix_epg.py/
mymedia_epg.py.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt der Abruf fehl,
bekommt der betroffene Sender in generate_epg.py einfach die normale,
kategoriebasierte generische EPG-Generierung wie jeder andere Sender -
dieses Modul darf einen Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import html
import re

import requests
from quellen import _http

from epg_lib import normalisiere_sendername

# Enge, feste Whitelist statt Kanalsuche: vikom.tv ist eine einzelne
# Senderseite (kein Kanalverzeichnis), es gibt also nur diesen einen
# Treffer. normalisiere_sendername() entfernt Unicode-Suffixe wie
# " ⱽᴵᴾ ᴿᴬᵂ" bereits selbst, "VIKOM TV" und "VIKOM TV ⱽᴵᴾ ᴿᴬᵂ" landen
# daher beide auf demselben Schluessel und bekommen so automatisch
# dasselbe echte Programm.
_WHITELIST = {normalisiere_sendername("Vikom Tv")}

URL_VORLAGE = "https://vikom.tv/program.php?media=tv&dan={dan}"

REQUEST_TIMEOUT_SEKUNDEN = 20

BANJALUKA_TZ = ZoneInfo("Europe/Sarajevo")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_EINTRAG_RE = re.compile(
    r'<span class="vreme">([^<]*)</span>.*?'
    r'<span class="naziv">([^<]*)</span>\s*'
    r'<span class="opis">(.*?)</span>',
    re.DOTALL,
)

_FUELLPROGRAMM_RE = re.compile(r"(?i)marketing|tele[sš]op|^muzika\s*(&|und)?\s*marketing$")

# Modul-weiter Cache: pro Wochentag (0=Sonntag..6=Samstag, wie im
# vikom.tv-URL-Parameter "dan") wird die Seite nur einmal pro Lauf
# geholt, das Wochenschema wiederholt sich fuer beliebig viele Tage.
_wochentag_cache = {}


def vikom_kanal_treffer(sendername):
    """Nur ein exakter Abgleich gegen die enge Whitelist oben (True/
    False) - kein Netzwerk-Request, reiner Namensvergleich."""
    schluessel = normalisiere_sendername(sendername)
    return bool(schluessel) and schluessel in _WHITELIST


def _python_wochentag_zu_dan(python_wochentag):
    """Rechnet Pythons date.weekday() (Montag=0..Sonntag=6) in den
    vikom.tv-URL-Parameter "dan" um (Sonntag=0..Samstag=6)."""
    return (python_wochentag + 1) % 7


def _zeit_parsen(text):
    match = re.match(r"^(\d{1,2})[.:](\d{2})$", (text or "").strip())
    if not match:
        return None
    stunde, minute = int(match.group(1)), int(match.group(2))
    if stunde > 23 or minute > 59:
        return None
    return stunde, minute


def _text_bereinigen(text):
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def _dan_holen(dan):
    """Holt (und cached) die rohe Liste von {"stunde", "minute", "title",
    "beschreibung"} fuer den gegebenen Wochentag-Parameter (0-6).
    None bei jedem Fehler (Netzwerk, HTTP-Status)."""
    if dan in _wochentag_cache:
        return _wochentag_cache[dan]

    try:
        response = _http.mit_retry(requests.get, 
            URL_VORLAGE.format(dan=dan), headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()

        eintraege = []
        for zeit_text, titel_text, opis_text in _EINTRAG_RE.findall(response.text):
            zeit = _zeit_parsen(zeit_text)
            titel = _text_bereinigen(titel_text)
            if zeit is None or not titel:
                continue
            if _FUELLPROGRAMM_RE.search(titel):
                continue
            stunde, minute = zeit
            eintraege.append({
                "stunde": stunde,
                "minute": minute,
                "title": titel,
                "beschreibung": _text_bereinigen(opis_text),
            })

        _wochentag_cache[dan] = eintraege
        return eintraege
    except Exception as e:
        print(f"Vikom-EPG: Abruf (dan={dan}) fehlgeschlagen ({e}), ueberspringe.")
        _wochentag_cache[dan] = None
        return None


def vikom_hole_programme(tage=7):
    """Holt Programmdaten fuer Vikom TV fuer `tage` aufeinanderfolgende
    Tage ab heute (Europe/Sarajevo) - das wiederkehrende Wochenschema wird
    dabei auf die tatsaechlichen Kalendertage gemappt. Liefert eine nach
    Startzeit sortierte Liste von {"title", "beschreibung", "bild",
    "start", "stop"} (tz-aware) - leere Liste bei jedem Fehler."""
    heute = datetime.now(BANJALUKA_TZ).date()

    alle = []
    for i in range(tage):
        tag = heute + timedelta(days=i)
        dan = _python_wochentag_zu_dan(tag.weekday())
        eintraege = _dan_holen(dan)
        if not eintraege:
            continue

        for eintrag in eintraege:
            start = datetime(
                tag.year, tag.month, tag.day,
                eintrag["stunde"], eintrag["minute"], tzinfo=BANJALUKA_TZ,
            )
            alle.append({
                "title": eintrag["title"],
                "beschreibung": eintrag["beschreibung"],
                "start": start,
            })

    alle.sort(key=lambda s: s["start"])

    ergebnis = []
    for index, sendung in enumerate(alle):
        if index + 1 < len(alle):
            stop = alle[index + 1]["start"]
        else:
            tag_start = sendung["start"].replace(hour=0, minute=0, second=0, microsecond=0)
            stop = tag_start + timedelta(days=1)
        if stop <= sendung["start"]:
            continue
        ergebnis.append({
            "title": sendung["title"],
            "beschreibung": sendung["beschreibung"],
            "bild": None,
            "start": sendung["start"],
            "stop": stop,
        })

    return ergebnis
