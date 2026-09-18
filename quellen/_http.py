"""
_http.py - Gemeinsamer Retry-Wrapper fuer requests.get()/requests.post()-
Aufrufe in allen Quellen-Skripten (quellen/*.py).

Bisher liess ein einzelner Verbindungsabbruch/Timeout eine Quelle fuer
den kompletten Lauf komplett auf die naechste Kaskaden-Stufe (oder ganz
auf generisch) zurueckfallen, obwohl ein zweiter Versuch oft gereicht
haette - der naechste Workflow-Lauf folgt erst bis zu 4h spaeter.

mit_retry(requests.get, url, ...) ruft die uebergebene Funktion mit den
gleichen Argumenten auf wie ein direkter requests.get(url, ...)-Aufruf
und wiederholt bei einem reinen Verbindungs-/Timeout-Fehler
(requests.exceptions.ConnectionError/Timeout) sowie bei HTTP 429/503
(Too Many Requests/Service Unavailable - typisches serverseitiges
Rate-Limiting bei mehreren parallelen Workern, siehe HISTORIE.md
September 2026) mit steigender Pause (Retry-After-Header wird dabei
respektiert, falls die Antwort einen liefert). Alle anderen Fehler
(z.B. HTTPError bei 404, oder Fehler beim Parsen der Antwort) werden
NICHT wiederholt, da ein erneuter Versuch daran nichts aendern wuerde,
und unveraendert nach oben an den bestehenden try/except-Block der
jeweiligen Quelle weitergereicht - das Zero-Risk-Verhalten (jeder
Fehler faellt still auf die naechste Quelle zurueck) bleibt dadurch
unangetastet.

Bewusst ein duenner Wrapper um requests.get/requests.post (statt einer
gemeinsamen requests.Session mit Retry-Adapter): so bleibt in jedem
Quellen-Skript weiterhin "requests.get"/"requests.post" der Aufruf, den
test_generate_epg.py per patch("quellen.<modul>.requests.get", ...)
mockt - ein Wechsel auf eine Session-Methode haette alle bestehenden
Tests unbemerkt am Mock vorbeilaufen lassen.
"""

import time

import requests

_VERSUCHE = 3
_PAUSE_SEKUNDEN = 1.5
_RATE_LIMIT_STATUS = (429, 503)


def _rate_limit_pause(response, versuch):
    """Bestimmt die Wartezeit vor dem naechsten Versuch nach einem
    429/503: nutzt den Retry-After-Header (Sekunden), falls vorhanden
    und plausibel, sonst einen mit jedem Versuch steigenden Backoff."""
    retry_after = response.headers.get("Retry-After") if response is not None else None
    if retry_after:
        try:
            sekunden = float(retry_after)
            if 0 < sekunden <= 30:
                return sekunden
        except ValueError:
            pass
    return _PAUSE_SEKUNDEN * versuch


def mit_retry(fn, *args, **kwargs):
    """Ruft fn(*args, **kwargs) auf (z.B. requests.get) und wiederholt
    bis zu _VERSUCHE mal insgesamt bei requests.exceptions.
    ConnectionError/Timeout sowie bei HTTP 429/503 (Rate-Limiting).
    Andere Fehler (inkl. HTTPError bei anderen Status-Codes) werden
    sofort weitergereicht."""
    letzter_fehler = None
    for versuch in range(1, _VERSUCHE + 1):
        try:
            response = fn(*args, **kwargs)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            letzter_fehler = e
            if versuch < _VERSUCHE:
                time.sleep(_PAUSE_SEKUNDEN)
            continue

        if response.status_code in _RATE_LIMIT_STATUS:
            letzter_fehler = requests.exceptions.HTTPError(
                f"{response.status_code} Client/Server Error (Rate-Limiting)",
                response=response,
            )
            if versuch < _VERSUCHE:
                time.sleep(_rate_limit_pause(response, versuch))
                continue
            return response

        return response
    raise letzter_fehler
