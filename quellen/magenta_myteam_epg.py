"""Echte Programmdaten fuer MAGENTA SPORT PPV 1-18 - AUTOMATISCH fuer
jeden "DE|MAGENTA SPORT PPV N HD/RAW"-Sender in sender.txt.

Hintergrund: Magentas eigene oeffentliche API (magenta_epg.py, MPX-Feed)
fuehrt KEINE eigenen PPV-Kanaele - nur einen Basis-Kanal "MagentaSport"
mit einem generischen "Programmübersicht"-Platzhalter alle 4h, keine
echten Einzel-Event-Titel. Die Rohnamen dieser Sender in der eigenen
IPTV-Playlist des Nutzers sind zudem komplett STATISCH (kein NEXT/LIVE/
ENDED-Marker wie bei DYN PPV/DAZN PPV) - der `m3u_playlist_abgleichen()`-
Live-Event-Mechanismus greift hier also strukturell nicht.

Der oeffentliche, community-gepflegte XMLTV-Spiegel von epgshare01.online
fuehrt Magentas PPV-Events stattdessen unter der Marke "myTeamTV" (die
zugehoerige interne Magenta-Kanalgruppe: "Sport 1 - myTeamTV" bis "Sport
18 - myTeamTV", Teil des allgemeinen DE1-Sammelfeeds
`epg_ripper_DE1.xml.gz`, nicht ein eigener Feed) - Nummerierung 1-18
entspricht exakt unseren "MAGENTA SPORT PPV N"-Sendern. Bestaetigt echte
Daten (z.B. "Live: Champions Hockey League" auf Kanal 1).

Genau wie bei plutotv_epg.py/sportklub_epg.py wird die komplette
XMLTV-Datei nur EINMAL pro Lauf geladen (gefiltert auf die 18 Sport-N-
myTeamTV-Kanaele, um den Speicherbedarf klein zu halten trotz des
grossen Sammelfeeds), danach lokal gematcht ohne weitere Netzwerk-
Aufrufe. Kanalzuordnung laeuft bewusst NICHT ueber Fuzzy-/Kern-Abgleich,
sondern ueber einen exakten Nummern-Vergleich (Regex auf "MAGENTA SPORT
PPV N") - kein Fehltreffer-Risiko.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt der Download, das
Parsen oder die Kanalsuche fehl, bekommt der betroffene Sender in
generate_epg.py einfach die normale, kategoriebasierte generische
EPG-Generierung wie jeder andere Sender - dieses Modul darf einen Lauf
niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import gzip
import re
import xml.etree.ElementTree as ET

import requests

URL = "https://epgshare01.online/epgshare01/epg_ripper_DE1.xml.gz"

REQUEST_TIMEOUT_SEKUNDEN = 60

# Modul-weiter Cache: {"kanaele": [...], "programme": {kanal_id: [...]}}
_daten_cache = None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# "MAGENTA SPORT PPV N"/"MAGENTA SPORT PPV N HD/RAW" (eigene sender.txt-
# Konvention) vs. "Sport N - myTeamTV" bei epgshare01.online.
_SENDER_NUMMER_PATTERN = re.compile(r"^MAGENTA\s*SPORT\s*PPV\s*0*(\d+)", re.IGNORECASE)
_KANAL_NUMMER_PATTERN = re.compile(r"^Sport\s*0*(\d+)\s*-\s*myTeamTV", re.IGNORECASE)


def _xml_laden():
    """Laedt und parst (und cached) NUR die "Sport N - myTeamTV"-Kanaele
    (samt Sendungen) aus dem grossen DE1-Sammelfeed - Filterung waehrend
    des Parsens haelt den Speicherbedarf klein. Gibt {"kanaele": [...],
    "programme": {id: [...]}} zurueck, oder None bei jedem Fehler
    (Netzwerk, HTTP-Status, kaputtes Gzip/XML)."""
    global _daten_cache

    if _daten_cache is not None:
        return _daten_cache

    try:
        response = requests.get(URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        rohbytes = response.content

        try:
            xml_bytes = gzip.decompress(rohbytes)
        except OSError:
            xml_bytes = rohbytes

        wurzel = ET.fromstring(xml_bytes)

        relevante_ids = set()
        kanaele = []
        for kanal_tag in wurzel.findall("channel"):
            kanal_id = kanal_tag.get("id")
            name_tag = kanal_tag.find("display-name")
            name = name_tag.text.strip() if name_tag is not None and name_tag.text else ""
            if not kanal_id or not name:
                continue
            if not _KANAL_NUMMER_PATTERN.match(name):
                continue
            relevante_ids.add(kanal_id)
            kanaele.append({"site_id": kanal_id, "name": name})

        programme = {}
        for prog_tag in wurzel.findall("programme"):
            kanal_id = prog_tag.get("channel")
            if kanal_id not in relevante_ids:
                continue

            start_roh = prog_tag.get("start")
            stop_roh = prog_tag.get("stop")
            if not start_roh or not stop_roh:
                continue

            start = _xmltv_zeit_parsen(start_roh)
            stop = _xmltv_zeit_parsen(stop_roh)
            if start is None or stop is None:
                continue

            titel_tag = prog_tag.find("title")
            titel = titel_tag.text.strip() if titel_tag is not None and titel_tag.text else ""
            if not titel:
                continue

            beschr_tag = prog_tag.find("desc")
            beschreibung = beschr_tag.text.strip() if beschr_tag is not None and beschr_tag.text else ""

            programme.setdefault(kanal_id, []).append({
                "title": titel,
                "beschreibung": beschreibung,
                "bild": None,
                "start": start,
                "stop": stop,
            })

        for eintraege in programme.values():
            eintraege.sort(key=lambda s: s["start"])

        print(f"Magenta-myTeamTV-EPG: {len(kanaele)} Kanaele, {len(programme)} Kanaele mit Sendungen geladen.")

        daten = {"kanaele": kanaele, "programme": programme}
        _daten_cache = daten
        return daten
    except Exception as e:
        print(f"Magenta-myTeamTV-EPG: Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        # Fehlschlag wird ebenfalls gecacht (leeres, aber nicht-None
        # Dict statt None) - verhindert, dass bei einem dauerhaften Fehler
        # (Netzwerk down, Host tot) JEDER einzelne Sender in generate_epg.py
        # denselben fehlschlagenden Download erneut versucht.
        _daten_cache = {"kanaele": [], "programme": {}}
        return _daten_cache


def _xmltv_zeit_parsen(text):
    """Parst das XMLTV-Zeitformat 'YYYYMMDDHHMMSS +ZZZZ' zu einem
    tz-aware datetime (UTC). None bei Parse-Fehler."""
    try:
        return datetime.strptime(text.strip(), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
    except Exception:
        return None


def magenta_myteam_kanal_finden(kanalname):
    """Sucht den myTeamTV-Kanal, der exakt zur sender.txt-Nummer
    (MAGENTA SPORT PPV N) passt. Gibt die Kanal-ID zurueck oder None
    (kein Fehltreffer-Risiko: nur exakter Nummern-Vergleich, kein
    Fuzzy-Abgleich)."""
    daten = _xml_laden()
    if not daten or not daten["kanaele"]:
        return None

    treffer = _SENDER_NUMMER_PATTERN.match(kanalname.strip())
    if not treffer:
        return None
    ziel_nummer = treffer.group(1)

    for kanal in daten["kanaele"]:
        kanal_treffer = _KANAL_NUMMER_PATTERN.match(kanal["name"].strip())
        if kanal_treffer and kanal_treffer.group(1) == ziel_nummer:
            return kanal["site_id"]

    return None


def magenta_myteam_hole_programme(site_id, tage=2):
    """Liefert die bereits geladenen Programmdaten fuer den gegebenen
    Kanal (site_id) aus dem Modul-Cache, begrenzt auf die naechsten
    `tage` Tage ab heute (UTC). Leere Liste bei jedem Fehler oder wenn
    keine Sendungen vorhanden sind. Der generische "myTeamTV: Momentan
    kein Programm"-Platzhalter der Quelle selbst wird bewusst NICHT mehr
    herausgefiltert (anders als frueher) - auf Nutzerwunsch soll bei
    Leerlauf genau der Text erscheinen, den die Quelle selbst dafuer
    liefert, statt eines selbst ausgedachten Ersatztextes."""
    if site_id is None:
        return []

    daten = _xml_laden()
    if not daten:
        return []

    eintraege = daten["programme"].get(site_id, [])
    if not eintraege:
        return []

    heute = datetime.now(timezone.utc).date()
    erlaubte_tage = {heute + timedelta(days=i) for i in range(tage)}

    # Eigenes, selbst gehostetes Logo statt keines - epgshare01.online
    # liefert fuer diese Kanaele kein <icon>, daher wird hier zusaetzlich
    # (zur Sicherheit/Redundanz) dasselbe Logo wie bei den "MAGENTA SPORT
    # PPV N"-sender.txt-Zeilen als Sendungsbild gesetzt.
    nummer_treffer = re.search(r"Sport\.(\d+)\.", site_id)
    bild = (
        f"https://raw.githubusercontent.com/babo20094-rgb/Epg/main/logos/magenta_myteam/{nummer_treffer.group(1)}.png"
        if nummer_treffer else None
    )

    return [
        {**p, "bild": bild}
        for p in eintraege
        if (p["start"].date() in erlaubte_tage or p["stop"].date() in erlaubte_tage)
    ]
