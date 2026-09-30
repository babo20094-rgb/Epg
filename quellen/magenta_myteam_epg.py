"""Echte Programmdaten fuer MAGENTA SPORT PPV 1-18 / MYTEAM SPORT 1-18 -
AUTOMATISCH fuer jeden "DE|MAGENTA SPORT PPV N HD/RAW"- ODER
"DE|MYTEAM SPORT N HD"-Sender in sender.txt (beide Namensschemata
bezeichnen dieselben 18 Kanaele, siehe unten).

Hintergrund: Magentas eigene oeffentliche API (magenta_epg.py, MPX-Feed)
fuehrt zwar KEINEN eigenen "MagentaSport"-Basiskanal mit Einzel-Event-
Titeln (nur einen generischen "Programmübersicht"-Platzhalter alle 4h),
seit September 2026 aber bestaetigt sehr wohl 18 eigene "Sport N -
myTeamTV"-STATIONEN mit echten Team-vs-Team-Titeln (z.B. "LIVE: Kölner
Haie - Eisbären Berlin") - dieselbe MPX-Feed-API, die auch die
www.magenta.tv/tv-guide-Webseite selbst verwendet (Nutzerhinweis
September 2026: Team-Namen fehlten im vorher genutzten epgshare01.online-
Spiegel). Die Rohnamen dieser Sender in der eigenen IPTV-Playlist des
Nutzers sind zudem komplett STATISCH (kein NEXT/LIVE/ENDED-Marker wie bei
DYN PPV/DAZN PPV) - der `m3u_playlist_abgleichen()`-Live-Event-Mechanismus
greift hier also strukturell nicht.

**Erster Versuch (bevorzugt): MPX-Feed-API direkt (via magenta_epg.py,
"neu"-Quelle)** - liefert echte Team-vs-Team-Titel statt nur der
Liga-/Wettbewerbsnamen. Kanalzuordnung ueber exakten Nummern-Vergleich
gegen die "Sport N - myTeamTV"-Stationsnamen aus
`magenta_hole_kanalliste()` (bereits modulweit gecacht, kein
zusaetzlicher Netzwerk-Aufruf noetig, falls schon ein MAGENTA:-Sender im
selben Lauf lief). Bewusst KEIN Fuzzy-/Kern-Abgleich wie bei
`magenta_kanal_finden()` (das waere fuer automatisches, nicht Opt-in-
Matching zu riskant) - nur exakter Nummern-Vergleich, kein
Fehltreffer-Risiko.

**Zweiter Versuch (Fallback, falls MPX nichts liefert): der oeffentliche,
community-gepflegte XMLTV-Spiegel von epgshare01.online**, der Magentas
PPV-Events ebenfalls unter der Marke "myTeamTV" fuehrt ("Sport 1 -
myTeamTV" bis "Sport 18 - myTeamTV", Teil des allgemeinen DE1-
Sammelfeeds `epg_ripper_DE1.xml.gz`) - liefert nur generische Liga-Titel
ohne Teams (z.B. "Live: DEL"), aber immerhin noch echte Zeiten/
Wettbewerbe, falls der MPX-Feed fuer diesen Kanal/Tag ausnahmsweise
nichts hat. Genau wie bei plutotv_epg.py/sportklub_epg.py wird die
komplette XMLTV-Datei nur EINMAL pro Lauf geladen (gefiltert auf die 18
Sport-N-myTeamTV-Kanaele, um den Speicherbedarf klein zu halten trotz
des grossen Sammelfeeds), danach lokal gematcht ohne weitere Netzwerk-
Aufrufe.

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

import threading
import requests
from quellen import _http
from quellen.magenta_epg import magenta_hole_kanalliste, magenta_hole_programme

URL = "https://epgshare01.online/epgshare01/epg_ripper_DE1.xml.gz"

REQUEST_TIMEOUT_SEKUNDEN = 60

# Modul-weiter Cache: {"kanaele": [...], "programme": {kanal_id: [...]}}
_daten_cache = None
# Schuetzt den Erstzugriff auf _daten_cache: bei gleichzeitigem Zugriff aus
# mehreren Threads (siehe _parallel_abrufen() in generate_epg.py)
# wuerden ohne diese Sperre alle Threads gleichzeitig "noch nicht
# geladen" sehen und dieselbe Datei jeder fuer sich parallel
# herunterladen, statt dass nur einer laedt und die anderen warten.
_daten_cache_lock = threading.Lock()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# "MAGENTA SPORT PPV N"/"MAGENTA SPORT PPV N HD/RAW" UND "MYTEAM SPORT N
# HD" (beide eigene sender.txt-Konventionen fuer dieselben 18 Kanaele)
# vs. "Sport N - myTeamTV" bei magenta.tv (MPX-Feed) UND epgshare01.online.
_SENDER_NUMMER_PATTERN = re.compile(
    r"^(?:MAGENTA\s*SPORT\s*PPV|MYTEAM\s*SPORT)\s*0*(\d+)", re.IGNORECASE
)
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

    with _daten_cache_lock:
        # Erneut pruefen: ein anderer Thread koennte das Laden
        # bereits erledigt haben, waehrend dieser Thread auf die
        # Sperre wartete.
        if _daten_cache is not None:
            return _daten_cache

        try:
            response = _http.mit_retry(requests.get, URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
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


def _mpx_kanal_finden(ziel_nummer):
    """Sucht die "Sport N - myTeamTV"-Station mit passender Nummer in
    der (modulweit gecachten) MPX-Kanalliste von magenta_epg.py. Gibt
    die MPX-site_id zurueck oder None."""
    try:
        kanaele = magenta_hole_kanalliste()
    except Exception:
        return None
    if not kanaele:
        return None

    for kanal in kanaele:
        kanal_treffer = _KANAL_NUMMER_PATTERN.match((kanal.get("name") or "").strip())
        if kanal_treffer and kanal_treffer.group(1) == ziel_nummer:
            return kanal["site_id"]

    return None


def magenta_myteam_kanal_finden(kanalname):
    """Sucht den myTeamTV-Kanal, der exakt zur sender.txt-Nummer
    (MAGENTA SPORT PPV N ODER MYTEAM SPORT N) passt. Gibt ein Tupel
    ("mpx"|"epgshare", site_id) zurueck oder None (kein Fehltreffer-
    Risiko: nur exakter Nummern-Vergleich, kein Fuzzy-Abgleich). "mpx"
    (magenta.tv MPX-Feed, echte Team-vs-Team-Titel) wird bevorzugt,
    "epgshare" (epgshare01.online-Spiegel, nur generische Liga-Titel)
    ist der Fallback, falls die MPX-Kanalliste fuer diese Nummer keinen
    Treffer hat."""
    treffer = _SENDER_NUMMER_PATTERN.match(kanalname.strip())
    if not treffer:
        return None
    ziel_nummer = treffer.group(1)

    mpx_site_id = _mpx_kanal_finden(ziel_nummer)
    if mpx_site_id is not None:
        return ("mpx", mpx_site_id)

    daten = _xml_laden()
    if not daten or not daten["kanaele"]:
        return None

    for kanal in daten["kanaele"]:
        kanal_treffer = _KANAL_NUMMER_PATTERN.match(kanal["name"].strip())
        if kanal_treffer and kanal_treffer.group(1) == ziel_nummer:
            return ("epgshare", kanal["site_id"])

    return None


def magenta_myteam_hole_programme(kanal_ref, tage=2):
    """Liefert Programmdaten fuer den gegebenen Kanal (Rueckgabewert von
    magenta_myteam_kanal_finden()), begrenzt auf die naechsten `tage`
    Tage ab heute (UTC). Leere Liste bei jedem Fehler oder wenn keine
    Sendungen vorhanden sind."""
    if not kanal_ref:
        return []
    quelle, site_id = kanal_ref
    if site_id is None:
        return []

    if quelle == "mpx":
        # MPX liefert kein eigenes <icon> je Sendung (siehe
        # magenta_hole_programme()) - bleibt hier bewusst ohne
        # nachtraeglich gesetztes Logo (anders als beim epgshare01-Zweig
        # unten), kein Korrektheitsproblem, nur ein optisches Detail.
        try:
            return magenta_hole_programme({"quelle": "neu", "site_id": site_id}, tage)
        except Exception:
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
