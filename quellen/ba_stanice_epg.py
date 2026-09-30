"""Echte Programmdaten von einzelnen, eigenstaendigen Webseiten
bosnischer Regionalsender - AUTOMATISCH fuer die passende sender.txt-
Zeile, als Fallback fuer Sender, die bei KEINER der grossen Kaskaden-
Quellen (Telemach/mtel.ba/klix.ba/TvProfil.net/tvprogramdanas.net/
open-epg.com) etwas liefern.

Jede Seite in dieser engen Whitelist wurde EINZELN manuell geprueft
(erreichbar, echte Daten, mit Datumsabdeckung, die auch die naechsten
Tage einschliesst - nicht nur die Vergangenheit, siehe z.B. der
verworfene rtvbpk.ba-Fall, dessen Seite beim Test eine volle Woche
veraltet war). NICHT einfach um weitere Domains erweitern, ohne das
genauso zu verifizieren.

Zwei unterschiedliche Quellen-Typen, je nach Sender:
- "xmltv": Standard-XMLTV-Datei mit expliziten start/stop-Attributen
  (z.B. RTV Vogosca, https://rtvvogosca.ba/pregledprograma/
  rtvvogosca.xml) - ein einzelner Abruf liefert bereits alle Tage.
- "html_daily": eigene HTML-Seite mit Tages-Navigation ueber einen
  "?date=YYYY-MM-DD"-URL-Parameter (z.B. RTVTK,
  https://rtvtk.ba/tv_cms/public_epg.php/) - ein Abruf PRO Tag noetig,
  Zeiten sind lokale Zeit ohne Zeitzonen-Angabe (Europe/Sarajevo
  angenommen, wie bei allen anderen BA-Quellen im Projekt).

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen - dieses Modul darf einen
Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import re
import xml.etree.ElementTree as ET

import requests
from quellen import _http

from epg_lib import normalisiere_sendername

REQUEST_TIMEOUT_SEKUNDEN = 20

SARAJEVO_TZ = ZoneInfo("Europe/Sarajevo")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# ENGE Whitelist: normalisierter Sendername -> {"typ": ..., "url"/
# "url_muster": ...}. Nur einzeln verifizierte Sender aufnehmen (siehe
# Modul-Docstring).
_WHITELIST = {
    normalisiere_sendername("RTV Vogosca"): {
        "typ": "xmltv",
        "url": "https://rtvvogosca.ba/pregledprograma/rtvvogosca.xml",
    },
    # "TK" (eigene sender.txt-Kurzform fuer RTVTK/RTV Tuzlanski Kanton -
    # NICHT identisch mit "RTV TK", das bereits ueber Telemach laeuft)
    # - {datum} wird durch YYYY-MM-DD ersetzt.
    normalisiere_sendername("TK"): {
        "typ": "html_daily",
        "url_muster": "https://rtvtk.ba/tv_cms/public_epg.php/?date={datum}",
    },
}

_datei_cache = {}
_html_tag_cache = {}


def ba_stanice_kanal_finden(kanalname):
    """Nur ein exakter Abgleich gegen die enge Whitelist oben - gibt bei
    Treffer den Whitelist-Eintrag (dict) zurueck, sonst None."""
    schluessel = normalisiere_sendername(kanalname)
    if not schluessel:
        return None
    return _WHITELIST.get(schluessel)


def _xmltv_zeit_parsen(text):
    match = re.match(r"^(\d{14})\s*([+-]\d{4})$", (text or "").strip())
    if not match:
        return None
    zeitpunkt = datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
    vorzeichen = 1 if match.group(2)[0] == "+" else -1
    versatz_minuten = vorzeichen * (int(match.group(2)[1:3]) * 60 + int(match.group(2)[3:5]))
    return zeitpunkt.replace(tzinfo=timezone.utc) - timedelta(minutes=versatz_minuten)


def _datei_holen(url):
    """Laedt (und cached) die komplette XMLTV-Datei als ElementTree-
    Wurzel. None bei jedem Fehler."""
    if url in _datei_cache:
        return _datei_cache[url]

    try:
        response = _http.mit_retry(requests.get, url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        wurzel = ET.fromstring(response.content)
        _datei_cache[url] = wurzel
        return wurzel
    except Exception as e:
        print(f"BA-Stanice-EPG: Abruf ({url}) fehlgeschlagen ({type(e).__name__}), ueberspringe.")
        _datei_cache[url] = None
        return None


def _xmltv_programme_holen(url, tage):
    wurzel = _datei_holen(url)
    if wurzel is None:
        return []

    grenze = datetime.now(timezone.utc) + timedelta(days=tage)

    ergebnis = []
    try:
        for programme in wurzel.findall("programme"):
            start = _xmltv_zeit_parsen(programme.get("start", ""))
            stop = _xmltv_zeit_parsen(programme.get("stop", ""))
            if start is None or stop is None or stop <= start:
                continue
            if start > grenze:
                continue
            titel_el = programme.find("title")
            desc_el = programme.find("desc")
            titel = titel_el.text.strip() if titel_el is not None and titel_el.text else ""
            if not titel:
                continue
            ergebnis.append({
                "title": titel,
                "beschreibung": desc_el.text.strip() if desc_el is not None and desc_el.text else "",
                "bild": None,
                "start": start,
                "stop": stop,
            })
    except Exception as e:
        print(f"BA-Stanice-EPG: XMLTV-Parsen ({url}) fehlgeschlagen ({type(e).__name__}), ueberspringe.")
        return []

    return ergebnis


_HTML_TAG_MUSTER = re.compile(
    r'<span class="start">([0-9:]+)</span>\s*<span class="end">([0-9:]+)</span>.*?'
    r'<div class="schedule-title">\s*([^<]+?)\s*</div>',
    re.S,
)


def _html_tag_holen(url_muster, tag):
    """Holt (und cached pro URL/Tag) die HTML-Seite fuer einen
    einzelnen Tag. Gibt den rohen HTML-Text zurueck, None bei Fehler."""
    url = url_muster.format(datum=tag.isoformat())
    schluessel = url

    if schluessel in _html_tag_cache:
        return _html_tag_cache[schluessel]

    try:
        response = _http.mit_retry(requests.get, url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        _html_tag_cache[schluessel] = response.text
        return response.text
    except Exception as e:
        print(f"BA-Stanice-EPG: Abruf ({url}) fehlgeschlagen ({type(e).__name__}), ueberspringe.")
        _html_tag_cache[schluessel] = None
        return None


def _html_daily_programme_holen(url_muster, tage):
    heute = datetime.now(SARAJEVO_TZ).date()

    ergebnis = []
    for i in range(tage):
        tag = heute + timedelta(days=i)
        text = _html_tag_holen(url_muster, tag)
        if not text:
            continue
        try:
            for start_text, end_text, titel in _HTML_TAG_MUSTER.findall(text):
                titel = titel.strip()
                if not titel:
                    continue
                start_h, start_m = (int(x) for x in start_text.split(":"))
                end_h, end_m = (int(x) for x in end_text.split(":"))
                start = datetime(tag.year, tag.month, tag.day, start_h, start_m, tzinfo=SARAJEVO_TZ)
                stop_tag = tag if (end_h, end_m) > (start_h, start_m) else tag + timedelta(days=1)
                stop = datetime(stop_tag.year, stop_tag.month, stop_tag.day, end_h, end_m, tzinfo=SARAJEVO_TZ)
                if stop <= start:
                    continue
                ergebnis.append({
                    "title": titel,
                    "beschreibung": "",
                    "bild": None,
                    "start": start.astimezone(timezone.utc),
                    "stop": stop.astimezone(timezone.utc),
                })
        except Exception as e:
            print(f"BA-Stanice-EPG: HTML-Parsen fuer Tag {tag} fehlgeschlagen ({type(e).__name__}), ueberspringe Tag.")
            continue

    return ergebnis


def ba_stanice_hole_programme(eintrag, tage=3):
    """Holt Programmdaten fuer den gegebenen Whitelist-Eintrag (dict aus
    ba_stanice_kanal_finden()), je nach "typ" ueber XMLTV oder taeglich
    per HTML-Seite. Liefert eine nach Startzeit sortierte Liste von
    {"title", "beschreibung", "bild", "start", "stop"} (UTC, tz-aware) -
    leere Liste bei jedem Fehler."""
    if not eintrag:
        return []

    typ = eintrag.get("typ")
    if typ == "xmltv":
        ergebnis = _xmltv_programme_holen(eintrag["url"], tage)
    elif typ == "html_daily":
        ergebnis = _html_daily_programme_holen(eintrag["url_muster"], tage)
    else:
        return []

    ergebnis.sort(key=lambda s: s["start"])
    return ergebnis
