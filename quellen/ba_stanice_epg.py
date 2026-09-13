"""Echte Programmdaten von einzelnen, eigenstaendigen Webseiten
bosnischer Regionalsender, die selbst eine kleine XMLTV-Datei anbieten
(Stand September 2026: RTV Vogosca, https://rtvvogosca.ba/
pregledprograma/rtvvogosca.xml) - AUTOMATISCH fuer die passende
sender.txt-Zeile, als Fallback fuer Sender, die bei KEINER der grossen
Kaskaden-Quellen (Telemach/mtel.ba/klix.ba/TvProfil.net/
tvprogramdanas.net/open-epg.com) etwas liefern.

Jede Seite in dieser engen Whitelist wurde EINZELN manuell geprueft
(erreichbar, echtes XMLTV, mit Datumsabdeckung, die auch die naechsten
Tage einschliesst - nicht nur die Vergangenheit, siehe z.B. der
verworfene rtvbpk.ba-Fall, dessen Seite beim Test eine volle Woche
veraltet war). NICHT einfach um weitere Domains erweitern, ohne das
genauso zu verifizieren.

Format ist bereits Standard-XMLTV mit expliziten start/stop-Attributen
(anders als z.B. klix.ba, das nur eine Startzeit liefert) - entsprechend
einfacher Parser ueber ElementTree, kein Endzeit-Berechnen noetig.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen - dieses Modul darf einen
Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import re
import xml.etree.ElementTree as ET

import requests

from epg_lib import normalisiere_sendername

REQUEST_TIMEOUT_SEKUNDEN = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# ENGE Whitelist: normalisierter Sendername -> volle XMLTV-URL. Nur
# einzeln verifizierte Sender aufnehmen (siehe Modul-Docstring).
_WHITELIST = {
    normalisiere_sendername("RTV Vogosca"): "https://rtvvogosca.ba/pregledprograma/rtvvogosca.xml",
}

_datei_cache = {}


def ba_stanice_kanal_finden(kanalname):
    """Nur ein exakter Abgleich gegen die enge Whitelist oben - gibt bei
    Treffer die volle XMLTV-URL zurueck, sonst None."""
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
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        wurzel = ET.fromstring(response.content)
        _datei_cache[url] = wurzel
        return wurzel
    except Exception as e:
        print(f"BA-Stanice-EPG: Abruf ({url}) fehlgeschlagen ({type(e).__name__}), ueberspringe.")
        _datei_cache[url] = None
        return None


def ba_stanice_hole_programme(url, tage=3):
    """Holt Programmdaten aus der gegebenen XMLTV-Datei (url),
    beschraenkt auf die naechsten `tage` Tage ab heute (UTC). Liefert
    eine nach Startzeit sortierte Liste von {"title", "beschreibung",
    "bild", "start", "stop"} - leere Liste bei jedem Fehler."""
    if not url:
        return []

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
        print(f"BA-Stanice-EPG: Parsen ({url}) fehlgeschlagen ({type(e).__name__}), ueberspringe.")
        return []

    ergebnis.sort(key=lambda s: s["start"])
    return ergebnis
