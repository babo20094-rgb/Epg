"""Schnelle Zeit-Parser fuer die haeufigsten Zeitformate der Quellen.

`datetime.strptime` ist bei zehntausenden Aufrufen pro Lauf spuerbar
langsam (Messung Oktober 2026: ca. 30 % der Rechenzeit des Laufs, siehe
docs/HISTORIE.md). Die Funktionen hier lesen die Zahlen direkt per
Regex ab und bauen daraus das datetime. Passt ein Text NICHT genau auf
das erwartete Muster (oder wirft die schnelle Variante), wird unveraendert
auf den urspruenglichen strptime-Aufruf zurueckgefallen - Ergebnis und
Fehlerverhalten bleiben dadurch identisch zu vorher.
"""

import re
from datetime import datetime, timezone

_XMLTV = re.compile(r"^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2}) ([+-])(\d{2})(\d{2})$")
_NAIV_SEK = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$")
_NAIV_MIN = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})$")


def xmltv_zeit_zu_utc(text):
    """'YYYYMMDDHHMMSS +ZZZZ' -> tz-aware UTC-datetime (wie
    datetime.strptime(text.strip(), "%Y%m%d%H%M%S %z").astimezone(utc))."""
    text = text.strip()
    m = _XMLTV.match(text)
    if m:
        try:
            # ISO-Form bauen und von der (in C geschriebenen) fromisoformat
            # lesen lassen - deutlich schneller als strptime.
            return datetime.fromisoformat(
                f"{text[0:4]}-{text[4:6]}-{text[6:8]}T{text[8:10]}:{text[10:12]}:{text[12:14]}"
                f"{text[15]}{text[16:18]}:{text[18:20]}"
            ).astimezone(timezone.utc)
        except Exception:
            pass
    return datetime.strptime(text, "%Y%m%d%H%M%S %z").astimezone(timezone.utc)


def naive_zeit_sekunden(text):
    """'YYYY-MM-DD HH:MM:SS' -> naives datetime (wie strptime mit
    "%Y-%m-%d %H:%M:%S")."""
    if _NAIV_SEK.match(text):
        try:
            return datetime.fromisoformat(text)
        except Exception:
            pass
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")


def naive_zeit_minuten(text):
    """'YYYY-MM-DD HH:MM' -> naives datetime (wie strptime mit
    "%Y-%m-%d %H:%M")."""
    if _NAIV_MIN.match(text):
        try:
            return datetime.fromisoformat(text)
        except Exception:
            pass
    return datetime.strptime(text, "%Y-%m-%d %H:%M")
