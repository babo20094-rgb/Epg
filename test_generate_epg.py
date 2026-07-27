"""
Unit-Tests für epg_lib.py (die reinen, seiteneffektfreien Funktionen
hinter generate_epg.py).

Ausführen mit:
    pip install pytest --break-system-packages
    pytest test_generate_epg.py -v

Diese Tests prüfen NICHT das gesamte generate_epg.py (das liest
sender.txt, ruft die DYN-API auf und schreibt eine XML-Datei), sondern
gezielt die Logik-Bausteine, die am ehesten kaputtgehen, wenn Keywords,
Kategorien oder Sprachen erweitert werden:

- Kategorie-Erkennung anhand von Keywords (standard_beschreibung)
- Prioritätsreihenfolge zwischen Kategorien (z.B. NEWS vor UNTERHALTUNG)
- Sprachzuordnung nach Land
- Datumsbezug im Sendetitel
- DYN/Flo-Racing-Zeit-Parsing
- Poster-Zuordnung je Kategorie
"""

import datetime
import pytest

from epg_lib import (
    KATEGORIEN,
    KATEGORIE_PRIORITAET,
    POSTER_URLS,
    DEFAULT_POSTER,
    standard_beschreibung,
    kategorie_label,
    sprache_fuer_land,
    sendetitel,
    datumspraefix,
    parse_event_zeit,
    poster_fuer_kategorie,
)


# ==========================================================
# Kategorie-Erkennung
# ==========================================================

@pytest.mark.parametrize("sender,erwartete_kategorie", [
    ("CNN", "NEWS"),
    ("BBC NEWS", "NEWS"),
    ("Big Brother", "REALITY"),
    ("Nickelodeon", "KINDER"),
    ("ESPN Gaming Twitch", "GAMING"),
    ("Comedy Central", "COMEDY"),
    ("Discovery Science", "WISSEN"),
    ("Random Sender Ohne Keyword", None),
])
def test_kategorie_erkennung(sender, erwartete_kategorie):
    _, kategorie_key = standard_beschreibung("DE", sender)
    assert kategorie_key == erwartete_kategorie


def test_news_schlaegt_nicht_unterhaltung():
    """NEWS steht in der Prioritätsliste weit vor UNTERHALTUNG - ein
    Sender mit 'NEWS' im Namen darf nicht faelschlich als generische
    Unterhaltung eingeordnet werden."""
    _, kategorie_key = standard_beschreibung("DE", "Fox News")
    assert kategorie_key == "NEWS"


def test_reality_hat_prioritaet_vor_generischen_keywords():
    """REALITY steht ganz vorne in KATEGORIE_PRIORITAET, damit z.B.
    'Love Island' nicht von einer breiteren Kategorie ueberdeckt wird."""
    _, kategorie_key = standard_beschreibung("EN", "Love Island")
    assert kategorie_key == "REALITY"


def test_alle_kategorien_haben_pflichtfelder():
    """Jede Kategorie muss label/keywords/DE/EXYU/EN besitzen, sonst
    crasht standard_beschreibung oder kategorie_label zur Laufzeit."""
    pflichtfelder = {"label", "keywords", "DE", "EXYU", "EN"}
    for key, daten in KATEGORIEN.items():
        fehlende = pflichtfelder - daten.keys()
        assert not fehlende, f"Kategorie {key} fehlen Felder: {fehlende}"
        for sprache in ("DE", "EXYU", "EN"):
            assert len(daten[sprache]) > 0, f"{key}/{sprache} hat keine Textvarianten"
            assert sprache in daten["label"], f"{key} fehlt Label fuer {sprache}"


def test_kategorie_prioritaet_enthaelt_alle_kategorien():
    """Jede in KATEGORIEN definierte Kategorie muss auch in der
    Prüfreihenfolge KATEGORIE_PRIORITAET auftauchen, sonst wird sie nie
    erkannt (stiller Bug, den ein Test aktiv verhindert)."""
    assert set(KATEGORIE_PRIORITAET) == set(KATEGORIEN.keys())


# ==========================================================
# Sprachzuordnung
# ==========================================================

@pytest.mark.parametrize("land,erwartete_sprache", [
    ("DE", "DE"),
    ("HR", "EXYU"),
    ("RS", "EXYU"),
    ("BA", "EXYU"),
    ("US", "EN"),
    ("UK", "EN"),
    ("XX", "EN"),  # unbekanntes Land -> Fallback Englisch
])
def test_sprache_fuer_land(land, erwartete_sprache):
    assert sprache_fuer_land(land) == erwartete_sprache


def test_sprache_ignoriert_klammerzusatz():
    """'US (ESPN+ 001)' muss trotz Klammerzusatz als 'US' erkannt
    werden."""
    assert sprache_fuer_land("US (ESPN+ 001)") == "EN"


# ==========================================================
# Datumsbezug im Sendetitel
# ==========================================================

def test_datumspraefix_montag():
    montag = datetime.date(2026, 7, 27)  # tatsächlich ein Montag
    assert datumspraefix("DE", montag) == "Mo 27.07: "
    assert datumspraefix("EN", montag) == "Mon 27.07: "


def test_datumspraefix_none_ergibt_leerstring():
    assert datumspraefix("DE", None) == ""


def test_sendetitel_enthaelt_datumsbezug_wenn_angegeben():
    montag = datetime.date(2026, 7, 27)
    titel = sendetitel("SPORT", "DE", hash_wert=5, tageszeit="ABEND", datum=montag)
    assert titel.startswith("Mo 27.07: ")


def test_sendetitel_ohne_datum_hat_keinen_praefix():
    titel = sendetitel("SPORT", "DE", hash_wert=5, tageszeit="ABEND")
    assert not titel.startswith("Mo") and not titel.startswith("Di")


def test_sendetitel_ist_deterministisch():
    """Gleicher hash_wert + gleiche Parameter müssen immer denselben
    Titel liefern (kein Flackern zwischen Tagen)."""
    titel1 = sendetitel("SPORT", "DE", hash_wert=42, tageszeit="NACHT")
    titel2 = sendetitel("SPORT", "DE", hash_wert=42, tageszeit="NACHT")
    assert titel1 == titel2


# ==========================================================
# DYN / Flo-Racing Zeit-Parsing
# ==========================================================

@pytest.mark.parametrize("text,erwartet", [
    ("Sa 14:00 : Flo Racing 05", (14, 0)),
    ("Mi 09:30 : Flo Racing 12", (9, 30)),
    ("So 23:59 : Flo Racing 01", (23, 59)),
    ("- NO EVENT STREAMING - | 8K EXCLUSIVE | DE: DYN PPV 1", None),
    ("Flo Racing 03", None),
    ("FC Bayern - Real Madrid", None),
    ("", None),
    (None, None),
])
def test_parse_event_zeit(text, erwartet):
    assert parse_event_zeit(text) == erwartet


def test_parse_event_zeit_ignoriert_ungueltige_stunden():
    """'25:00' ist keine gültige Uhrzeit und darf nicht erkannt werden."""
    assert parse_event_zeit("Sa 25:00 : Flo Racing 05") is None


# ==========================================================
# Poster-Zuordnung
# ==========================================================

def test_poster_fuer_bekannte_kategorie():
    assert poster_fuer_kategorie("SPORT") == POSTER_URLS["SPORT"]


def test_poster_fallback_ohne_kategorie():
    assert poster_fuer_kategorie(None) == DEFAULT_POSTER


def test_poster_fallback_fuer_unbekannte_kategorie():
    assert poster_fuer_kategorie("GIBT_ES_NICHT") == DEFAULT_POSTER


def test_alle_kategorien_haben_ein_poster():
    """Jede Kategorie aus KATEGORIEN sollte ein eigenes Poster haben,
    damit nicht überall nur das Fallback-Bild erscheint."""
    fehlende = set(KATEGORIEN.keys()) - set(POSTER_URLS.keys())
    assert not fehlende, f"Kategorien ohne Poster: {fehlende}"


def test_poster_urls_sind_direkte_bild_links():
    """Alle Poster-URLs müssen auf den Wikimedia-Commons-Special:FilePath-
    Endpunkt zeigen (direkter Hotlink-fähiger Bildlink, kein HTML-Link
    auf eine Dateiseite)."""
    for kategorie, url in POSTER_URLS.items():
        assert "Special:FilePath/" in url, f"{kategorie}: {url} ist kein Special:FilePath-Link"
