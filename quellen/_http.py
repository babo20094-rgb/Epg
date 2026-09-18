"""
_http.py - Gemeinsamer Retry-Wrapper fuer requests.get()/requests.post()-
Aufrufe in allen Quellen-Skripten (quellen/*.py).

Bisher liess ein einzelner Verbindungsabbruch/Timeout eine Quelle fuer
den kompletten Lauf komplett auf die naechste Kaskaden-Stufe (oder ganz
auf generisch) zurueckfallen, obwohl ein zweiter Versuch oft gereicht
haette - der naechste Workflow-Lauf folgt erst bis zu 4h spaeter.

mit_retry(requests.get, url, ...) ruft die uebergebene Funktion mit den
gleichen Argumenten auf wie ein direkter requests.get(url, ...)-Aufruf
und wiederholt genau einmal (mit kurzer Pause), wenn requests dabei
einen reinen Verbindungs-/Timeout-Fehler wirft (requests.exceptions.
ConnectionError/Timeout). Alle anderen Fehler (z.B. HTTPError bei
4xx, oder Fehler beim Parsen der Antwort) werden NICHT wiederholt,
da ein erneuter Versuch daran nichts aendern wuerde, und unveraendert
nach oben an den bestehenden try/except-Block der jeweiligen Quelle
weitergereicht - das Zero-Risk-Verhalten (jeder Fehler faellt still
auf die naechste Quelle zurueck) bleibt dadurch unangetastet.

Bewusst ein duenner Wrapper um requests.get/requests.post (statt einer
gemeinsamen requests.Session mit Retry-Adapter): so bleibt in jedem
Quellen-Skript weiterhin "requests.get"/"requests.post" der Aufruf, den
test_generate_epg.py per patch("quellen.<modul>.requests.get", ...)
mockt - ein Wechsel auf eine Session-Methode haette alle bestehenden
Tests unbemerkt am Mock vorbeilaufen lassen.
"""

import time

import requests

_VERSUCHE = 2
_PAUSE_SEKUNDEN = 1.5


def mit_retry(fn, *args, **kwargs):
    """Ruft fn(*args, **kwargs) auf (z.B. requests.get) und wiederholt
    bei requests.exceptions.ConnectionError/Timeout bis zu _VERSUCHE
    mal insgesamt. Andere Exceptions (inkl. HTTPError) werden sofort
    weitergereicht."""
    letzter_fehler = None
    for versuch in range(1, _VERSUCHE + 1):
        try:
            return fn(*args, **kwargs)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            letzter_fehler = e
            if versuch < _VERSUCHE:
                time.sleep(_PAUSE_SEKUNDEN)
    raise letzter_fehler
