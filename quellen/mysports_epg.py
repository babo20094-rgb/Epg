"""Echte Programmdaten fuer "MySports 1-9"/"MySports EDGE" (CH) direkt
von www.mysports.ch - AUTOMATISCH fuer jeden Sender, dessen Name auf
"MYSPORTS <Nummer>" oder "MYSPORTS EDGE" passt (mit oder ohne HD/4K/
VIP/RAW-Zusaetzen). Kein eigenes Praefix noetig.

Hintergrund (September 2026): Die generische DE-Kaskade (deswird.org/
tvmovie.de/hoerzu.de) kennt gar keinen echten "MySports"-Kanal - der
unscharfe difflib-Abgleich matchte "MYSPORTS" bisher faelschlich auf
den voellig anderen Sender "Sky Sport"/"eSports1" (aehnliche
Buchstabenfolge), was als "echter Treffer" durchging und dauerhaft
falsche fremde Programmdaten anzeigte. Ein erster Versuch mit der
teleboy.ch-API funktionierte lokal einwandfrei, wurde aber vom echten
GitHub-Actions-Runner aus mit 403 Forbidden geblockt (Geo-/Cloud-IP-
Sperre, per eigenem Diagnose-Workflow verifiziert) - komplett verworfen.

https://www.mysports.ch/api/epg ist der oeffentliche, unauthentifizierte
Endpunkt, den die mysports.ch-Webseite selbst fuer ihre TV-Programm-
Seite (https://www.mysports.ch/<lang>/programme) laedt. EIN einziger
GET-Request liefert sowohl die komplette Kanalliste ("channel", inkl.
Namen/Alias-Namen/IDs) als auch alle Sendungen der naechsten ~2 Wochen
("events") - kein API-Key, kein Login noetig, deutlich einfacher als
teleboy.ch. Wird pro Lauf nur EINMAL geladen und geparst (Modul-weiter
Cache fuer BEIDE Teile aus derselben Antwort).

"event_subtitle"/"event_plot" sind selbst wieder als JSON-Strings
kodiert (z.B. "{\"de\":\"Vol. 125\",...}") - werden hier zusaetzlich
geparst, mit leerem String als Fallback bei Parse-Fehlern.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt Download, Parsen
oder Kanalsuche fehl, bekommt der betroffene Sender in generate_epg.py
einfach die normale, kategoriebasierte generische EPG-Generierung wie
jeder andere Sender - dieses Modul darf einen Lauf niemals zum Absturz
bringen.
"""

from datetime import datetime, timezone
import json
import re

import requests
from quellen import _http

BASIS_URL = "https://www.mysports.ch/api/epg"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}
REQUEST_TIMEOUT_SEKUNDEN = 25

_MYSPORTS_PATTERN = re.compile(r"^MYSPORTS\s*(\d{1,2}|EDGE)\b", re.IGNORECASE)

# Modul-weiter Cache fuer die EINE API-Antwort: None (noch nicht
# geladen) oder ein Tupel (kanal_index, sendungen_je_kanal) - beides
# aus derselben Antwort abgeleitet, ein einziger HTTP-Request pro Lauf.
_cache = None


def _sprachtext(rohtext):
    """event_title ist bereits ein Dict, event_subtitle/event_plot sind
    aber JSON-KODIERTE STRINGS (siehe Moduldocstring). Liefert den
    deutschen Text (Fallback: englisch, dann irgendeine Sprache, dann
    leer)."""
    if isinstance(rohtext, dict):
        werte = rohtext
    elif isinstance(rohtext, str) and rohtext.strip():
        try:
            werte = json.loads(rohtext)
        except (ValueError, TypeError):
            return rohtext.strip()
    else:
        return ""
    if not isinstance(werte, dict):
        return ""
    for sprache in ("de", "en"):
        if werte.get(sprache):
            return werte[sprache].strip()
    for wert in werte.values():
        if wert:
            return wert.strip()
    return ""


def _laden():
    """Laedt und parst (und cached modulweit) die komplette EPG-Antwort
    von mysports.ch EIN einziges Mal. Liefert ein Tupel
    (kanal_index: alias_name -> channel_id,
     sendungen_je_kanal: channel_id -> Sendungsliste),
    oder ({}, {}) bei jedem Fehler."""
    global _cache
    if _cache is not None:
        return _cache

    kanal_index = {}
    sendungen_je_kanal = {}
    try:
        response = _http.mit_retry(
            requests.get, BASIS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN
        )
        response.raise_for_status()
        antwort = response.json()

        for kanal in antwort.get("channel", []):
            channel_id = kanal.get("channel_id")
            if not channel_id:
                continue
            for alias in kanal.get("alias_names", []):
                # Bei Aliasen wie "mysports1", die sowohl fuer den
                # deutschen ("Eins") als auch franzoesischen ("Un")
                # Kanal 1 auftauchen, gewinnt der ZUERST gefundene
                # (deutscher Kanal steht zuerst in der API-Antwort).
                kanal_index.setdefault(alias.lower(), channel_id)

        for event in antwort.get("events", []):
            titel = _sprachtext(event.get("event_title"))
            if not titel:
                continue
            try:
                start = datetime.fromtimestamp(int(event["event_start"]), tz=timezone.utc)
                stop = datetime.fromtimestamp(int(event["event_end"]), tz=timezone.utc)
            except (KeyError, ValueError, TypeError):
                continue
            if stop <= start:
                continue

            beschreibung = _sprachtext(event.get("event_subtitle"))
            if not beschreibung or beschreibung == titel:
                beschreibung = _sprachtext(event.get("event_plot")) or titel

            channel_id = event.get("event_channel_id")
            sendungen_je_kanal.setdefault(channel_id, []).append({
                "title": titel,
                "beschreibung": beschreibung,
                "bild": event.get("event_thumbnail") or None,
                "start": start,
                "stop": stop,
            })

        for channel_id in sendungen_je_kanal:
            sendungen_je_kanal[channel_id].sort(key=lambda p: p["start"])

        print(
            f"MySports-EPG (mysports.ch): {len(antwort.get('events', []))} Sendungen "
            f"fuer {len(sendungen_je_kanal)} Kanaele geladen."
        )
    except Exception as e:
        print(f"MySports-EPG (mysports.ch): Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        kanal_index = {}
        sendungen_je_kanal = {}

    _cache = (kanal_index, sendungen_je_kanal)
    return _cache


def mysports_kanal_finden(kanalname):
    """Erkennt "MYSPORTS <Nummer>" bzw. "MYSPORTS EDGE" (mit beliebigen
    Whitespace-/HD/4K/VIP/RAW-Zusaetzen) und gibt die zugehoerige
    mysports.ch-Kanal-ID (channel_id-Hash) zurueck, sonst None.
    "MYSPORTS 10" liefert bewusst None - existiert bei mysports.ch
    nicht (nur 1-9 + EDGE)."""
    if not kanalname:
        return None
    treffer = _MYSPORTS_PATTERN.match(kanalname.strip())
    if not treffer:
        return None
    schluessel = treffer.group(1).upper()

    kanal_index, _ = _laden()
    if schluessel == "EDGE":
        return kanal_index.get("mysportsedge")
    return kanal_index.get(f"mysports{schluessel.lower()}")


def mysports_hole_programme(channel_id, tage=2):
    """Liefert die bereits geladenen Programmdaten fuer eine per
    mysports_kanal_finden() ermittelte Kanal-ID. Leere Liste bei jedem
    Fehler oder wenn channel_id None ist. `tage` bleibt aus Kompatibilitaet
    zu den anderen *_hole_programme()-Funktionen erhalten, wird hier aber
    nicht filternd angewendet - die API liefert ohnehin nur ein festes,
    bereits sinnvoll begrenztes Zeitfenster (aktuell ca. 2 Wochen)."""
    if not channel_id:
        return []
    _, sendungen_je_kanal = _laden()
    return sendungen_je_kanal.get(channel_id, [])
