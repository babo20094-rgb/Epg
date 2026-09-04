"""Echte Programmdaten von tvprofil.net (XMLTV-Service von tvprofil.com,
oeffentlich, loginfrei) - AUTOMATISCH fuer HR/BA/RS/SI/MK/ME/MNG/MO/CG-
Sender, als LETZTER Fallback nach den jeweiligen Haupt-Quellen (MojMaxTV/
Telemach/mtel.ba/mymedia.ba/klix.ba/mts.rs/Siol/SportKlub - siehe deren
Verarbeitungsbloecke in generate_epg.py). Kein eigenes sender.txt-Praefix
noetig.

Hintergrund: tvprofil.net fuehrt nur eine kleine, feste Liste von ca. 56
Kanaelen (https://tvprofil.net/xmltv/data/channel-list.tvprofil.net.xml),
ueberwiegend grosse, ohnehin schon abgedeckte Sender (HTV1, RTL HR, RTS1,
ZDF, ...) - aber auch ein paar kleinere, sonst nirgends echte Daten
liefernde Sender (z.B. Plava Vinkovačka, TV Zapad, CMC/CMC Music, Doma TV,
Nova M), fuer die es sich als schmale Ergaenzung lohnt.

Kanalzuordnung laeuft NUR ueber einen EXAKTEN Namensabgleich (Diakritika-
und VIP/RAW-tolerant, siehe _normalisiere()) - kein Fuzzy-Anteil, da die
Kanalliste zu klein und die Namen teils zu kurz/aehnlich fuer einen
sicheren unscharfen Abgleich sind (das immer wiederkehrende Fehltreffer-
Muster dieser Session).

Pro Kanal wird die wochenweise XML-Datei
(tvprofil.net/xmltv/data/<site_id>/weekly_<site_id>_tvprofil.net.xml) live
abgerufen und pro site_id gecacht (kein erneuter Download bei mehreren
sender.txt-Zeilen mit demselben Kanal). Die Kanalliste selbst wird nur
EINMAL pro Lauf geladen.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen - dieses Modul darf einen
Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import re
import unicodedata
import xml.etree.ElementTree as ET

import requests

KANALLISTE_URL = "https://tvprofil.net/xmltv/data/channel-list.tvprofil.net.xml"
PROGRAMM_URL_MUSTER = "https://tvprofil.net/xmltv/data/{site_id}/weekly_{site_id}_tvprofil.net.xml"

REQUEST_TIMEOUT_SEKUNDEN = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# Modul-weiter Cache: Kanalliste einmal pro Lauf, Programmdaten pro
# site_id (nur fuer tatsaechlich abgefragte Kanaele, nicht alle 56 auf
# Vorrat).
_kanalliste_cache = None
_programme_cache = {}


def _normalisiere(name):
    """Normalisiert einen Sendernamen fuer den exakten Vergleich: entfernt
    Diakritika (NFKD-Zerlegung, z.B. "č" -> "c"), die playlist-eigenen
    Deko-Marker VIP/RAW/HD/FHD/UHD/SD/HEVC/4K/8K, Satzzeichen und
    ueberschuessige Leerzeichen, wandelt in Grossbuchstaben."""
    zerlegt = unicodedata.normalize("NFKD", name)
    zerlegt = "".join(z for z in zerlegt if not unicodedata.combining(z))
    ohne_marker = re.sub(
        r"\b(VIP|RAW|HD|FHD|UHD|SD|HEVC|4K|8K)\b", " ", zerlegt, flags=re.IGNORECASE
    )
    ohne_satzzeichen = re.sub(r"[^A-Za-z0-9]+", " ", ohne_marker)
    return ohne_satzzeichen.strip().upper()


def _kanalliste_laden():
    """Laedt und parst (und cached) die komplette tvprofil.net-Kanalliste.
    Gibt eine Liste von {"site_id": ..., "name": ...} zurueck, oder []
    bei jedem Fehler (Netzwerk, HTTP-Status, kaputtes XML)."""
    global _kanalliste_cache

    if _kanalliste_cache is not None:
        return _kanalliste_cache

    try:
        response = requests.get(KANALLISTE_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        wurzel = ET.fromstring(response.content)

        kanaele = []
        for kanal_tag in wurzel.findall("channel"):
            site_id = kanal_tag.get("id")
            name_tag = kanal_tag.find("display-name")
            name = name_tag.text.strip() if name_tag is not None and name_tag.text else ""
            if not site_id or not name:
                continue
            kanaele.append({"site_id": site_id, "name": name})

        print(f"TvProfil.net-EPG: {len(kanaele)} Kanaele in der Kanalliste geladen.")
        _kanalliste_cache = kanaele
        return kanaele
    except Exception as e:
        print(f"TvProfil.net-EPG: Kanalliste laden fehlgeschlagen ({e}), ueberspringe.")
        _kanalliste_cache = []
        return _kanalliste_cache


def tvprofil_kanal_finden(kanalname):
    """Sucht den tvprofil.net-Kanal mit exakt (normalisiert) passendem
    Namen. Gibt die site_id zurueck oder None (kein Fehltreffer-Risiko:
    nur exakter Vergleich, kein Fuzzy-Abgleich)."""
    kanaele = _kanalliste_laden()
    if not kanaele:
        return None

    ziel = _normalisiere(kanalname)
    if not ziel:
        return None

    for kanal in kanaele:
        if _normalisiere(kanal["name"]) == ziel:
            return kanal["site_id"]

    return None


def _xmltv_zeit_parsen(text):
    """Parst das XMLTV-Zeitformat 'YYYYMMDDHHMMSS +ZZZZ' zu einem
    tz-aware datetime (UTC). None bei Parse-Fehler."""
    try:
        return datetime.strptime(text.strip(), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
    except Exception:
        return None


def tvprofil_hole_programme(site_id, tage=3):
    """Laedt (und cached pro site_id) die wochenweise Programm-XML fuer
    den gegebenen Kanal und liefert die Sendungen der naechsten `tage`
    Tage ab heute (UTC). Leere Liste bei jedem Fehler."""
    if site_id is None:
        return []

    if site_id not in _programme_cache:
        try:
            url = PROGRAMM_URL_MUSTER.format(site_id=site_id)
            response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
            response.raise_for_status()
            wurzel = ET.fromstring(response.content)

            sendungen = []
            for prog_tag in wurzel.findall("programme"):
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

                sendungen.append({
                    "title": titel,
                    "beschreibung": beschreibung,
                    "start": start,
                    "stop": stop,
                })

            sendungen.sort(key=lambda s: s["start"])
            _programme_cache[site_id] = sendungen
        except Exception as e:
            print(f"TvProfil.net-EPG: Programm fuer '{site_id}' laden fehlgeschlagen ({e}), ueberspringe.")
            _programme_cache[site_id] = []

    eintraege = _programme_cache[site_id]
    if not eintraege:
        return []

    heute = datetime.now(timezone.utc).date()
    erlaubte_tage = {heute + timedelta(days=i) for i in range(tage)}

    return [
        p for p in eintraege
        if p["start"].date() in erlaubte_tage or p["stop"].date() in erlaubte_tage
    ]
