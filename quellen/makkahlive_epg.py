"""Echte "Programmdaten" fuer BA|MEKA TV (24/7-Dauerstream aus Mekka)
von makkahlive.net - kein klassisches TV-EPG mit Sendungstiteln,
sondern ein Pseudo-Sendeplan aus den echten taeglichen Gebetszeiten
(Fajr/Dhuhr/Asr/Maghrib/Isha), die den Ablauf des Streams tatsaechlich
bestimmen (Live-Uebertragung des Gebets zur jeweiligen Zeit, dazwischen
durchgehende Live-Uebertragung/Rezitation aus der Moschee).

Die komplette Jahres-Tabelle (365 Tage, Umm-al-Qura-Methode, Zeiten fuer
Mekka) steckt bereits fertig als JSON im Next.js-RSC-Seiten-Payload von
`https://makkahlive.net/en/prayer-times/saudi-arabia/makkah` - kein
separates API-Endpoint noetig, nur ein Regex-Extract aus dem HTML
(Nutzer-Screenshot vom 19.09.2026 bestaetigt: Seite zeigt tatsaechlich
mehrere Tage/Monate voraus, nicht nur "heute"). Wird EINMAL pro Lauf
geladen und geparst (gecached).

Blockbildung: zu jeder der fuenf Gebetszeiten (Sunrise zaehlt nicht als
Gebet) ein kurzer "<Name> namaz"-Block fester Laenge (NAMAZ_DAUER,
Schaetzwert - die echte Sendedauer der Live-Gebetsuebertragung ist
nicht exakt bekannt), dazwischen durchgehend "Uživo prijenos iz
Harama" (Fuellblock, keine Luecken). Zeiten sind in Asia/Riyadh
(Saudi-Arabien, ganzjaehrig UTC+3, keine Sommerzeit).

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf []/leere Ergebnisse statt zu werfen - dieses Modul darf einen Lauf
niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import re

import requests
from quellen import _http

URL = "https://makkahlive.net/en/prayer-times/saudi-arabia/makkah"

REQUEST_TIMEOUT_SEKUNDEN = 20

RIYADH_TZ = ZoneInfo("Asia/Riyadh")

NAMAZ_DAUER = timedelta(minutes=20)

FUELL_TITEL = "Uživo prijenos iz Harama"

_NAMEN = {
    "fajr": "Sabah namaz",
    "dhuhr": "Podne namaz",
    "asr": "Ikindija namaz",
    "maghrib": "Akšam namaz",
    "isha": "Jacija namaz",
}

# Extrahiert direkt aus dem escapten JSON-String im Next.js-RSC-Payload
# der Seite (siehe Modul-Docstring) - "sunrise" wird bewusst NICHT
# mitgeparst (kein eigener Gebets-/Programmblock).
_TAG_MUSTER = re.compile(
    r'date\\":\\"(\d{4}-\d{2}-\d{2})\\",\\"fajr\\":\\"(\d{2}:\d{2}:\d{2})\\",'
    r'\\"sunrise\\":\\"\d{2}:\d{2}:\d{2}\\",\\"dhuhr\\":\\"(\d{2}:\d{2}:\d{2})\\",'
    r'\\"asr\\":\\"(\d{2}:\d{2}:\d{2})\\",\\"maghrib\\":\\"(\d{2}:\d{2}:\d{2})\\",'
    r'\\"isha\\":\\"(\d{2}:\d{2}:\d{2})'
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_jahresdaten_cache = None


def _jahresdaten_holen(benoetigte_daten):
    """Laedt (und cached) NUR die tatsaechlich benoetigten Tage als Dict
    "YYYY-MM-DD" -> {"fajr": time, "dhuhr": time, ...}. Die Seite selbst
    liefert zwar bei jedem Abruf die komplette Jahrestabelle (365 Tage)
    in einem Rutsch mit (kein separates Tages-Endpoint verfuegbar, siehe
    Modul-Docstring) - alle Eintraege ausserhalb von `benoetigte_daten`
    (ein Set von "YYYY-MM-DD"-Strings) werden aber sofort verworfen,
    statt unnoetig alle 365 Tage im Cache vorzuhalten. Leeres Dict bei
    jedem Fehler."""
    global _jahresdaten_cache
    if _jahresdaten_cache is not None:
        return _jahresdaten_cache

    ergebnis = {}
    try:
        response = _http.mit_retry(requests.get, URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        for datum, fajr, dhuhr, asr, maghrib, isha in _TAG_MUSTER.findall(response.text):
            if datum not in benoetigte_daten:
                continue
            ergebnis[datum] = {
                "fajr": fajr, "dhuhr": dhuhr, "asr": asr, "maghrib": maghrib, "isha": isha,
            }
    except Exception as e:
        print(f"Makkah-Live-EPG: Abruf der Gebetszeiten fehlgeschlagen ({e}), ueberspringe.")
        ergebnis = {}

    _jahresdaten_cache = ergebnis
    return ergebnis


def _tages_ereignisse(tag, daten):
    eintrag = daten.get(tag.isoformat())
    if not eintrag:
        return []
    ereignisse = []
    for schluessel, name in _NAMEN.items():
        zeit_text = eintrag.get(schluessel)
        match = re.match(r"^(\d{2}):(\d{2}):(\d{2})$", zeit_text or "")
        if not match:
            continue
        stunde, minute, _sek = (int(g) for g in match.groups())
        start = datetime(tag.year, tag.month, tag.day, stunde, minute, tzinfo=RIYADH_TZ)
        ereignisse.append((start, name))
    return ereignisse


def makkahlive_hole_programme(tage=3):
    """Baut den Pseudo-Sendeplan (Namaz-Bloecke + Fuellbloecke) fuer die
    naechsten `tage` Kalendertage ab heute (Asia/Riyadh). Liefert eine
    nach Startzeit sortierte Liste von {"title", "beschreibung", "bild",
    "start", "stop"} (UTC, tz-aware) - leere Liste bei jedem Fehler."""
    heute = datetime.now(RIYADH_TZ).date()
    benoetigte_tage = [heute + timedelta(days=offset) for offset in range(-1, tage + 1)]
    benoetigte_daten = {tag.isoformat() for tag in benoetigte_tage}

    daten = _jahresdaten_holen(benoetigte_daten)
    if not daten:
        return []

    ereignisse = []
    for tag in benoetigte_tage:
        ereignisse.extend(_tages_ereignisse(tag, daten))
    ereignisse.sort(key=lambda e: e[0])

    if len(ereignisse) < 2:
        return []

    fenster_start = datetime(heute.year, heute.month, heute.day, tzinfo=RIYADH_TZ)
    fenster_ende = fenster_start + timedelta(days=tage)

    bloecke = []
    for (start, name), (naechster_start, _) in zip(ereignisse, ereignisse[1:]):
        namaz_ende = min(start + NAMAZ_DAUER, naechster_start)
        bloecke.append({"title": name, "start": start, "stop": namaz_ende})
        if namaz_ende < naechster_start:
            bloecke.append({"title": FUELL_TITEL, "start": namaz_ende, "stop": naechster_start})

    ergebnis = []
    for block in bloecke:
        start, stop = block["start"], block["stop"]
        if stop <= fenster_start or start >= fenster_ende:
            continue
        try:
            ergebnis.append({
                "title": block["title"],
                "beschreibung": "",
                "bild": None,
                "start": start.astimezone(timezone.utc),
                "stop": stop.astimezone(timezone.utc),
            })
        except Exception:
            continue

    ergebnis.sort(key=lambda s: s["start"])
    return ergebnis
