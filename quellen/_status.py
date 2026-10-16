"""
_status.py - Meldungen der HTML-Quellen ("Seite geladen, aber wie viele
Zeilen hat der Parser gefunden?") fuer die Quellen-Ueberwachung am
Lauf-Ende (siehe generate_epg.py / epg_lib.quellen_gesundheit_pruefen()).

Unterscheidet damit "Server nicht erreichbar" (Seite wurde nicht geladen)
von "Layout vermutlich geaendert" (Seite geladen, Parser findet 0 Zeilen) -
genau der Fall bei rtvbn.tv im Oktober 2026 (siehe docs/HISTORIE.md).

Rein passiv: speichert nur Zahlen, wirft nie und veraendert keine Daten.
"""

import threading

_lock = threading.Lock()
_meldungen = {}


def parser_meldung(quelle, geladene_zeichen, gefundene_zeilen):
    """Merkt sich fuer `quelle` die Groesse der geladenen Seite und die
    Zahl der vom Parser gefundenen Zeilen/Sendungen (letzte Meldung gilt)."""
    try:
        with _lock:
            _meldungen[quelle] = (int(geladene_zeichen), int(gefundene_zeilen))
    except Exception:
        pass


def layout_verdacht():
    """Quellen, deren Seite geladen wurde (> 500 Zeichen), der Parser aber
    0 Zeilen fand: [(quelle, geladene_zeichen), ...]."""
    with _lock:
        return [
            (q, z) for q, (z, n) in sorted(_meldungen.items())
            if z > 500 and n == 0
        ]
