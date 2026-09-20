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

import threading
import time
from urllib.parse import urlparse

import requests

_VERSUCHE = 3
_PAUSE_SEKUNDEN = 1.5
_RATE_LIMIT_STATUS = (429, 503)

# Begrenzt GLEICHZEITIGE Requests pro Host (unabhaengig davon, wie viele
# Worker-Threads der aufrufenden Quelle insgesamt parallel laufen) -
# hoerzu.de/tvmovie.de reagieren bei zu vielen gleichzeitigen Anfragen
# mit einer 429/503-Flut (September 2026, siehe docs/HISTORIE.md:
# DE-Kaskade lief in Run #874 dadurch 463s statt der ueblichen ~150s,
# weil jeder Rate-Limit-Treffer einen eigenen Retry-Backoff ausloest).
# Ein Semaphore pro Host statt eines globalen Workerzahl-Downgrades,
# damit NUR die tatsaechlich betroffenen Hosts gedrosselt werden, ohne
# die restliche DE-Kaskade (deswird/PlutoTV/Joyn-VOD/...) zu verlangsamen.
_MAX_GLEICHZEITIG_PRO_HOST = 3
_HOST_SEMAPHOREN = {}
_HOST_SEMAPHOREN_LOCK = threading.Lock()


def _semaphore_fuer_host(host):
    with _HOST_SEMAPHOREN_LOCK:
        semaphore = _HOST_SEMAPHOREN.get(host)
        if semaphore is None:
            semaphore = threading.Semaphore(_MAX_GLEICHZEITIG_PRO_HOST)
            _HOST_SEMAPHOREN[host] = semaphore
        return semaphore

# Zaehlt pro Host (z.B. "www.hoerzu.de"), wie oft ein Abruf insgesamt
# versucht wurde, wie oft dabei ein 429/503 (Rate-Limiting) auftrat und
# wie oft ein Abruf trotz aller Versuche endgueltig fehlgeschlagen ist -
# ausgegeben als kurze Zusammenfassung am Laufende (siehe
# fehler_uebersicht()/generate_epg.py), damit Faelle wie die 429-Flut bei
# hoerzu.de/tvmovie.de (September 2026, siehe docs/HISTORIE.md) direkt
# sichtbar sind, statt sie erst im kompletten Rohlog suchen zu muessen.
_STATISTIK = {}


def _host_aus_url(args):
    if not args:
        return "unbekannt"
    try:
        host = urlparse(args[0]).netloc
        return host or "unbekannt"
    except Exception:
        return "unbekannt"


def _statistik_eintrag(host):
    return _STATISTIK.setdefault(host, {"versuche": 0, "rate_limit": 0, "fehlgeschlagen": 0})


def fehler_uebersicht():
    """Gibt die gesammelte Statistik als Liste von (host, versuche,
    rate_limit_treffer, endgueltig_fehlgeschlagen) zurueck, absteigend
    nach rate_limit_treffer sortiert - nur Hosts mit mindestens einem
    429/503 oder einem endgueltigen Fehlschlag."""
    ergebnis = [
        (host, s["versuche"], s["rate_limit"], s["fehlgeschlagen"])
        for host, s in _STATISTIK.items()
        if s["rate_limit"] or s["fehlgeschlagen"]
    ]
    ergebnis.sort(key=lambda e: (e[2], e[3]), reverse=True)
    return ergebnis


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
    host = _host_aus_url(args)
    eintrag = _statistik_eintrag(host)
    semaphore = _semaphore_fuer_host(host)

    letzter_fehler = None
    for versuch in range(1, _VERSUCHE + 1):
        eintrag["versuche"] += 1
        with semaphore:
            try:
                response = fn(*args, **kwargs)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                letzter_fehler = e
                response = None

        if response is None:
            if versuch < _VERSUCHE:
                time.sleep(_PAUSE_SEKUNDEN)
            continue

        if response.status_code in _RATE_LIMIT_STATUS:
            eintrag["rate_limit"] += 1
            letzter_fehler = requests.exceptions.HTTPError(
                f"{response.status_code} Client/Server Error (Rate-Limiting)",
                response=response,
            )
            if versuch < _VERSUCHE:
                time.sleep(_rate_limit_pause(response, versuch))
                continue
            eintrag["fehlgeschlagen"] += 1
            return response

        return response

    eintrag["fehlgeschlagen"] += 1
    raise letzter_fehler
