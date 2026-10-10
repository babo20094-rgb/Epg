"""Optionale, echte Programmdaten aus den epgshare01-Feeds RS1 und BA1
(Serbien/Bosnien) - AUTOMATISCH fuer Ex-YU-Sender ohne andere echte Quelle
(Laender EXYU/RS/HR/MK/BA/SI/MNG/MO, kein sender.txt-Praefix noetig).

Hintergrund (Oktober 2026): Die bestehenden Ex-YU-Quellen (mts.rs,
Telemach/mtel/klix, MojMaxTV, Siol, ...) kennen einige Sender nicht, die
epgshare01 fuehrt (z.B. TV Zvezda, TV Hype, Belle Amie, Tanjug, UNA TV,
Zadruga Live 2-4, TV Vijesti, RTL Croatia World sowie mehrere Radio-
Sender). Ein Abgleich aller Ex-YU-Zeilen aus sender.txt gegen RS1/BA1/HR1
ergab nur ca. 25 zusaetzliche Treffer - der Rest sind Filmsammlungen/
Serien/Musikbloecke ohne EPG. Wie bei epgshare_de_epg.py: je Feed EINE
Datei, nur EINMAL pro Lauf geladen (RS1 ~8 MB, BA1 ~2 MB, zusammen ca.
2-3 s) und danach lokal gematcht.

Kanalabgleich ABSICHTLICH nur EXAKT (nach Normalisierung ohne HD/FHD/RAW/
VIP/TV/Klammerzusatz wie "(BIH)"), KEIN unscharfer Abgleich - die Feeds
enthalten viele fremde Kanaele, ein Fuzzy-Treffer wuerde leicht den
falschen Sender erwischen.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt ein Download oder
das Parsen fehl, bleibt es fuer die betroffenen Sender beim bisherigen
generischen Platzhalter - dieses Modul darf einen Lauf niemals zum
Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import gzip
import re
import threading
import unicodedata

import requests
from quellen import _http
from quellen.epgshare_de_epg import _feed_parsen

# Reihenfolge = Prioritaet bei gleichnamigen Kanaelen in mehreren Feeds.
FEEDS = ["RS1", "BA1"]
URL = "https://epgshare01.online/epgshare01/epg_ripper_{feed}.xml.gz"

REQUEST_TIMEOUT_SEKUNDEN = 120

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# Nur Sender dieser Laender (Land-Feld in sender.txt) werden abgeglichen.
# "BS" (Film-Genre-Sammlungen wie "BS| SCI-FI") bewusst NICHT dabei: der
# Name passt zufaellig auf einen echten Kanal, ist aber eine VOD-Rubrik.
LAENDER = {"EXYU", "RS", "HR", "MK", "BA", "SI", "MNG", "MO"}

# Woerter, die beim Namensvergleich ignoriert werden.
_IGNORIERT = {
    "HD", "FHD", "UHD", "4K", "SD", "HEVC", "RAW", "VIP", "LIVE", "60FPS",
    "H265", "1080P", "720P", "TV", "CHANNEL", "THE",
}

_daten_cache = None
_daten_cache_lock = threading.Lock()


def _norm(name):
    """Normalisiert einen Sendernamen fuer den exakten Vergleich:
    Diakritika/hochgestellte Zeichen weg, Klammerzusaetze weg, Gross-
    schreibung, Zusatzwoerter (HD/RAW/VIP/TV ...) ignoriert."""
    s = (name or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s).upper()
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]", "", s).replace("&", "AND")
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return "".join(w for w in s.split() if w not in _IGNORIERT)


def _xml_laden():
    """Laedt und parst (und cached) RS1 und BA1. Gibt {"programme":
    {site_id: [...]}, "name_index": {normname: site_id}} zurueck. Ein
    fehlgeschlagener Feed wird uebersprungen (Fehlschlaege werden
    mitgecached)."""
    global _daten_cache

    if _daten_cache is not None:
        return _daten_cache

    with _daten_cache_lock:
        if _daten_cache is not None:
            return _daten_cache

        kanaele, programme = [], {}
        for feed in FEEDS:
            try:
                response = _http.mit_retry(
                    requests.get, URL.format(feed=feed), headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN
                )
                response.raise_for_status()
                rohbytes = response.content
                try:
                    xml_bytes = gzip.decompress(rohbytes)
                except OSError:
                    xml_bytes = rohbytes

                feed_kanaele, feed_programme = _feed_parsen(feed, xml_bytes)
                kanaele.extend(feed_kanaele)
                programme.update(feed_programme)
                print(f"EpgshareBalkan-EPG ({feed}): {len({k['site_id'] for k in feed_kanaele})} Kanaele mit Sendungen geladen.")
            except Exception as e:
                print(f"EpgshareBalkan-EPG ({feed}): Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")

        # Je normalisiertem Namen gewinnt der erste Feed in FEEDS.
        name_index = {}
        for kanal in kanaele:
            schluessel = _norm(kanal["name"])
            if len(schluessel) >= 3 and schluessel not in name_index:
                name_index[schluessel] = kanal["site_id"]

        _daten_cache = {"programme": programme, "name_index": name_index}
        return _daten_cache


def epgshare_balkan_kanal_finden(sendername, land):
    """Sucht den RS1/BA1-Kanal zu sendername (nur fuer Sender der Laender in
    LAENDER) per exaktem Namensabgleich - KEIN unscharfer Abgleich.
    Gibt die site_id ('<FEED>:<kanal_id>') zurueck oder None."""
    if (land or "").strip().upper() not in LAENDER:
        return None

    schluessel = _norm(sendername)
    if len(schluessel) < 3:
        return None

    daten = _xml_laden()
    if not daten:
        return None
    return daten["name_index"].get(schluessel)


def epgshare_balkan_hole_programme(site_id, tage=3):
    """Liefert die geladenen Programmdaten fuer den Kanal, begrenzt auf die
    naechsten `tage` Tage ab heute (UTC). Leere Liste bei jedem Fehler."""
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

    return [
        p for p in eintraege
        if p["start"].date() in erlaubte_tage or p["stop"].date() in erlaubte_tage
    ]
