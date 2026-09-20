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
from urllib.parse import urlparse

import requests

_VERSUCHE = 3
_PAUSE_SEKUNDEN = 1.5
_RATE_LIMIT_STATUS = (429, 503)

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
    return _STATISTIK.setdefault(host, {
        "versuche": 0, "rate_limit": 0, "fehlgeschlagen": 0,
        # Debug-Zusatz (September 2026, siehe docs/HISTORIE.md
        # "Retry-Wartezeit gedeckelt"): misst, wie viel Wartezeit die
        # Rate-Limit-Retries TATSAECHLICH gekostet haben und ob die
        # Server ueberhaupt einen Retry-After-Header schicken - ohne
        # diese Zahlen war unklar, ob der 5s-Deckel in
        # _rate_limit_pause() irgendetwas bewirkt oder wirkungslos ist
        # (die eigene Backoff-Formel kommt ohne Header sowieso nie ueber
        # 4.5s). Rein additiv, aendert nichts am Retry-Verhalten selbst.
        "wartezeit_gesamt": 0.0,
        "retry_after_header_treffer": 0,
    })


def fehler_uebersicht():
    """Gibt die gesammelte Statistik als Liste von (host, versuche,
    rate_limit_treffer, endgueltig_fehlgeschlagen, wartezeit_gesamt,
    retry_after_header_treffer) zurueck, absteigend nach
    rate_limit_treffer sortiert - nur Hosts mit mindestens einem
    429/503 oder einem endgueltigen Fehlschlag."""
    ergebnis = [
        (
            host, s["versuche"], s["rate_limit"], s["fehlgeschlagen"],
            s["wartezeit_gesamt"], s["retry_after_header_treffer"],
        )
        for host, s in _STATISTIK.items()
        if s["rate_limit"] or s["fehlgeschlagen"]
    ]
    ergebnis.sort(key=lambda e: (e[2], e[3]), reverse=True)
    return ergebnis


_RETRY_AFTER_MAX_SEKUNDEN = 5

def _rate_limit_pause(response, versuch):
    """Bestimmt die Wartezeit vor dem naechsten Versuch nach einem
    429/503: nutzt den Retry-After-Header (Sekunden), falls vorhanden
    und plausibel, sonst einen mit jedem Versuch steigenden Backoff.
    Auf _RETRY_AFTER_MAX_SEKUNDEN gedeckelt (statt bisher 30s) - ein
    Sender, der nach diesem kuerzeren Warten immer noch nicht durchkommt,
    faellt einfach graceful auf die naechste Kaskaden-Stufe zurueck
    (z.B. hoerzu.de -> Joyn-VOD), verliert dabei keine Daten, nur
    potenziell ein paar echte Sendungen von der langsameren Quelle -
    spart aber bei vielen gleichzeitigen 429ern (siehe hoerzu.de/
    tvmovie.de-Faelle in docs/HISTORIE.md) spuerbar Laufzeit.

    Gibt (wartezeit, hatte_retry_after_header) zurueck - das zweite
    Element ist reines Debug-Signal fuer fehler_uebersicht() (siehe
    dort), damit sichtbar wird, ob der Server ueberhaupt einen
    Retry-After-Header schickt (nur dann kann der Deckel ueberhaupt
    etwas bewirken - ohne Header liegt die eigene Backoff-Formel
    sowieso immer unter dem Deckel)."""
    retry_after = response.headers.get("Retry-After") if response is not None else None
    if retry_after:
        try:
            sekunden = float(retry_after)
            if 0 < sekunden <= _RETRY_AFTER_MAX_SEKUNDEN:
                return sekunden, True
            if sekunden > _RETRY_AFTER_MAX_SEKUNDEN:
                return _RETRY_AFTER_MAX_SEKUNDEN, True
        except ValueError:
            pass
    return min(_PAUSE_SEKUNDEN * versuch, _RETRY_AFTER_MAX_SEKUNDEN), False


def mit_retry(fn, *args, **kwargs):
    """Ruft fn(*args, **kwargs) auf (z.B. requests.get) und wiederholt
    bis zu _VERSUCHE mal insgesamt bei requests.exceptions.
    ConnectionError/Timeout sowie bei HTTP 429/503 (Rate-Limiting).
    Andere Fehler (inkl. HTTPError bei anderen Status-Codes) werden
    sofort weitergereicht."""
    eintrag = _statistik_eintrag(_host_aus_url(args))

    letzter_fehler = None
    for versuch in range(1, _VERSUCHE + 1):
        eintrag["versuche"] += 1
        try:
            response = fn(*args, **kwargs)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            letzter_fehler = e
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
                pause_sekunden, hatte_header = _rate_limit_pause(response, versuch)
                eintrag["wartezeit_gesamt"] += pause_sekunden
                if hatte_header:
                    eintrag["retry_after_header_treffer"] += 1
                time.sleep(pause_sekunden)
                continue
            eintrag["fehlgeschlagen"] += 1
            return response

        return response

    eintrag["fehlgeschlagen"] += 1
    raise letzter_fehler
