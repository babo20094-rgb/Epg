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
- Poster-Zuordnung je Kategorie
"""

import datetime
import gzip
import json
import os
from unittest.mock import patch, MagicMock

import pytest

from epg_lib import (
    KATEGORIEN,
    KATEGORIE_PRIORITAET,
    standard_beschreibung,
    kategorie_label,
    sprache_fuer_land,
)

from quellen import telemach_epg
from quellen import mtel_epg
from quellen import sky_epg
from quellen import arena_epg
from quellen import magenta_epg
from quellen import dazn_epg
from quellen import freeview_epg
from quellen import tvguide_epg
from quellen import tvpassport_epg
from quellen import mts_epg
from quellen import mojmaxtv_epg
from quellen import siol_epg
from quellen import plutotv_epg
from quellen import klix_epg
from quellen import tvmovie_epg


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
# Telemach-EPG (opt-in TELEMACH:-Sender, siehe telemach_epg.py)
# ==========================================================

@pytest.fixture(autouse=True)
def _telemach_caches_zuruecksetzen():
    """Modul-weite Caches (Token/Kanalliste) muessen zwischen Tests
    zurueckgesetzt werden, sonst beeinflussen sich Tests gegenseitig."""
    telemach_epg._access_token_cache = None
    telemach_epg._kanalliste_cache = {}
    yield
    telemach_epg._access_token_cache = None
    telemach_epg._kanalliste_cache = {}


def _mock_response(json_daten, status_ok=True):
    response = MagicMock()
    response.json.return_value = json_daten
    if status_ok:
        response.raise_for_status.return_value = None
    else:
        response.raise_for_status.side_effect = Exception("HTTP-Fehler")
    return response


def test_telemach_erfolgreicher_abruf_liefert_echte_sendungen():
    """Erfolgreicher Login + Kanalsuche + Programmabruf muss echte
    Sendungen mit Titel/Zeiten liefern (gemockte Netzwerkaufrufe)."""
    login_response = _mock_response({"access_token": "abc123"})
    channels_response = _mock_response([
        {"id": "42", "name": "BHT 1"},
        {"id": "43", "name": "Sport Klub 1"},
    ])
    epg_response = _mock_response({
        "42": [
            {
                "title": "Dnevnik",
                "shortDescription": "Vijesti dana",
                "images": [{"path": "https://example.com/img.jpg"}],
                "startTime": "2026-08-09T19:00:00+00:00",
                "endTime": "2026-08-09T19:30:00+00:00",
            }
        ]
    })

    with patch("quellen.telemach_epg.requests.post", return_value=login_response), \
         patch("quellen.telemach_epg.requests.get", side_effect=[channels_response, epg_response, epg_response, epg_response]):
        site_id = telemach_epg.telemach_kanal_finden("BHT 1", "ba")
        assert site_id == "42"

        programme = telemach_epg.telemach_hole_programme(site_id, "ba", tage=3)

    # 3 Tage werden abgefragt, jeder Mock-Response liefert dieselbe eine
    # Sendung zurueck -> 3 Eintraege insgesamt.
    assert len(programme) == 3
    sendung = programme[0]
    assert sendung["title"] == "Dnevnik"
    assert sendung["beschreibung"] == "Vijesti dana"
    assert sendung["bild"] == "https://example.com/img.jpg"
    assert sendung["start"].tzinfo is not None
    assert sendung["stop"] > sendung["start"]


def test_telemach_login_fehlschlag_gibt_leere_liste_ohne_exception():
    """Schlaegt der Login fehl (z.B. Netzwerkfehler), duerfen
    telemach_hole_kanalliste()/telemach_hole_programme() NIE werfen,
    sondern muessen graceful auf leere Ergebnisse zurueckfallen -
    das ist die Grundlage fuer den generischen Fallback in
    generate_epg.py."""
    with patch("quellen.telemach_epg.requests.post", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert telemach_epg.telemach_login() is None
        assert telemach_epg.telemach_hole_kanalliste("ba") == []
        assert telemach_epg.telemach_kanal_finden("BHT 1", "ba") is None
        assert telemach_epg.telemach_hole_programme("42", "ba", tage=3) == []


def test_telemach_kein_kanal_treffer_gibt_none():
    """Kein passender Kanal in der Telemach-Liste -> None statt
    Exception oder falschem Treffer."""
    login_response = _mock_response({"access_token": "abc123"})
    channels_response = _mock_response([{"id": "1", "name": "Voellig anderer Sender"}])

    with patch("quellen.telemach_epg.requests.post", return_value=login_response), \
         patch("quellen.telemach_epg.requests.get", return_value=channels_response):
        assert telemach_epg.telemach_kanal_finden("Nicht Existierender Kanal XYZ", "ba") is None


# ==========================================================
# Mtel-EPG (zweite BA-only Quelle, Fallback nach Telemach,
# siehe mtel_epg.py)
# ==========================================================

@pytest.fixture(autouse=True)
def _mtel_cache_zuruecksetzen():
    mtel_epg._epg_tag_cache = {}
    mtel_epg._epg_tag_sperren = {}
    mtel_epg._kanalliste_cache = {}
    yield
    mtel_epg._kanalliste_cache = {}


def test_mtel_erfolgreicher_abruf_liefert_echte_sendungen():
    """Erfolgreicher Kanalsuche + Programmabruf muss echte Sendungen mit
    Titel/Zeiten liefern und den 'Nema informacija o programu'-
    Platzhalter ausfiltern (gemockte Netzwerkaufrufe)."""
    channels_response = _mock_response({
        "products": [
            {"code": "111", "name": "BHT 1"},
            {"code": "222", "name": "Sport Klub 1"},
        ]
    })
    epg_response = _mock_response({
        "products": [
            {
                "code": "111",
                "programs": [
                    {
                        "title": "Dnevnik",
                        "description": "Vijesti dana",
                        "picture": {"url": "https://example.com/img.jpg"},
                        "start": "2026-08-09 19:00",
                        "end": "2026-08-09 19:30",
                    },
                    {
                        "title": "Nema informacija o programu",
                        "description": "",
                        "picture": {},
                        "start": "2026-08-09 20:00",
                        "end": "2026-08-09 20:30",
                    },
                ],
            }
        ]
    })

    with patch("quellen.mtel_epg.requests.get", side_effect=[channels_response, epg_response, epg_response]):
        site_id = mtel_epg.mtel_kanal_finden("BHT 1")
        assert site_id == "iptv#111"

        programme = mtel_epg.mtel_hole_programme(site_id, tage=2)

    # 2 Tage abgefragt, jeder Mock liefert dieselbe eine echte Sendung
    # (der Platzhalter-Eintrag wird ausgefiltert) -> 2 Eintraege.
    assert len(programme) == 2
    sendung = programme[0]
    assert sendung["title"] == "Dnevnik"
    assert sendung["beschreibung"] == "Vijesti dana"
    assert sendung["bild"] == "https://example.com/img.jpg"
    assert sendung["start"].tzinfo is not None
    assert sendung["stop"] > sendung["start"]


def test_mtel_fehlschlag_gibt_leere_liste_ohne_exception():
    """Schlaegt der Netzwerkaufruf fehl, duerfen
    mtel_hole_kanalliste()/mtel_hole_programme() NIE werfen, sondern
    muessen graceful auf leere Ergebnisse zurueckfallen - das ist die
    Grundlage fuer den generischen Fallback in generate_epg.py, auch
    wenn schon Telemach fehlgeschlagen ist. mtel_kanal_finden() darf
    trotz Live-Fehlschlag ueber die statische Namenserweiterung
    (mtel_kanalliste.txt) noch einen Treffer liefern - der eigentliche
    Programmabruf faellt dann separat (s.u.) auf [] zurueck."""
    with patch("quellen.mtel_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert mtel_epg.mtel_hole_kanalliste() == []
        assert mtel_epg.mtel_kanal_finden("BHT 1") == "iptv#ch-15-bht"
        assert mtel_epg.mtel_hole_programme("iptv#111", tage=2) == []


def test_mtel_kein_kanal_treffer_gibt_none():
    """Kein passender Kanal in der Mtel-Liste -> None statt Exception
    oder falschem Treffer."""
    channels_response = _mock_response({"products": [{"code": "1", "name": "Voellig anderer Sender"}]})

    with patch("quellen.mtel_epg.requests.get", return_value=channels_response):
        assert mtel_epg.mtel_kanal_finden("Nicht Existierender Kanal XYZ") is None


def _telemach_dann_mtel_fallback(sender_name, telemach_country="ba"):
    """Repliziert exakt die Fallback-Kette aus generate_epg.py
    (telemach_sender-Verarbeitungsblock): Telemach zuerst, mtel.ba nur
    als zweiter Versuch fuer BA-Sender, wenn Telemach nichts liefert."""
    programme = []
    site_id = telemach_kanal_finden_wrapper = telemach_epg.telemach_kanal_finden(sender_name, telemach_country)
    if site_id is not None:
        programme = telemach_epg.telemach_hole_programme(site_id, telemach_country, 3)

    if not programme and telemach_country == "ba":
        mtel_site_id = mtel_epg.mtel_kanal_finden(sender_name)
        if mtel_site_id is not None:
            programme = mtel_epg.mtel_hole_programme(mtel_site_id, 2)

    return programme


def _requests_get_router(routen):
    """telemach_epg und mtel_epg teilen sich dasselbe `requests`-Modul-
    objekt (beide machen `import requests`) - ein einzelnes `patch` auf
    `requests.get` mit url-basiertem Routing haelt die Mocks fuer beide
    Quellen sauber getrennt, statt sich beim gleichzeitigen Patchen von
    "telemach_epg.requests.get" und "mtel_epg.requests.get" gegenseitig
    zu ueberschreiben (patchen denselben globalen Modul-Attribut)."""
    def _side_effect(url, *args, **kwargs):
        for teilstring, antworten in routen:
            if teilstring in url:
                return antworten.pop(0) if isinstance(antworten, list) else antworten
        raise AssertionError(f"Unerwarteter requests.get-Aufruf: {url}")
    return _side_effect


def test_mtel_fallback_greift_wenn_telemach_nichts_findet():
    """Telemach findet keinen Kanal-Treffer -> mtel.ba wird als zweiter
    Versuch probiert und liefert echte Sendungen."""
    telemach_login_response = _mock_response({"access_token": "abc123"})
    telemach_channels_response = _mock_response([{"id": "1", "name": "Voellig anderer Sender"}])
    mtel_channels_response = _mock_response({"products": [{"code": "111", "name": "BHT 1"}]})
    mtel_epg_response = _mock_response({
        "products": [{
            "code": "111",
            "programs": [{
                "title": "Dnevnik",
                "description": "Vijesti dana",
                "picture": {},
                "start": "2026-08-09 19:00",
                "end": "2026-08-09 19:30",
            }],
        }]
    })

    router = _requests_get_router([
        (telemach_epg.CHANNELS_URL, telemach_channels_response),
        (mtel_epg.CHANNELS_URL, mtel_channels_response),
        (mtel_epg.EPG_URL, [mtel_epg_response, mtel_epg_response]),
    ])

    with patch("quellen.telemach_epg.requests.post", return_value=telemach_login_response), \
         patch("quellen.telemach_epg.requests.get", side_effect=router):
        programme = _telemach_dann_mtel_fallback("BHT 1")

    assert len(programme) == 2
    assert programme[0]["title"] == "Dnevnik"


def test_mtel_fallback_auch_fehlschlag_faellt_auf_generisch_zurueck():
    """Telemach findet nichts UND mtel.ba schlaegt ebenfalls fehl ->
    leere Programmliste ohne Exception (generische EPG uebernimmt)."""
    telemach_login_response = _mock_response({"access_token": "abc123"})
    telemach_channels_response = _mock_response([{"id": "1", "name": "Voellig anderer Sender"}])

    def _side_effect(url, *args, **kwargs):
        if telemach_epg.CHANNELS_URL in url:
            return telemach_channels_response
        raise Exception("Netzwerk nicht erreichbar")

    with patch("quellen.telemach_epg.requests.post", return_value=telemach_login_response), \
         patch("quellen.telemach_epg.requests.get", side_effect=_side_effect):
        programme = _telemach_dann_mtel_fallback("BHT 1")

    assert programme == []


def test_mtel_wird_nicht_aufgerufen_wenn_telemach_erfolgreich_ist():
    """Findet Telemach echte Programmdaten, darf mtel.ba fuer diesen
    Sender ueberhaupt nicht kontaktiert werden."""
    telemach_login_response = _mock_response({"access_token": "abc123"})
    telemach_channels_response = _mock_response([{"id": "42", "name": "BHT 1"}])
    telemach_epg_response = _mock_response({
        "42": [{
            "title": "Dnevnik",
            "shortDescription": "Vijesti dana",
            "images": [],
            "startTime": "2026-08-09T19:00:00+00:00",
            "endTime": "2026-08-09T19:30:00+00:00",
        }]
    })

    mtel_call_count = {"n": 0}

    def _side_effect(url, *args, **kwargs):
        if telemach_epg.CHANNELS_URL in url:
            return telemach_channels_response
        if telemach_epg.EPG_URL in url:
            return telemach_epg_response
        mtel_call_count["n"] += 1
        raise AssertionError("mtel.ba haette nicht kontaktiert werden duerfen")

    with patch("quellen.telemach_epg.requests.post", return_value=telemach_login_response), \
         patch("quellen.telemach_epg.requests.get", side_effect=_side_effect):
        programme = _telemach_dann_mtel_fallback("BHT 1")

    assert len(programme) == 3
    assert mtel_call_count["n"] == 0


# ==========================================================
# Sky-EPG (opt-in SKY:-Sender, DE-only, siehe sky_epg.py)
# ==========================================================

@pytest.fixture(autouse=True)
def _sky_cache_zuruecksetzen():
    sky_epg._kanalliste_cache = {}
    yield
    sky_epg._kanalliste_cache = {}


def test_sky_erfolgreicher_abruf_liefert_echte_sendungen():
    """Erfolgreiche Kanalsuche + Programmabruf muss echte Sendungen mit
    Titel/Zeiten liefern (gemockte Netzwerkaufrufe)."""
    regions_response = _mock_response({"regions": [{"bouquetId": 1, "subBouquetId": 1}]})
    services_response = _mock_response({
        "services": [
            {"sid": "1001", "t": "Sky Sport Bundesliga 1", "schedule": True},
            {"sid": "1002", "t": "Sky Sport News", "schedule": True},
        ]
    })
    def _schedule_response(eid):
        return _mock_response({
            "schedule": [
                {
                    "sid": "1001",
                    "events": [
                        {
                            "eid": eid,
                            "st": 1786384800,
                            "d": 1800,
                            "t": "Bundesliga Highlights",
                            "sy": "Zusammenfassung des Spieltags",
                            "programmeuuid": "abc-123",
                        }
                    ],
                }
            ]
        })

    with patch(
        "quellen.sky_epg.requests.get",
        side_effect=[regions_response, services_response, _schedule_response(555), _schedule_response(556)],
    ):
        site_id = sky_epg.sky_kanal_finden("Sky Sport Bundesliga 1", "DE")
        assert site_id == "1001"

        programme = sky_epg.sky_hole_programme(site_id, "DE", tage=2)

    assert len(programme) == 2
    sendung = programme[0]
    assert sendung["title"] == "Bundesliga Highlights"
    assert sendung["beschreibung"] == "Zusammenfassung des Spieltags"
    assert sendung["bild"] == "https://images.metadata.sky.com/pd-image/abc-123/16-9/640"
    assert sendung["start"].tzinfo is not None
    assert sendung["stop"] > sendung["start"]


def test_sky_kein_kanal_treffer_oder_fehlschlag_faellt_graceful_zurueck():
    """Kein Kanal-Treffer bzw. ein Netzwerkfehler duerfen NIE eine
    Exception werfen, sondern muessen graceful auf None/[]
    zurueckfallen - Grundlage fuer den generischen Fallback in
    generate_epg.py."""
    regions_response = _mock_response({"regions": [{"bouquetId": 1, "subBouquetId": 1}]})
    services_response = _mock_response({
        "services": [{"sid": "1001", "t": "Sky Sport Bundesliga 1", "schedule": True}]
    })

    with patch("quellen.sky_epg.requests.get", side_effect=[regions_response, services_response]):
        assert sky_epg.sky_kanal_finden("Nicht Existierender Kanal XYZ", "DE") is None

    sky_epg._kanalliste_cache = {}

    with patch("quellen.sky_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert sky_epg.sky_hole_kanalliste("DE") == []
        assert sky_epg.sky_kanal_finden("Sky Sport Bundesliga 1", "DE") is None
        assert sky_epg.sky_hole_programme("1001", "DE", tage=2) == []


def test_sky_ohne_sky_zeilen_werden_keine_requests_ausgeloest():
    """sender.txt ganz ohne SKY:-Zeilen darf sky_epg's Request-Funktionen
    ueberhaupt nicht kontaktieren (Zero-Risk-Garantie, analog zum
    TELEMACH:/mtel-Guard in generate_epg.py: `sky_sender = [d for d in
    sender_daten if d.get("sky")]` bleibt leer, die for-Schleife darueber
    laeuft dann nie)."""
    sky_sender_leer = []

    with patch("quellen.sky_epg.requests.get", side_effect=AssertionError("sky_epg haette nicht kontaktiert werden duerfen")):
        for daten in sky_sender_leer:
            sky_epg.sky_kanal_finden(daten["sender"], "DE")

    # Kein Aufruf erfolgt -> kein Fehler ausgeloest, Liste bleibt leer.
    assert sky_sender_leer == []


def test_sky_gb_territory_wird_unterstuetzt_und_nicht_auf_de_zurueckgesetzt():
    """Seit der GB-Erweiterung darf "GB" NICHT mehr still auf "DE"
    zurueckfallen (im Unterschied zu jedem anderen/unbekannten Wert, der
    weiterhin auf "DE" faellt) - der Territory-Header muss "GB" sein."""
    regions_response = _mock_response({"regions": [{"bouquetId": 2, "subBouquetId": 2}]})
    services_response = _mock_response({
        "services": [{"sid": "2001", "t": "Sky Showcase", "schedule": True}]
    })

    aufgerufene_header = []

    def _get(url, headers=None, timeout=None):
        aufgerufene_header.append(headers.get("X-SkyOTT-Territory"))
        if "regions" in url:
            return regions_response
        return services_response

    with patch("quellen.sky_epg.requests.get", side_effect=_get):
        site_id = sky_epg.sky_kanal_finden("Sky Showcase", "GB")

    assert site_id == "2001"
    assert all(h == "GB" for h in aufgerufene_header)
    assert sky_epg._territory_normalisieren("unbekannt") == "DE"
    assert sky_epg._territory_normalisieren("GB") == "GB"


# ==========================================================
# Arena-EPG (opt-in ARENA:-Sender, HR/RS, siehe arena_epg.py)
# ==========================================================

def _mock_html_response(html_text, status_ok=True):
    response = MagicMock()
    response.text = html_text
    if status_ok:
        response.raise_for_status.return_value = None
    else:
        response.raise_for_status.side_effect = Exception("HTTP-Fehler")
    return response


@pytest.fixture(autouse=True)
def _arena_cache_zuruecksetzen():
    arena_epg._kanalliste_cache = {}
    arena_epg._seite_cache = {}
    arena_epg._rs_schema_cache = None
    yield
    arena_epg._kanalliste_cache = {}
    arena_epg._seite_cache = {}
    arena_epg._rs_schema_cache = None


def _hr_tage_labels():
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/Budapest")
    heute = datetime.datetime.now(tz).date()
    morgen = heute + datetime.timedelta(days=1)
    return heute.strftime("%d.%m."), morgen.strftime("%d.%m.")


def _rs_tage_labels():
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/Belgrade")
    heute = datetime.datetime.now(tz).date()
    morgen = heute + datetime.timedelta(days=1)
    return heute.strftime("%d.%m."), morgen.strftime("%d.%m.")


def _rs_tage_iso():
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/Belgrade")
    heute = datetime.datetime.now(tz).date()
    morgen = heute + datetime.timedelta(days=1)
    return heute.strftime("%Y-%m-%d"), morgen.strftime("%Y-%m-%d")


def _hr_fixture_html():
    tag1, tag2 = _hr_tage_labels()
    return f"""
    <html><body>
    <div class="tv-scheme-chanel">
      <div class="tv-scheme-chanel-header"><img src="https://x/chanel-1.png"></div>
      <div class="tv-scheme-days">
        <a><span></span><span></span><span>{tag1}</span></a>
        <a><span></span><span></span><span>{tag2}</span></a>
      </div>
      <div class="tv-scheme-new-slider-wrapper">
        <div class="tv-scheme-new-slider-item">
          <div class="slider-content">
            <div class="slider-content-top"><span>20:00</span></div>
            <div class="slider-content-middle"><span>Football</span></div>
            <div class="slider-content-bottom"><p>Match A</p><span>Description A</span></div>
          </div>
          <div class="slider-content">
            <div class="slider-content-top"><span>22:00</span></div>
            <div class="slider-content-middle"><span>Football</span></div>
            <div class="slider-content-bottom"><p>Match B</p></div>
          </div>
        </div>
        <div class="tv-scheme-new-slider-item">
          <div class="slider-content">
            <div class="slider-content-top"><span>09:00</span></div>
            <div class="slider-content-middle"><span>News</span></div>
            <div class="slider-content-bottom"><p>Morning News</p></div>
          </div>
        </div>
      </div>
    </div>
    </body></html>
    """


def _rs_fixture_html():
    # Seit dem Website-Redesign (September 2026, siehe CLAUDE.md/
    # arena_epg.py) laedt tvarenasport.com die Sendungen per JavaScript
    # nach - das rohe HTML enthaelt nur noch einen leeren Platzhalter-Div
    # mit "data-channel-index", die eigentlichen Daten stecken in einem
    # "window.TV_SCHEMES = {...};"-Inline-Script.
    tag1_iso, tag2_iso = _rs_tage_iso()
    return f"""
    <html><body>
    <div class="tv-scheme-chanel">
      <div class="tv-scheme-chanel-header"><img src="https://x/chanel-1.png"></div>
      <div class="tv-day-shell" data-channel-index="Arena Sport 1 Test" data-day-key="{tag1_iso}"></div>
    </div>
    <script>
      window.TV_SCHEMES = {{"Arena Sport 1 Test": {{"days": {{
        "{tag1_iso}": {{"emisije": [
          {{"content": "Match A", "time": "20:00", "category": "Liga A", "description": "snimak"}},
          {{"content": "Match B", "time": "22:00", "category": "Liga B", "description": "uzivo"}}
        ]}},
        "{tag2_iso}": {{"emisije": [
          {{"content": "Morning Show", "time": "09:00", "category": "", "description": "snimak"}}
        ]}}
      }}}}}};
    </script>
    </body></html>
    """


def test_arena_hr_erfolgreicher_abruf_liefert_echte_sendungen():
    """Erfolgreiche Kanalsuche + Programmabruf (HR/tvarenasport.hr) muss
    echte Sendungen mit Titel/Zeiten liefern. Der kurze Spielname bleibt
    Titel, der laengere Fliesstext wird zur Beschreibung (kein Tausch
    mehr - siehe CLAUDE.md/arena_epg.py)."""
    html_response = _mock_html_response(_hr_fixture_html())

    with patch("quellen.arena_epg.requests.get", return_value=html_response):
        site_id = arena_epg.arena_kanal_finden("Arena Sport 1", "HR")
        assert site_id == "1"

        programme = arena_epg.arena_hole_programme(site_id, "HR", tage=2)

    assert len(programme) >= 1
    erste = programme[0]
    assert erste["title"] == "Match A"
    assert erste["beschreibung"] == "Description A"
    assert erste["start"].tzinfo is not None
    assert erste["stop"] > erste["start"]


def test_arena_rs_erfolgreicher_abruf_liefert_echte_sendungen():
    """Erfolgreiche Kanalsuche + Programmabruf (RS/tvarenasport.com) muss
    echte Sendungen mit Titel inkl. Liga-Praefix und Live-Markierung
    liefern."""
    html_response = _mock_html_response(_rs_fixture_html())

    with patch("quellen.arena_epg.requests.get", return_value=html_response):
        site_id = arena_epg.arena_kanal_finden("Arena Sport 1 Serbia", "RS")
        assert site_id == "1"

        programme = arena_epg.arena_hole_programme(site_id, "RS", tage=2)

    assert len(programme) >= 2
    titel = [p["title"] for p in programme]
    assert "Liga A: Match A" in titel
    assert any(t.startswith("(Uživo) ") and "Liga B: Match B" in t for t in titel)


def test_arena_kein_kanal_treffer_oder_fehlschlag_faellt_graceful_zurueck():
    """Kein Kanal-Treffer bzw. ein Netzwerk-/Parse-Fehler duerfen NIE eine
    Exception werfen, sondern muessen graceful auf None/[] zurueckfallen -
    Grundlage fuer den generischen Fallback in generate_epg.py."""
    html_response = _mock_html_response(_hr_fixture_html())

    with patch("quellen.arena_epg.requests.get", return_value=html_response):
        assert arena_epg.arena_kanal_finden("Nicht Existierender Kanal XYZ", "HR") is None

    arena_epg._kanalliste_cache = {}
    arena_epg._seite_cache = {}

    with patch("quellen.arena_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert arena_epg.arena_hole_kanalliste("HR") == []
        assert arena_epg.arena_kanal_finden("Arena Sport 1", "HR") is None
        assert arena_epg.arena_hole_programme("1", "HR", tage=2) == []


def test_arena_ohne_arena_zeilen_werden_keine_requests_ausgeloest():
    """sender.txt ganz ohne ARENA:-Zeilen darf arena_epg's Request-
    Funktionen ueberhaupt nicht kontaktieren (Zero-Risk-Garantie, analog
    zum SKY:-Guard in generate_epg.py: `arena_sender = [d for d in
    sender_daten if d.get("arena")]` bleibt leer, die for-Schleife
    darueber laeuft dann nie)."""
    arena_sender_leer = []

    with patch("quellen.arena_epg.requests.get", side_effect=AssertionError("arena_epg haette nicht kontaktiert werden duerfen")):
        for daten in arena_sender_leer:
            arena_epg.arena_kanal_finden(daten["sender"], "HR")

    # Kein Aufruf erfolgt -> kein Fehler ausgeloest, Liste bleibt leer.
    assert arena_sender_leer == []



# ==========================================================
# Magenta-EPG (opt-in MAGENTA:-Sender, DE-only, zwei verkettete Quellen,
# siehe magenta_epg.py)
# ==========================================================

@pytest.fixture(autouse=True)
def _magenta_cache_zuruecksetzen():
    magenta_epg._kanalliste_cache = None
    magenta_epg._kanalliste_quelle = None
    magenta_epg._alt_auth_cache = None
    yield
    magenta_epg._kanalliste_cache = None
    magenta_epg._kanalliste_quelle = None
    magenta_epg._alt_auth_cache = None


def _magenta_requests_get_router(routen):
    def _side_effect(url, *args, **kwargs):
        for teilstring, antworten in routen:
            if teilstring in url:
                return antworten.pop(0) if isinstance(antworten, list) else antworten
        raise AssertionError(f"Unerwarteter requests.get-Aufruf: {url}")
    return _side_effect


def test_magenta_neu_erfolgreicher_abruf_liefert_echte_sendungen():
    """Neuere www.magenta.tv-API liefert Kanalliste + Programmdaten ->
    keine alte API kontaktiert."""
    stations_response = _mock_response({
        "entries": [
            {
                "id": "http://data.entertainment.tv.theplatform.eu/entertainment/data/Station/12345",
                "stations": {"x": {"title": "RTL"}},
                "dt$isRadio": False,
            }
        ]
    })
    schedule_response = _mock_response({
        "entries": [
            {
                "id": "http://data.entertainment.tv.theplatform.eu/entertainment/data/Schedule/12345",
                "listings": [
                    {
                        "program": {"title": "Wetter", "description": "Die Vorhersage"},
                        "startTime": 1786384800000,
                        "endTime": 1786386600000,
                    }
                ],
            }
        ]
    })

    router = _magenta_requests_get_router([
        (magenta_epg.MPX_ALL_CHANNEL_STATIONS_FEED, [stations_response]),
        (magenta_epg.MPX_ALL_CHANNEL_SCHEDULES_FEED, [schedule_response, schedule_response]),
    ])

    with patch("quellen.magenta_epg.requests.get", side_effect=router), \
         patch("quellen.magenta_epg.requests.post", side_effect=AssertionError("alte API haette nicht kontaktiert werden duerfen")):
        kanal_ref = magenta_epg.magenta_kanal_finden("RTL")
        assert kanal_ref == {"quelle": "neu", "site_id": "12345"}

        programme = magenta_epg.magenta_hole_programme(kanal_ref, tage=2)

    assert len(programme) == 2
    sendung = programme[0]
    assert sendung["title"] == "Wetter"
    assert sendung["beschreibung"] == "Die Vorhersage"
    assert sendung["start"].tzinfo is not None
    assert sendung["stop"] > sendung["start"]


def test_magenta_neu_fehlschlaegt_faellt_auf_alt_zurueck():
    """Neuere API liefert keine Kanalliste (Netzwerkfehler) -> aeltere
    web.magentatv.de-API wird als zweiter Versuch erfolgreich probiert."""
    auth_response = _mock_response({"csrfToken": "tok123"})
    auth_response.headers = {"Set-Cookie": "JSESSIONID=abc; Path=/, CSESSIONID=def; Path=/"}
    channels_response = _mock_response({"channellist": [{"contentId": "999", "name": "RTL"}]})
    epg_response = _mock_response({
        "playbilllist": [{
            "name": "Wetter",
            "introduce": "Die Vorhersage",
            "starttime": "2026-08-09 19:00:00",
            "endtime": "2026-08-09 19:30:00",
        }]
    })

    def _get_side_effect(url, *args, **kwargs):
        raise Exception("Netzwerk nicht erreichbar")

    def _post_side_effect(url, *args, **kwargs):
        if magenta_epg.MAGENTA_ALT_AUTH_URL in url:
            return auth_response
        if magenta_epg.MAGENTA_ALT_CHANNELS_URL in url:
            return channels_response
        if magenta_epg.MAGENTA_ALT_EPG_URL in url:
            return epg_response
        raise AssertionError(f"Unerwarteter requests.post-Aufruf: {url}")

    with patch("quellen.magenta_epg.requests.get", side_effect=_get_side_effect), \
         patch("quellen.magenta_epg.requests.post", side_effect=_post_side_effect):
        kanal_ref = magenta_epg.magenta_kanal_finden("RTL")
        assert kanal_ref == {"quelle": "alt", "site_id": "999"}

        programme = magenta_epg.magenta_hole_programme(kanal_ref, tage=2)

    assert len(programme) == 2
    assert programme[0]["title"] == "Wetter"
    assert programme[0]["beschreibung"] == "Die Vorhersage"
    assert programme[0]["start"].tzinfo is not None


def test_magenta_beide_quellen_fehlschlagen_gibt_leere_liste_ohne_exception():
    """Neuere UND aeltere API schlagen fehl -> kein Kanal-Treffer, keine
    Exception (generische EPG uebernimmt)."""
    with patch("quellen.magenta_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")), \
         patch("quellen.magenta_epg.requests.post", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert magenta_epg.magenta_hole_kanalliste() == []
        assert magenta_epg.magenta_kanal_finden("RTL") is None


def test_magenta_ohne_magenta_zeilen_werden_keine_requests_ausgeloest():
    """sender.txt ganz ohne MAGENTA:-Zeilen darf magenta_epg's Request-
    Funktionen ueberhaupt nicht kontaktieren (Zero-Risk-Garantie, analog
    zum SKY:-Guard in generate_epg.py: `magenta_sender = [d for d in
    sender_daten if d.get("magenta")]` bleibt leer, die for-Schleife
    darueber laeuft dann nie)."""
    magenta_sender_leer = []

    with patch("quellen.magenta_epg.requests.get", side_effect=AssertionError("magenta_epg haette nicht kontaktiert werden duerfen")), \
         patch("quellen.magenta_epg.requests.post", side_effect=AssertionError("magenta_epg haette nicht kontaktiert werden duerfen")):
        for daten in magenta_sender_leer:
            magenta_epg.magenta_kanal_finden(daten["sender"])

    assert magenta_sender_leer == []


# ==========================================================
# DAZN-EPG (opt-in DAZN:-Sender, beliebiges Land, siehe dazn_epg.py)
# ==========================================================

@pytest.fixture(autouse=True)
def _dazn_cache_zuruecksetzen():
    dazn_epg._raw_cache = {}
    yield
    dazn_epg._raw_cache = {}


def _dazn_rail_response():
    return _mock_response({
        "Tiles": [
            {
                "AssetId": "dazn1",
                "Title": "DAZN 1 HD",
                "LinearSchedule": {
                    "Now": {
                        "Title": "Bundesliga Live",
                        "Description": "1. FC Koeln - Bayern Muenchen",
                        "Start": "2026-08-09T18:00:00Z",
                        "End": "2026-08-09T20:00:00Z",
                    },
                    "Next": {
                        "Title": "Analyse",
                        "Start": "2026-08-09T20:00:00Z",
                        "End": "2026-08-09T21:00:00Z",
                    },
                    "Later": [],
                },
            },
            {"AssetId": "dazn2", "Title": "DAZN 2 HD"},
        ]
    })


def test_dazn_erfolgreicher_abruf_liefert_echte_sendungen():
    """Erfolgreiche Kanalsuche + Programmabruf muss echte Sendungen mit
    Titel/Zeiten liefern (gemockter Netzwerkaufruf) - nur EIN Request pro
    Land, da _rail_holen() pro Land cached."""
    with patch("quellen.dazn_epg.requests.get", side_effect=[_dazn_rail_response()]):
        site_id = dazn_epg.dazn_kanal_finden("DAZN 1 HD", "de")
        assert site_id == "dazn1"

        programme = dazn_epg.dazn_hole_programme(site_id, "de", tage=3)

    assert len(programme) == 2
    sendung = programme[0]
    assert sendung["title"] == "Bundesliga Live"
    assert sendung["beschreibung"] == "1. FC Koeln - Bayern Muenchen"
    assert sendung["bild"] is None
    assert sendung["start"].tzinfo is not None
    assert sendung["stop"] > sendung["start"]


def test_dazn_kanal_id_verwendet_land_pipe_name_format():
    """Regressionstest fuer den kuerzlich gefixten Bug: 'kanal' (die
    <channel>-id/display-name in der XML) muss im selben 'LAND| Name'-
    Format wie normale sender.txt-Zeilen gebaut werden (z.B. 'DE| RTL'),
    NICHT als bloßer Kanalname - sonst bricht TiviMates automatisches
    EPG-zu-Playlist-Channel-Matching. Repliziert exakt die Formel aus dem
    DAZN:-Parsing-Block in generate_epg.py."""
    dazn_land = "de"
    dazn_kanalname = "DAZN 1 HD"
    kanal = f"{dazn_land.upper()}| {dazn_kanalname}"
    assert kanal == "DE| DAZN 1 HD"
    assert kanal != dazn_kanalname


def test_dazn_kein_kanal_treffer_oder_fehlschlag_faellt_graceful_zurueck():
    """Kein Kanal-Treffer bzw. ein Netzwerkfehler duerfen NIE eine
    Exception werfen, sondern muessen graceful auf None/[]
    zurueckfallen - Grundlage fuer den generischen Fallback in
    generate_epg.py."""
    with patch("quellen.dazn_epg.requests.get", side_effect=[_dazn_rail_response()]):
        assert dazn_epg.dazn_kanal_finden("Nicht Existierender Kanal XYZ", "de") is None

    dazn_epg._raw_cache = {}

    with patch("quellen.dazn_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert dazn_epg.dazn_hole_kanalliste("de") == []
        assert dazn_epg.dazn_kanal_finden("DAZN 1 HD", "de") is None
        assert dazn_epg.dazn_hole_programme("dazn1", "de", tage=3) == []


def test_dazn_ohne_dazn_zeilen_werden_keine_requests_ausgeloest():
    """sender.txt ganz ohne DAZN:-Zeilen darf dazn_epg's Request-
    Funktionen ueberhaupt nicht kontaktieren (Zero-Risk-Garantie, analog
    zum SKY:-Guard in generate_epg.py: `dazn_sender = [d for d in
    sender_daten if d.get("dazn")]` bleibt leer, die for-Schleife
    darueber laeuft dann nie)."""
    dazn_sender_leer = []

    with patch("quellen.dazn_epg.requests.get", side_effect=AssertionError("dazn_epg haette nicht kontaktiert werden duerfen")):
        for daten in dazn_sender_leer:
            dazn_epg.dazn_kanal_finden(daten["sender"], "de")

    assert dazn_sender_leer == []


# ==========================================================
# FREEVIEW-EPG (opt-in FREEVIEW:-Sender, nur GB, siehe freeview_epg.py)
# ==========================================================

@pytest.fixture(autouse=True)
def _freeview_cache_zuruecksetzen():
    freeview_epg._raw_cache = {}
    yield
    freeview_epg._raw_cache = {}


def _freeview_guide_response():
    return _mock_response({
        "data": {
            "programs": [
                {
                    "service_id": "bbc1",
                    "title": "BBC One",
                    "events": [
                        {
                            "main_title": "News",
                            "secondary_title": None,
                            "start_time": "2026-08-09T18:00:00Z",
                            "duration": "01:00:00",
                            "image_url": "https://example.com/img.jpg",
                        },
                        {
                            "main_title": "Drama",
                            "secondary_title": "Episode 1",
                            "start_time": "2026-08-09T19:00:00Z",
                            "duration": 1800,
                        },
                    ],
                },
                {"service_id": "itv1", "title": "ITV1", "events": []},
            ]
        }
    })


def test_freeview_erfolgreicher_abruf_liefert_echte_sendungen():
    """Erfolgreiche Kanalsuche + Programmabruf muss echte Sendungen mit
    Titel/Zeiten liefern (gemockter Netzwerkaufruf) - EIN Request pro Tag
    (kanal_finden und Tag 0 des Programmabrufs teilen sich den Cache)."""
    with patch(
        "quellen.freeview_epg.requests.get",
        side_effect=[_freeview_guide_response(), _freeview_guide_response()],
    ):
        site_id = freeview_epg.freeview_kanal_finden("BBC One")
        assert site_id == "64257#bbc1"

        programme = freeview_epg.freeview_hole_programme(site_id, tage=2)

    assert len(programme) == 2
    sendung = programme[0]
    assert sendung["title"] == "News"
    assert sendung["beschreibung"] is None
    assert sendung["bild"] == "https://example.com/img.jpg"
    assert sendung["start"].tzinfo is not None
    assert sendung["stop"] > sendung["start"]
    assert programme[1]["title"] == "Drama (Episode 1)"


def test_freeview_kanal_id_verwendet_land_pipe_name_format():
    """Regressionstest fuer den kanal-id-Bug: 'kanal' (die <channel>-id/
    display-name in der XML) muss im 'LAND| Name'-Format gebaut werden,
    NICHT als bloßer Kanalname - repliziert exakt die Formel aus dem
    FREEVIEW:-Parsing-Block in generate_epg.py. Anzeige-Land ist bewusst
    "UK" (nicht "GB"), damit es zur "UK|..."-Konvention der eigenen
    IPTV-Playlist des Nutzers passt und TiviMate automatisch zuordnet."""
    freeview_anzeige_land = "UK"
    freeview_kanalname = "BBC One"
    kanal = f"{freeview_anzeige_land}| {freeview_kanalname}"
    assert kanal == "UK| BBC One"
    assert kanal != freeview_kanalname


def test_freeview_kein_kanal_treffer_oder_fehlschlag_faellt_graceful_zurueck():
    """Kein Kanal-Treffer bzw. ein Netzwerkfehler duerfen NIE eine
    Exception werfen, sondern muessen graceful auf None/[]
    zurueckfallen."""
    with patch("quellen.freeview_epg.requests.get", side_effect=[_freeview_guide_response()]):
        assert freeview_epg.freeview_kanal_finden("Nicht Existierender Kanal XYZ") is None

    freeview_epg._raw_cache = {}

    with patch("quellen.freeview_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert freeview_epg.freeview_hole_kanalliste() == []
        assert freeview_epg.freeview_kanal_finden("BBC One") is None
        assert freeview_epg.freeview_hole_programme("64257#bbc1", tage=2) == []


def test_freeview_ohne_freeview_zeilen_werden_keine_requests_ausgeloest():
    """sender.txt ganz ohne FREEVIEW:-Zeilen darf freeview_epg's Request-
    Funktionen ueberhaupt nicht kontaktieren (Zero-Risk-Garantie, analog
    zum SKY:/DAZN:-Guard in generate_epg.py)."""
    freeview_sender_leer = []

    with patch("quellen.freeview_epg.requests.get", side_effect=AssertionError("freeview_epg haette nicht kontaktiert werden duerfen")):
        for daten in freeview_sender_leer:
            freeview_epg.freeview_kanal_finden(daten["sender"])

    assert freeview_sender_leer == []


# ==========================================================
# TVGUIDE-EPG (opt-in TVGUIDE:-Sender, nur US, siehe tvguide_epg.py)
# ==========================================================

@pytest.fixture(autouse=True)
def _tvguide_cache_zuruecksetzen():
    tvguide_epg._segment_cache = {}
    yield
    tvguide_epg._segment_cache = {}


def _tvguide_channels_response():
    return _mock_response({
        "data": {
            "items": [
                {"sourceId": "111", "fullName": "CBS Channel Schedule"},
                {"sourceId": "222", "fullName": "NBC"},
            ]
        }
    })


def _tvguide_segment_response(mit_daten=True):
    if not mit_daten:
        return _mock_response({"data": {"items": []}})
    return _mock_response({
        "data": {
            "items": [
                {
                    "channel": {"sourceId": 111},
                    "programSchedules": [
                        {
                            "title": "Evening News",
                            "startTime": 1786377600,
                            "endTime": 1786381200,
                        }
                    ],
                },
                {"channel": {"sourceId": 222}, "programSchedules": []},
            ]
        }
    })


def test_tvguide_erfolgreicher_abruf_liefert_echte_sendungen():
    """Erfolgreiche Kanalsuche + Programmabruf muss echte Sendungen mit
    Titel/Zeiten liefern (gemockter Netzwerkaufruf) - 1 Request fuer die
    Kanalliste + 6 Segment-Requests pro Tag."""
    responses = [_tvguide_channels_response()] + [
        _tvguide_segment_response() for _ in range(12)
    ]
    with patch("quellen.tvguide_epg.requests.get", side_effect=responses):
        site_id = tvguide_epg.tvguide_kanal_finden("CBS")
        assert site_id == "111"

        programme = tvguide_epg.tvguide_hole_programme(site_id, tage=2)

    assert len(programme) == 1
    sendung = programme[0]
    assert sendung["title"] == "Evening News"
    assert sendung["beschreibung"] is None
    assert sendung["bild"] is None
    assert sendung["start"].tzinfo is not None
    assert sendung["stop"] > sendung["start"]


def test_tvguide_kanal_id_verwendet_land_pipe_name_format():
    """Regressionstest fuer den kanal-id-Bug: 'kanal' (die <channel>-id/
    display-name in der XML) muss im 'LAND| Name'-Format gebaut werden
    (z.B. 'US| CBS'), NICHT als bloßer Kanalname - repliziert exakt die
    Formel aus dem TVGUIDE:-Parsing-Block in generate_epg.py."""
    tvguide_land = "US"
    tvguide_kanalname = "CBS"
    kanal = f"{tvguide_land}| {tvguide_kanalname}"
    assert kanal == "US| CBS"
    assert kanal != tvguide_kanalname


def test_tvguide_kein_kanal_treffer_oder_fehlschlag_faellt_graceful_zurueck():
    """Kein Kanal-Treffer bzw. ein Netzwerkfehler duerfen NIE eine
    Exception werfen, sondern muessen graceful auf None/[]
    zurueckfallen."""
    with patch("quellen.tvguide_epg.requests.get", side_effect=[_tvguide_channels_response()]):
        assert tvguide_epg.tvguide_kanal_finden("Nicht Existierender Kanal XYZ") is None

    with patch("quellen.tvguide_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert tvguide_epg.tvguide_hole_kanalliste() == []
        assert tvguide_epg.tvguide_kanal_finden("CBS") is None
        assert tvguide_epg.tvguide_hole_programme("111", tage=2) == []


def test_tvguide_ohne_tvguide_zeilen_werden_keine_requests_ausgeloest():
    """sender.txt ganz ohne TVGUIDE:-Zeilen darf tvguide_epg's Request-
    Funktionen ueberhaupt nicht kontaktieren (Zero-Risk-Garantie, analog
    zum SKY:/DAZN:-Guard in generate_epg.py)."""
    tvguide_sender_leer = []

    with patch("quellen.tvguide_epg.requests.get", side_effect=AssertionError("tvguide_epg haette nicht kontaktiert werden duerfen")):
        for daten in tvguide_sender_leer:
            tvguide_epg.tvguide_kanal_finden(daten["sender"])

    assert tvguide_sender_leer == []



# ==========================================================
# Mts-EPG (automatischer Abgleich fuer RS-Sender, siehe mts_epg.py)
# ==========================================================

@pytest.fixture(autouse=False)
def _mts_cache_zuruecksetzen():
    mts_epg._tages_cache = {}
    yield
    mts_epg._tages_cache = {}


def _mts_tagesdaten_response():
    return _mock_response({
        "products": [
            {
                "code": "1",
                "name": "RTS 1",
                "programs": [
                    {
                        "title": "Dnevnik",
                        "description": "Vesti",
                        "picture": {"url": "http://example.com/p.jpg"},
                        "start": "2026-08-10T19:30:00",
                        "end": "2026-08-10T20:00:00",
                    }
                ],
            }
        ]
    })


def test_mts_erfolgreicher_abruf_liefert_echte_sendungen(_mts_cache_zuruecksetzen):
    with patch("quellen.mts_epg.requests.get", return_value=_mts_tagesdaten_response()):
        site_id = mts_epg.mts_kanal_finden("RTS 1")
        assert site_id is not None

        programme = mts_epg.mts_hole_programme(site_id, tage=2)

    # tage=2 -> 2 Tagesabrufe, das Mock liefert fuer jeden Tag dieselbe
    # eine Sendung zurueck.
    assert len(programme) == 2
    sendung = programme[0]
    assert sendung["title"] == "Dnevnik"
    assert sendung["beschreibung"] == "Vesti"
    assert sendung["start"].tzinfo is not None
    assert sendung["stop"] > sendung["start"]


def test_mts_arena_sport_wird_komplett_uebersprungen(_mts_cache_zuruecksetzen):
    """mts.rs fuehrt zwar einen eigenen 'Arena Sport N'/'Arena PREMIUM N'-
    Kanal, dessen Sendezeiten live nachweislich falsch sind (ca. 4h
    Versatz, siehe _ARENA_SPORT_GUARD in mts_epg.py) - jeder Name, der
    mit 'ARENA SPORT' beginnt, wird deshalb komplett uebersprungen
    (None), unabhaengig davon, ob mts.rs selbst einen (aehnlich
    benannten) Kanal dafuer haette. arena_epg.py (tvarenasport.com)
    uebernimmt stattdessen als Fallback in generate_epg.py."""
    response = _mock_response({
        "products": [
            {"code": "as1", "name": "Arena Sport 1", "programs": []},
            {"code": "p1", "name": "Arena PREMIUM 1", "programs": []},
        ]
    })
    with patch("quellen.mts_epg.requests.get", return_value=response):
        assert mts_epg.mts_kanal_finden("ARENA SPORT 1") is None
        assert mts_epg.mts_kanal_finden("ARENA SPORT 1 HD") is None
        assert mts_epg.mts_kanal_finden("ARENA SPORT 1 PREMIUM") is None
        assert mts_epg.mts_kanal_finden("ARENA SPORT 1 PREMIUM HD") is None


def test_mts_kein_kanal_treffer_oder_fehlschlag_faellt_graceful_zurueck(_mts_cache_zuruecksetzen):
    with patch("quellen.mts_epg.requests.get", return_value=_mts_tagesdaten_response()):
        assert mts_epg.mts_kanal_finden("Nicht Existierender Kanal XYZ") is None

    mts_epg._tages_cache = {}
    with patch("quellen.mts_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert mts_epg.mts_hole_kanalliste() == []
        assert mts_epg.mts_kanal_finden("RTS 1") is None
        assert mts_epg.mts_hole_programme("1", tage=2) == []


def test_mts_ohne_rs_zeilen_werden_keine_requests_ausgeloest():
    """sender.txt ganz ohne RS-Zeilen darf mts_epg's Request-Funktionen
    ueberhaupt nicht kontaktieren (Zero-Risk-Garantie, analog zum
    TELEMACH:/mtel-Guard in generate_epg.py)."""
    mts_sender_leer = []

    with patch("quellen.mts_epg.requests.get", side_effect=AssertionError("mts_epg haette nicht kontaktiert werden duerfen")):
        for daten in mts_sender_leer:
            mts_epg.mts_kanal_finden(daten["sender"])

    assert mts_sender_leer == []


# ==========================================================
# MojMaxTV-EPG (automatischer Abgleich fuer HR-Sender, siehe
# mojmaxtv_epg.py)
# ==========================================================

@pytest.fixture(autouse=False)
def _mojmaxtv_cache_zuruecksetzen():
    mojmaxtv_epg._kanalliste_cache = None
    mojmaxtv_epg._schedule_cache = {}
    yield
    mojmaxtv_epg._kanalliste_cache = None
    mojmaxtv_epg._schedule_cache = {}


def _mojmaxtv_channels_response():
    return _mock_response({"channels": [{"station_id": "42", "title": "RTL Hrvatska"}]})


def _mojmaxtv_schedule_response(mit_sendung=True):
    if not mit_sendung:
        return _mock_response({"channels": {}})
    return _mock_response({
        "channels": {
            "42": [
                {
                    "description": "Vijesti",
                    "start_time": "2026-08-10T19:00:00Z",
                    "end_time": "2026-08-10T19:30:00Z",
                }
            ]
        }
    })


def test_mojmaxtv_erfolgreicher_abruf_liefert_echte_sendungen(_mojmaxtv_cache_zuruecksetzen):
    responses = [_mojmaxtv_channels_response()] + [
        _mojmaxtv_schedule_response() for _ in range(8)
    ]
    with patch("quellen.mojmaxtv_epg.requests.get", side_effect=responses):
        site_id = mojmaxtv_epg.mojmaxtv_kanal_finden("RTL Hrvatska")
        assert site_id == "42"

        programme = mojmaxtv_epg.mojmaxtv_hole_programme(site_id, tage=1)

    # 8 3h-Zeitfenster pro Tag, das Mock liefert fuer jedes Fenster
    # dieselbe eine Sendung zurueck - die Dedup-Logik (siehe
    # _hole_schedules_fuer_tag()) fasst das korrekt zu einer einzigen
    # Sendung zusammen statt sie 8x zu wiederholen (Regressionstest
    # fuer den echten MojMaxTV-Duplikat-Bug: die API liefert an jeder
    # Fenstergrenze die dort noch laufende Sendung des Vorfensters
    # zusaetzlich erneut mit, siehe Moduldocstring dort).
    assert len(programme) == 1
    sendung = programme[0]
    assert sendung["title"] == "Vijesti"
    assert sendung["start"].tzinfo is not None
    assert sendung["stop"] > sendung["start"]


def test_mojmaxtv_dedupliziert_ueberlappende_fenster_behaelt_echte_sendungen(_mojmaxtv_cache_zuruecksetzen):
    """Regressionstest fuer den echten, live beobachteten MojMaxTV-
    Duplikat-Bug (Arena Sport 8, September 2026): die API liefert an
    jeder 3h-Fenstergrenze die dort noch laufende Sendung des
    Vorfensters zusaetzlich erneut mit (identischer Titel/Start/Ende),
    wird hier ueber zwei Fenster mit einer echten Ueberlappung plus
    zwei echt unterschiedlichen Sendungen nachgebaut. Muss NUR das
    echte Duplikat entfernen, beide unterschiedlichen Sendungen
    bleiben erhalten."""
    fenster_1 = _mock_response({
        "channels": {
            "42": [
                {"description": "A", "start_time": "2026-08-10T00:00:00Z", "end_time": "2026-08-10T02:00:00Z"},
                {"description": "B", "start_time": "2026-08-10T02:00:00Z", "end_time": "2026-08-10T04:00:00Z"},
            ]
        }
    })
    fenster_2 = _mock_response({
        "channels": {
            "42": [
                # Echtes Duplikat (identisch zum letzten Eintrag aus Fenster 1):
                {"description": "B", "start_time": "2026-08-10T02:00:00Z", "end_time": "2026-08-10T04:00:00Z"},
                {"description": "C", "start_time": "2026-08-10T04:00:00Z", "end_time": "2026-08-10T07:00:00Z"},
            ]
        }
    })
    responses = [_mojmaxtv_channels_response(), fenster_1, fenster_2] + [
        _mojmaxtv_schedule_response(mit_sendung=False) for _ in range(6)
    ]
    with patch("quellen.mojmaxtv_epg.requests.get", side_effect=responses):
        site_id = mojmaxtv_epg.mojmaxtv_kanal_finden("RTL Hrvatska")
        programme = mojmaxtv_epg.mojmaxtv_hole_programme(site_id, tage=1)

    titel = [p["title"] for p in programme]
    assert titel == ["A", "B", "C"]


def test_mojmaxtv_sk_alias_matcht_nicht_faelschlich_bei_fehlendem_sport_klub(_mojmaxtv_cache_zuruecksetzen):
    """Regressionstest fuer den Fehltreffer-Bug: MojMaxTV fuehrt aktuell
    KEINEN "Sport Klub"-Kanal mehr - "SK 1" darf dann NICHT per
    unscharfem Abgleich auf einen voellig unabhaengigen Kanal wie
    "Sport 1" matchen (fuehrte zu deutschen Sendungen statt kroatischem
    Sport-Klub-Programm), sondern muss None liefern."""
    kanalliste_response = _mock_response({
        "channels": [{"station_id": "1", "title": "Sport 1"}]
    })
    with patch("quellen.mojmaxtv_epg.requests.get", return_value=kanalliste_response):
        assert mojmaxtv_epg.mojmaxtv_kanal_finden("SK 1") is None

    mojmaxtv_epg._kanalliste_cache = None
    kanalliste_mit_sport_klub = _mock_response({
        "channels": [
            {"station_id": "1", "title": "Sport 1"},
            {"station_id": "43", "title": "Sport Klub 1"},
        ]
    })
    with patch("quellen.mojmaxtv_epg.requests.get", return_value=kanalliste_mit_sport_klub):
        assert mojmaxtv_epg.mojmaxtv_kanal_finden("SK 1") == "43"


def test_mojmaxtv_kein_kanal_treffer_oder_fehlschlag_faellt_graceful_zurueck(_mojmaxtv_cache_zuruecksetzen):
    with patch("quellen.mojmaxtv_epg.requests.get", return_value=_mojmaxtv_channels_response()):
        assert mojmaxtv_epg.mojmaxtv_kanal_finden("Nicht Existierender Kanal XYZ") is None

    mojmaxtv_epg._kanalliste_cache = None
    with patch("quellen.mojmaxtv_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert mojmaxtv_epg.mojmaxtv_hole_kanalliste() == []
        assert mojmaxtv_epg.mojmaxtv_kanal_finden("RTL Hrvatska") is None
        assert mojmaxtv_epg.mojmaxtv_hole_programme("42", tage=1) == []


def test_mojmaxtv_ohne_hr_zeilen_werden_keine_requests_ausgeloest():
    """sender.txt ganz ohne HR-Zeilen darf mojmaxtv_epg's Request-
    Funktionen ueberhaupt nicht kontaktieren (Zero-Risk-Garantie)."""
    mojmaxtv_sender_leer = []

    with patch("quellen.mojmaxtv_epg.requests.get", side_effect=AssertionError("mojmaxtv_epg haette nicht kontaktiert werden duerfen")):
        for daten in mojmaxtv_sender_leer:
            mojmaxtv_epg.mojmaxtv_kanal_finden(daten["sender"])

    assert mojmaxtv_sender_leer == []


# ==========================================================
# SportKlub-EPG (Fallback fuer HR|SK N, wenn MojMaxTV nichts liefert,
# siehe sportklub_epg.py)
# ==========================================================

from quellen import sportklub_epg


@pytest.fixture(autouse=False)
def _sportklub_cache_zuruecksetzen():
    sportklub_epg._daten_cache = None
    yield
    sportklub_epg._daten_cache = None


def _sportklub_xml_response():
    heute = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="SK.1.HD.(HR).ba"><display-name>SK 1 HD (HR)</display-name></channel>
  <channel id="SK.11.HD.HR.(Portals).ba"><display-name>SK 11 HD HR (Portals)</display-name></channel>
  <channel id="SK.Golf.(BIH/SI).ba"><display-name>SK Golf (BIH/SI)</display-name></channel>
  <programme start="{heute}190000 +0000" stop="{heute}193000 +0000" channel="SK.1.HD.(HR).ba">
    <title>Nogomet: Hajduk - Dinamo</title>
  </programme>
</tv>"""
    komprimiert = gzip.compress(xml.encode("utf-8"))
    response = MagicMock()
    response.status_code = 200
    response.content = komprimiert
    response.raise_for_status = lambda: None
    return response


def test_sportklub_findet_sk1_nicht_faelschlich_sk11(_sportklub_cache_zuruecksetzen):
    """Regressionstest: 'SK 1' darf nicht auf 'SK 11'/'SK 12' matchen
    (Nummern-Praefix-Kollision bei rein textuellem Vergleich)."""
    with patch("quellen.sportklub_epg.requests.get", return_value=_sportklub_xml_response()):
        assert sportklub_epg.sportklub_kanal_finden("SK 1") == "SK.1.HD.(HR).ba"
        assert sportklub_epg.sportklub_kanal_finden("SK 11") == "SK.11.HD.HR.(Portals).ba"
        assert sportklub_epg.sportklub_kanal_finden("SK Golf") == "SK.Golf.(BIH/SI).ba"
        assert sportklub_epg.sportklub_kanal_finden("SK 99") is None


def test_sportklub_erfolgreicher_abruf_liefert_echte_sendungen(_sportklub_cache_zuruecksetzen):
    with patch("quellen.sportklub_epg.requests.get", return_value=_sportklub_xml_response()):
        site_id = sportklub_epg.sportklub_kanal_finden("SK 1")
        assert site_id == "SK.1.HD.(HR).ba"
        programme = sportklub_epg.sportklub_hole_programme(site_id, tage=365)

    assert len(programme) == 1
    assert programme[0]["title"] == "Nogomet: Hajduk - Dinamo"
    assert programme[0]["start"].tzinfo is not None


def test_sportklub_kaputtes_gzip_gibt_none_statt_exception(_sportklub_cache_zuruecksetzen):
    kaputte_response = MagicMock()
    kaputte_response.status_code = 200
    kaputte_response.content = b"kein gueltiges gzip/xml"
    kaputte_response.raise_for_status = lambda: None
    with patch("quellen.sportklub_epg.requests.get", return_value=kaputte_response):
        assert sportklub_epg.sportklub_kanal_finden("SK 1") is None
        assert sportklub_epg.sportklub_hole_programme("SK.1.HD.(HR).ba") == []


# ==========================================================
# Magenta-myTeamTV-EPG (Fallback fuer MAGENTA SPORT PPV 1-18, siehe
# magenta_myteam_epg.py)
# ==========================================================

from quellen import magenta_myteam_epg


@pytest.fixture(autouse=False)
def _magenta_myteam_cache_zuruecksetzen():
    magenta_myteam_epg._daten_cache = None
    yield
    magenta_myteam_epg._daten_cache = None


def _magenta_myteam_xml_response():
    heute = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="Sport.1.-.myTeamTV.de"><display-name>Sport 1 - myTeamTV</display-name></channel>
  <channel id="Sport.10.-.myTeamTV.de"><display-name>Sport 10 - myTeamTV</display-name></channel>
  <channel id="Andere.Sport.1.de"><display-name>Sport 1 - myTeamTV Sonstige</display-name></channel>
  <programme start="{heute}170000 +0000" stop="{heute}203000 +0000" channel="Sport.1.-.myTeamTV.de">
    <title>Live: Champions Hockey League</title>
  </programme>
  <programme start="{heute}040000 +0000" stop="{heute}080000 +0000" channel="Sport.10.-.myTeamTV.de">
    <title>myTeamTV: Momentan kein Programm</title>
  </programme>
</tv>"""
    komprimiert = gzip.compress(xml.encode("utf-8"))
    response = MagicMock()
    response.status_code = 200
    response.content = komprimiert
    response.raise_for_status = lambda: None
    return response


def test_magenta_myteam_findet_ppv1_nicht_faelschlich_ppv10(_magenta_myteam_cache_zuruecksetzen):
    """Regressionstest: 'MAGENTA SPORT PPV 1' darf nicht auf 'Sport 10 -
    myTeamTV' matchen (Nummern-Praefix-Kollision). MPX-Kanalliste wird
    hier bewusst leer gemockt, damit der (fuer diesen Test irrelevante)
    epgshare01-Fallback-Zweig geprueft wird."""
    with patch("quellen.magenta_myteam_epg.magenta_hole_kanalliste", return_value=[]), \
         patch("quellen.magenta_myteam_epg.requests.get", return_value=_magenta_myteam_xml_response()):
        assert magenta_myteam_epg.magenta_myteam_kanal_finden("MAGENTA SPORT PPV 1 HD") == ("epgshare", "Sport.1.-.myTeamTV.de")
        assert magenta_myteam_epg.magenta_myteam_kanal_finden("MAGENTA SPORT PPV 10 HD") == ("epgshare", "Sport.10.-.myTeamTV.de")
        assert magenta_myteam_epg.magenta_myteam_kanal_finden("MAGENTA SPORT PPV 99 HD") is None
        assert magenta_myteam_epg.magenta_myteam_kanal_finden("RTL HD") is None
        # "MYTEAM SPORT N" ist dasselbe Namensschema wie "MAGENTA SPORT
        # PPV N" (dieselben 18 Kanaele, siehe Moduldocstring).
        assert magenta_myteam_epg.magenta_myteam_kanal_finden("MYTEAM SPORT 1 HD") == ("epgshare", "Sport.1.-.myTeamTV.de")


def test_magenta_myteam_erfolgreicher_abruf_liefert_echte_sendungen_inkl_platzhalter(_magenta_myteam_cache_zuruecksetzen):
    with patch("quellen.magenta_myteam_epg.magenta_hole_kanalliste", return_value=[]), \
         patch("quellen.magenta_myteam_epg.requests.get", return_value=_magenta_myteam_xml_response()):
        kanal_ref = magenta_myteam_epg.magenta_myteam_kanal_finden("MAGENTA SPORT PPV 1 HD")
        programme = magenta_myteam_epg.magenta_myteam_hole_programme(kanal_ref, tage=365)

        leer_kanal_ref = magenta_myteam_epg.magenta_myteam_kanal_finden("MAGENTA SPORT PPV 10 HD")
        leer_programme = magenta_myteam_epg.magenta_myteam_hole_programme(leer_kanal_ref, tage=365)

    assert len(programme) == 1
    assert programme[0]["title"] == "Live: Champions Hockey League"
    # Der generische "kein Programm"-Platzhalter der Quelle selbst wird
    # NICHT mehr herausgefiltert (auf Nutzerwunsch) - er soll bei
    # Leerlauf genau wie von myTeamTV geliefert im EPG-Raster erscheinen,
    # statt eines selbst ausgedachten Ersatztextes.
    assert len(leer_programme) == 1
    assert "kein Programm" in leer_programme[0]["title"]


def test_magenta_myteam_kaputtes_gzip_gibt_none_statt_exception(_magenta_myteam_cache_zuruecksetzen):
    kaputte_response = MagicMock()
    kaputte_response.status_code = 200
    kaputte_response.content = b"kein gueltiges gzip/xml"
    kaputte_response.raise_for_status = lambda: None
    with patch("quellen.magenta_myteam_epg.magenta_hole_kanalliste", return_value=[]), \
         patch("quellen.magenta_myteam_epg.requests.get", return_value=kaputte_response):
        assert magenta_myteam_epg.magenta_myteam_kanal_finden("MAGENTA SPORT PPV 1 HD") is None
        assert magenta_myteam_epg.magenta_myteam_hole_programme(("epgshare", "Sport.1.-.myTeamTV.de")) == []


# ==========================================================
# Joyn-VOD-EPG (letzter Fallback der DE-Kaskade fuer Joyns thematische
# Serien-/Doku-"Sender", siehe joyn_vod_epg.py)
# ==========================================================

from quellen import joyn_vod_epg


@pytest.fixture(autouse=False)
def _joyn_vod_cache_zuruecksetzen():
    joyn_vod_epg._daten_cache = None
    yield
    joyn_vod_epg._daten_cache = None


def _joyn_vod_xml_response():
    heute = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="joyn-vod-de-odc-ancientaliens"><display-name lang="de">Ancient Aliens</display-name></channel>
  <channel id="joyn-vod-de-odc-charmed"><display-name lang="de">Charmed</display-name></channel>
  <programme start="{heute}060000 +0000" stop="{heute}070000 +0000" channel="joyn-vod-de-odc-ancientaliens">
    <title>Ancient Aliens</title>
  </programme>
</tv>"""
    response = MagicMock()
    response.status_code = 200
    response.content = gzip.compress(xml.encode("utf-8"))
    response.raise_for_status = lambda: None
    return response


def test_joyn_vod_findet_exakten_namen_kein_fuzzy(_joyn_vod_cache_zuruecksetzen):
    with patch("quellen.joyn_vod_epg.requests.get", return_value=_joyn_vod_xml_response()):
        site_id = joyn_vod_epg.joyn_vod_kanal_finden("ANCIENT ALIENS ᴿᴬᵂ")
        programme = joyn_vod_epg.joyn_vod_hole_programme(site_id, tage=365)

        # Kein Treffer fuer einen komplett anderen Namen - kein Fuzzy-
        # Abgleich, der faelschlich auf "Charmed" matchen koennte.
        kein_treffer = joyn_vod_epg.joyn_vod_kanal_finden("Voellig Anderer Name XYZ")

    assert site_id == "joyn-vod-de-odc-ancientaliens"
    assert len(programme) == 1
    assert programme[0]["title"] == "Ancient Aliens"
    assert kein_treffer is None


def test_joyn_vod_kaputtes_gzip_gibt_none_statt_exception(_joyn_vod_cache_zuruecksetzen):
    kaputte_response = MagicMock()
    kaputte_response.status_code = 200
    kaputte_response.content = b"kein gueltiges gzip/xml"
    kaputte_response.raise_for_status = lambda: None
    with patch("quellen.joyn_vod_epg.requests.get", return_value=kaputte_response):
        assert joyn_vod_epg.joyn_vod_kanal_finden("Ancient Aliens") is None
        assert joyn_vod_epg.joyn_vod_hole_programme("joyn-vod-de-odc-ancientaliens") == []


# ==========================================================
# Siol-EPG (automatischer Abgleich fuer SI-Sender, HTML-Scraping,
# siehe siol_epg.py)
# ==========================================================

@pytest.fixture(autouse=False)
def _siol_cache_zuruecksetzen():
    siol_epg._kanalliste_cache = None
    siol_epg._programm_cache = {}
    yield
    siol_epg._kanalliste_cache = None
    siol_epg._programm_cache = {}


def _siol_kanalliste_html(kanaele):
    """Baut ein minimales HTML-Fixture der siol.net-Kanaluebersichtsseite
    (/kanali), wie es siol_hole_kanalliste() per BeautifulSoup parsen
    koennen muss: ein <a href="/kanal/<slug>" target="_self"> mit
    verschachteltem <img alt="<Name>">."""
    teile = []
    for slug, name in kanaele:
        teile.append(
            f'<div><a href="/kanal/{slug}" target="_self">'
            f'<img alt="{name}" src="/slika/kanal/{slug}"/></a></div>'
        )
    return "<html><body>" + "".join(teile) + "</body></html>"


def _siol_programm_html(site_id, sendungen, datum="20260810"):
    """Baut ein minimales HTML-Fixture einer siol.net-Kanal/Tag-Seite
    (/kanal/<site_id>/datum/<datum>), wie es _hole_events_fuer_kanal_
    und_tag() per BeautifulSoup parsen koennen muss: pro Sendung ein
    <a href=".../oddaja/..."> mit Zeit-, Titel- und Kategorie-Divs."""
    teile = []
    for i, (zeit, titel, kategorie) in enumerate(sendungen):
        teile.append(
            f'<a href="/kanal/{site_id}/oddaja/sendung-{i}/{i}/datum/{datum}">'
            f'<div class="w-[70px] text-center flex-none">{zeit}</div>'
            '<div class="flex-initial">'
            f'<div class="font-extrabold" title="{titel}">{titel}</div>'
            f'<div class="desktop:order-last">{kategorie}</div>'
            "</div></a>"
        )
    return "<html><body>" + "".join(teile) + "</body></html>"


def test_siol_kanalliste_wird_aus_html_geparst(_siol_cache_zuruecksetzen):
    """Exercised die echte HTML-Extraktionslogik (kein Mocken der
    Parse-Funktion selbst) mit einem handgebauten Kanalliste-Fixture."""
    html = _siol_kanalliste_html([("rtv1", "RTV SLO 1"), ("alsatm", "Alsat Macedonia")])

    response = MagicMock()
    response.text = html
    response.raise_for_status.return_value = None

    with patch("quellen.siol_epg.requests.get", return_value=response):
        kanaele = siol_epg.siol_hole_kanalliste()

    assert kanaele == [
        {"site_id": "rtv1", "name": "RTV SLO 1"},
        {"site_id": "alsatm", "name": "Alsat Macedonia"},
    ]


def test_siol_programm_html_wird_geparst_und_endzeit_berechnet(_siol_cache_zuruecksetzen):
    """Die Seite liefert keine Endzeiten - die Endzeit einer Sendung
    muss aus der Startzeit der naechsten Sendung berechnet werden."""
    html = _siol_programm_html("rtv1", [("19.00", "Dnevnik", "Informativno"), ("19.30", "Vreme", "Informativno")])

    response = MagicMock()
    response.text = html
    response.raise_for_status.return_value = None

    with patch("quellen.siol_epg.requests.get", return_value=response):
        events = siol_epg._hole_events_fuer_kanal_und_tag("rtv1", datetime.datetime(2026, 8, 10, tzinfo=siol_epg.LJUBLJANA_TZ))

    assert events == [("19.00", "Dnevnik", "Informativno"), ("19.30", "Vreme", "Informativno")]


def test_siol_kaputte_html_struktur_gibt_leere_liste_statt_exception(_siol_cache_zuruecksetzen):
    """Fehlt die erwartete Struktur komplett oder ist die Seite leer,
    muss die Extraktion still [] liefern statt zu werfen - dieser
    Scraping-Pfad ist bewusst fragil."""
    response = MagicMock()
    response.text = "<html><body>Keine Kanaele hier</body></html>"
    response.raise_for_status.return_value = None

    with patch("quellen.siol_epg.requests.get", return_value=response):
        assert siol_epg.siol_hole_kanalliste() == []

    siol_epg._kanalliste_cache = None
    with patch("quellen.siol_epg.requests.get", side_effect=Exception("kaputt")):
        assert siol_epg.siol_hole_kanalliste() == []


def test_siol_erfolgreicher_abruf_liefert_echte_sendungen(_siol_cache_zuruecksetzen):
    kanalliste_html = _siol_kanalliste_html([("rtv1", "RTV SLO 1")])
    programm_html = _siol_programm_html("rtv1", [("19.00", "Dnevnik", "Informativno")])

    kanalliste_response = MagicMock()
    kanalliste_response.text = kanalliste_html
    kanalliste_response.raise_for_status.return_value = None

    programm_response = MagicMock()
    programm_response.text = programm_html
    programm_response.raise_for_status.return_value = None

    with patch("quellen.siol_epg.requests.get", side_effect=[kanalliste_response, programm_response]):
        site_id = siol_epg.siol_kanal_finden("RTV SLO 1")
        assert site_id == "rtv1"

        programme = siol_epg.siol_hole_programme(site_id, tage=1)

    assert len(programme) == 1
    sendung = programme[0]
    assert sendung["title"] == "Dnevnik"
    assert sendung["start"].tzinfo is not None
    assert sendung["stop"] > sendung["start"]


def test_siol_mrt_alias_matcht_nicht_faelschlich_rts_oder_hrt(_siol_cache_zuruecksetzen):
    """Regressionstest fuer den Fehltreffer-Bug: kurze mazedonische
    Sendernamen wie "MRT 1"/"MRT 2 HD" duerfen nicht per unscharfem
    Abgleich auf voellig andere Sender (RTS/HRT/MTV Live HD) matchen,
    sondern muessen ueber die feste Alias-Tabelle korrekt auf die
    echten siol.net-MRT-Kanaele (mktv1/mktv2/mktv3) aufgeloest werden."""
    kanalliste_html = _siol_kanalliste_html([
        ("rts1", "RTS 1"),
        ("rts2", "RTS 2"),
        ("hrt3", "HRT 3"),
        ("mktv1", "MTV 1"),
        ("mktv2", "MTV 2"),
        ("mktv3", "MTV 3 Sobrainski"),
        ("mtvlivehd", "MTV Live HD"),
    ])
    response = MagicMock()
    response.text = kanalliste_html
    response.raise_for_status.return_value = None

    with patch("quellen.siol_epg.requests.get", return_value=response):
        assert siol_epg.siol_kanal_finden("MRT 1") == "mktv1"
        assert siol_epg.siol_kanal_finden("MRT 2") == "mktv2"
        assert siol_epg.siol_kanal_finden("MRT 2 HD") == "mktv2"
        assert siol_epg.siol_kanal_finden("MRT 3") == "mktv3"
        assert siol_epg.siol_kanal_finden("MRT 3 ⱽᴵᴾ ᴿᴬᵂ") == "mktv3"


def test_siol_kein_kanal_treffer_oder_fehlschlag_faellt_graceful_zurueck(_siol_cache_zuruecksetzen):
    kanalliste_html = _siol_kanalliste_html([("rtv1", "RTV SLO 1")])
    kanalliste_response = MagicMock()
    kanalliste_response.text = kanalliste_html
    kanalliste_response.raise_for_status.return_value = None

    with patch("quellen.siol_epg.requests.get", return_value=kanalliste_response):
        assert siol_epg.siol_kanal_finden("Nicht Existierender Kanal XYZ") is None

    siol_epg._kanalliste_cache = None
    with patch("quellen.siol_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert siol_epg.siol_hole_kanalliste() == []
        assert siol_epg.siol_kanal_finden("RTV SLO 1") is None
        assert siol_epg.siol_hole_programme("rtv1", tage=1) == []


def test_siol_ohne_si_zeilen_werden_keine_requests_ausgeloest():
    """sender.txt ganz ohne SI-Zeilen darf siol_epg's Request-Funktionen
    ueberhaupt nicht kontaktieren (Zero-Risk-Garantie)."""
    siol_sender_leer = []

    with patch("quellen.siol_epg.requests.get", side_effect=AssertionError("siol_epg haette nicht kontaktiert werden duerfen")):
        for daten in siol_sender_leer:
            siol_epg.siol_kanal_finden(daten["sender"])

    assert siol_sender_leer == []


# ==========================================================
# TVPASSPORT-EPG (opt-in TVPASSPORT:-Sender, nur US, statische
# Kanalliste tvpassport_kanalliste.xml, siehe tvpassport_epg.py)
# ==========================================================

@pytest.fixture(autouse=True)
def _tvpassport_cache_zuruecksetzen():
    tvpassport_epg._kanalliste_cache = None
    yield
    tvpassport_epg._kanalliste_cache = None


def _mock_html_response(html_text, status_ok=True):
    response = MagicMock()
    response.text = html_text
    if status_ok:
        response.raise_for_status.return_value = None
    else:
        response.raise_for_status.side_effect = Exception("HTTP-Fehler")
    return response


def _tvpassport_tagesseite_html():
    return """
    <html><body>
    <select id="timezone_selector">
        <option value="America/New_York" selected="selected">Eastern</option>
    </select>
    <div class="station-listings">
        <div class="list-group-item"
             data-st="2026-08-10 20:00:00"
             data-duration="60"
             data-showname="Evening News"
             data-episodetitle=""
             data-description="Lokale Nachrichten"
             data-showpicture="news.jpg"></div>
        <div class="list-group-item"
             data-st="2026-08-10 21:00:00"
             data-duration="120"
             data-showname="Movie"
             data-episodetitle="Der grosse Film"
             data-description=""
             data-showpicture=""></div>
    </div>
    </body></html>
    """


def test_tvpassport_kanal_finden_nutzt_reale_statische_kanalliste():
    """kanal_finden muss ohne jeglichen Netzwerk-Request gegen die echte,
    im Repo mitgelieferte tvpassport_kanalliste.xml aufloesen - Beispiel
    per exaktem Namen aus der Datei selbst gelesen, damit der Test nicht
    von einem geratenen Eintrag abhaengt."""
    import xml.etree.ElementTree as ET

    baum = ET.parse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "quellen", "tvpassport_kanalliste.xml"))
    treffer = None
    for element in baum.getroot().findall("channel"):
        if (element.text or "").strip() == "FOX (KFFX) Yakima, WA":
            treffer = element.get("site_id")
            break

    assert treffer is not None, "Erwarteter Beispiel-Kanal nicht in tvpassport_kanalliste.xml gefunden"

    with patch("quellen.tvpassport_epg.requests.get", side_effect=AssertionError("kanal_finden haette keinen Netzwerk-Request ausloesen duerfen")):
        site_id = tvpassport_epg.tvpassport_kanal_finden("FOX (KFFX) Yakima, WA")

    assert site_id == treffer


def test_tvpassport_erfolgreicher_programmabruf_und_kanal_id_format():
    """Nach erfolgreicher (statischer) Kanalsuche muss der gemockte
    Schedule-Abruf echte Sendungen liefern - inkl. Movie/data-episodetitle-
    Tausch. Zusaetzlich Regressionscheck fuer das 'LAND| Name'-kanal-id-
    Format (analog TVGUIDE:)."""
    site_id = tvpassport_epg.tvpassport_kanal_finden("FOX (KFFX) Yakima, WA")
    assert site_id is not None

    responses = [_mock_html_response(_tvpassport_tagesseite_html()) for _ in range(2)]
    with patch("quellen.tvpassport_epg.requests.get", side_effect=responses):
        programme = tvpassport_epg.tvpassport_hole_programme(site_id, tage=2)

    assert len(programme) >= 1
    titel = [p["title"] for p in programme]
    assert "Evening News" in titel
    assert "Der grosse Film" in titel  # Movie -> episodetitle-Tausch
    for p in programme:
        assert p["start"].tzinfo is not None
        assert p["stop"] > p["start"]

    tvpassport_land = "US"
    tvpassport_kanalname = "FOX (KFFX) Yakima, WA"
    kanal = f"{tvpassport_land}| {tvpassport_kanalname}"
    assert kanal == "US| FOX (KFFX) Yakima, WA"
    assert kanal != tvpassport_kanalname


def test_tvpassport_kein_kanal_treffer_oder_fehlschlag_faellt_graceful_zurueck():
    """Kein Kanal-Treffer bzw. ein Netzwerkfehler duerfen NIE eine
    Exception werfen, sondern muessen graceful auf None/[]
    zurueckfallen."""
    assert tvpassport_epg.tvpassport_kanal_finden("Nicht Existierender Kanal Voellig Andere Stadt XYZ 999") is None

    with patch("quellen.tvpassport_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert tvpassport_epg.tvpassport_hole_programme("fox-kffx-yakima-wa/2141", tage=2) == []


def test_tvpassport_callsign_findet_exakten_hauptkanal_nicht_subkanal():
    """tvpassport_kanal_finden_callsign() muss ueber die Call-Sign in
    "ABC KATC BROOKLYN" (falsche/generische sender.txt-Stadtangabe) den
    tvpassport-Hauptaffiliate "ABC (KATC) Lafayette, LA" finden - NICHT
    einen der aehnlich benannten Subkanaele mit anderer Programmquelle
    (z.B. "Grit TV (KATC3)"/"CW (KATC2)"), da nur die exakte Klammer
    "(KATC)" ohne Zahlen-/Bindestrich-Suffix als Treffer zaehlen darf."""
    site_id = tvpassport_epg.tvpassport_kanal_finden_callsign("ABC KATC BROOKLYN ᴿᴬᵂ")
    assert site_id is not None
    assert "katc" in site_id.lower()
    assert "katc2" not in site_id.lower() and "katc3" not in site_id.lower() and "katc4" not in site_id.lower()


def test_tvpassport_callsign_ohne_erkennbare_callsign_gibt_none():
    """Ohne eine erkennbare Call-Sign (kein K/W-Wort) darf kein
    Zufallstreffer entstehen."""
    assert tvpassport_epg.tvpassport_kanal_finden_callsign("Nur Ein Generischer Name") is None


def test_tvpassport_ohne_tvpassport_zeilen_werden_keine_requests_ausgeloest():
    """sender.txt ganz ohne TVPASSPORT:-Zeilen darf tvpassport_epg's
    Schedule-Request-Funktion ueberhaupt nicht kontaktieren (Zero-Risk-
    Garantie, analog zum TVGUIDE:-Guard). Die statische Kanalliste darf
    weiterhin lokal gelesen werden (kein Netzwerk-Request)."""
    tvpassport_sender_leer = []

    with patch("quellen.tvpassport_epg.requests.get", side_effect=AssertionError("tvpassport_epg haette nicht kontaktiert werden duerfen")):
        for daten in tvpassport_sender_leer:
            tvpassport_epg.tvpassport_hole_programme(daten["sender"])

    assert tvpassport_sender_leer == []


def _plutotv_xmltv_bauen(kanaele, programme):
    root = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<tv generator-info-name=\"www.matthuisman.nz\">\n"
    for kid, name in kanaele:
        root += f'  <channel id="{kid}"><display-name>{name}</display-name></channel>\n'
    for kid, titel, start, stop, beschr in programme:
        root += (
            f'  <programme start="{start}" stop="{stop}" channel="{kid}">'
            f'<title>{titel}</title><desc>{beschr}</desc></programme>\n'
        )
    root += "</tv>"
    return root.encode("utf-8")


@pytest.fixture
def _plutotv_cache_zuruecksetzen():
    plutotv_epg._daten_cache = None
    yield
    plutotv_epg._daten_cache = None


def test_plutotv_erfolgreicher_abruf_liefert_echte_sendungen(_plutotv_cache_zuruecksetzen):
    heute = datetime.datetime.now(datetime.timezone.utc)
    start_str = heute.strftime("%Y%m%d") + "180000 +0000"
    stop_str = heute.strftime("%Y%m%d") + "183000 +0000"
    xml_bytes = _plutotv_xmltv_bauen(
        [("abc123", "iCarly")],
        [("abc123", "Freddie und Sam", start_str, stop_str, "Kurzbeschreibung")],
    )
    response = MagicMock()
    response.content = xml_bytes
    response.raise_for_status.return_value = None

    with patch("quellen.plutotv_epg.requests.get", return_value=response):
        site_id = plutotv_epg.plutotv_kanal_finden("ICARLY")
        assert site_id == "abc123"

        programme = plutotv_epg.plutotv_hole_programme(site_id, tage=1)

    assert len(programme) == 1
    sendung = programme[0]
    assert sendung["title"] == "Freddie und Sam"
    assert sendung["beschreibung"] == "Kurzbeschreibung"
    assert sendung["start"].tzinfo is not None
    assert sendung["stop"] > sendung["start"]


def test_plutotv_kein_kanal_treffer_oder_fehlschlag_faellt_graceful_zurueck(_plutotv_cache_zuruecksetzen):
    xml_bytes = _plutotv_xmltv_bauen([("abc123", "iCarly")], [])
    response = MagicMock()
    response.content = xml_bytes
    response.raise_for_status.return_value = None

    with patch("quellen.plutotv_epg.requests.get", return_value=response):
        assert plutotv_epg.plutotv_kanal_finden("Nicht Existierender Kanal Voellig Andere Stadt XYZ 999") is None

    plutotv_epg._daten_cache = None
    with patch("quellen.plutotv_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert plutotv_epg.plutotv_kanal_finden("ICARLY") is None
        assert plutotv_epg.plutotv_hole_programme("abc123", tage=1) == []


def test_plutotv_ohne_de_sender_werden_keine_requests_ausgeloest():
    """sender.txt ohne DE-Zeilen darf plutotv_epg's Download-Funktion
    ueberhaupt nicht kontaktieren (Zero-Risk-Garantie, analog zu den
    anderen automatischen Quellen)."""
    plutotv_relevante_sender_leer = []

    with patch("quellen.plutotv_epg.requests.get", side_effect=AssertionError("plutotv_epg haette nicht kontaktiert werden duerfen")):
        for daten in plutotv_relevante_sender_leer:
            plutotv_epg.plutotv_hole_programme(daten["sender"])

    assert plutotv_relevante_sender_leer == []




@pytest.fixture
def _klix_cache_zuruecksetzen():
    klix_epg._kanalliste_cache = None
    klix_epg._tag_cache = {}
    yield
    klix_epg._kanalliste_cache = None
    klix_epg._tag_cache = {}


def test_klix_kanalliste_wird_aus_datei_gelesen(_klix_cache_zuruecksetzen):
    kanaele = klix_epg.klix_hole_kanalliste()
    assert len(kanaele) > 0
    assert any(k["name"].upper() == "BHT1" for k in kanaele)


def test_klix_kanal_finden_exakt_und_kein_treffer(_klix_cache_zuruecksetzen):
    assert klix_epg.klix_kanal_finden("BHT1") is not None
    assert klix_epg.klix_kanal_finden("Nicht Existierender Kanal Voellig Andere Stadt XYZ 999") is None


def test_klix_erfolgreicher_abruf_liefert_echte_sendungen(_klix_cache_zuruecksetzen):
    response = MagicMock()
    response.json.return_value = [
        {"timeStart": "20:00", "title": "Dnevnik", "type": "Info"},
        {"timeStart": "20:30", "title": "Film", "type": "Film"},
    ]
    response.raise_for_status.return_value = None

    with patch("quellen.klix_epg.requests.get", return_value=response):
        programme = klix_epg.klix_hole_programme("59", tage=1)

    assert len(programme) == 2
    sendung = programme[0]
    assert sendung["title"] == "Dnevnik"
    assert sendung["start"].tzinfo is not None
    assert sendung["stop"] > sendung["start"]


def test_klix_kein_kanal_treffer_oder_fehlschlag_faellt_graceful_zurueck(_klix_cache_zuruecksetzen):
    assert klix_epg.klix_kanal_finden("Nicht Existierender Kanal Voellig Andere Stadt XYZ 999") is None

    with patch("quellen.klix_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert klix_epg.klix_hole_programme("59", tage=1) == []


def test_klix_ohne_relevante_sender_werden_keine_requests_ausgeloest():
    """sender.txt ohne BA-Zeilen darf klix_epg's Programm-Request-Funktion
    ueberhaupt nicht kontaktieren (Zero-Risk-Garantie, analog zu den
    anderen automatischen Quellen). Die statische Kanalliste darf
    weiterhin lokal gelesen werden (kein Netzwerk-Request)."""
    klix_relevante_sender_leer = []

    with patch("quellen.klix_epg.requests.get", side_effect=AssertionError("klix_epg haette nicht kontaktiert werden duerfen")):
        for daten in klix_relevante_sender_leer:
            klix_epg.klix_hole_programme(daten["sender"])

    assert klix_relevante_sender_leer == []


def _tvmovie_broadcast_html(titel, zeit, datum_text, genre1="Genre", genre2="Subgenre"):
    return (
        f'<a aria-label="{titel}" class="bx-epg-broadcast" href="https://www.tvmovie.de/tv/x">'
        f'<figure><img src=""/></figure><div>'
        f'<div><span>{genre1}</span><span>{genre2}</span></div>'
        f'<div>{titel}</div><div><!-- --></div>'
        f'<div><span>{zeit}</span><span>- {datum_text}</span></div>'
        f'</div></a>'
    )


@pytest.fixture
def _tvmovie_cache_zuruecksetzen():
    tvmovie_epg._kanalliste_cache = None
    tvmovie_epg._seite_cache = {}
    yield
    tvmovie_epg._kanalliste_cache = None
    tvmovie_epg._seite_cache = {}


def test_tvmovie_kanalliste_wird_aus_datei_gelesen(_tvmovie_cache_zuruecksetzen):
    kanaele = tvmovie_epg.tvmovie_hole_kanalliste()
    assert len(kanaele) > 0
    assert any(k["name"].upper() == "ARD" for k in kanaele)


def test_tvmovie_kanal_finden_exakt_und_kein_treffer(_tvmovie_cache_zuruecksetzen):
    assert tvmovie_epg.tvmovie_kanal_finden("ARD") == "ard"
    assert tvmovie_epg.tvmovie_kanal_finden("Nicht Existierender Kanal Voellig Andere Stadt XYZ 999") is None


def test_tvmovie_erfolgreicher_abruf_liefert_echte_sendungen(_tvmovie_cache_zuruecksetzen):
    heute = datetime.datetime.now(tvmovie_epg.BERLIN_TZ)
    datum_text = f"Mi. {heute.day:02d}.{heute.month:02d}."
    html = "<html><body>" + _tvmovie_broadcast_html("Tagesschau", "20:00-20:15", datum_text) + "</body></html>"
    response = MagicMock()
    response.text = html
    response.raise_for_status.return_value = None

    with patch("quellen.tvmovie_epg.requests.get", return_value=response):
        programme = tvmovie_epg.tvmovie_hole_programme("ard", tage=1)

    assert len(programme) == 1
    sendung = programme[0]
    assert sendung["title"] == "Tagesschau"
    assert sendung["beschreibung"] == "Genre / Subgenre"
    assert sendung["start"].tzinfo is not None
    assert sendung["stop"] > sendung["start"]


def test_tvmovie_kein_kanal_treffer_oder_fehlschlag_faellt_graceful_zurueck(_tvmovie_cache_zuruecksetzen):
    assert tvmovie_epg.tvmovie_kanal_finden("Nicht Existierender Kanal Voellig Andere Stadt XYZ 999") is None

    with patch("quellen.tvmovie_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert tvmovie_epg.tvmovie_hole_programme("ard", tage=1) == []

    response = MagicMock()
    response.text = "<html><body>kein passendes Markup hier</body></html>"
    response.raise_for_status.return_value = None
    with patch("quellen.tvmovie_epg.requests.get", return_value=response):
        assert tvmovie_epg.tvmovie_hole_programme("zdf", tage=1) == []


def test_tvmovie_ohne_relevante_sender_werden_keine_requests_ausgeloest():
    """sender.txt ohne TVMOVIE:-Zeilen darf tvmovie_epg's Seitenabruf-
    Funktion ueberhaupt nicht kontaktieren (Zero-Risk-Garantie, analog
    zu den anderen automatischen Quellen). Die statische Kanalliste
    darf weiterhin lokal gelesen werden (kein Netzwerk-Request)."""
    tvmovie_relevante_sender_leer = []

    with patch("quellen.tvmovie_epg.requests.get", side_effect=AssertionError("tvmovie_epg haette nicht kontaktiert werden duerfen")):
        for daten in tvmovie_relevante_sender_leer:
            tvmovie_epg.tvmovie_hole_programme(daten["sender"])

    assert tvmovie_relevante_sender_leer == []


# ---------------------------------------------------------------------------
# epgshare01 DE1/AT1/CH1 (epgshare_de_epg.py) + abgedeckte_minuten()
# ---------------------------------------------------------------------------

from quellen import epgshare_de_epg
from epg_lib import abgedeckte_minuten


@pytest.fixture
def _epgshare_de_cache_zuruecksetzen(monkeypatch):
    epgshare_de_epg._daten_cache = None
    monkeypatch.setattr(epgshare_de_epg, "MIN_SENDUNGEN_PRO_KANAL", 1)
    yield
    epgshare_de_epg._daten_cache = None


def _epgshare_de_antworten(feeds):
    """feeds: {"DE1": xml_bytes, ...} -> requests.get-Ersatz je Feed-URL."""
    def fake_get(url, **kwargs):
        response = MagicMock()
        response.raise_for_status.return_value = None
        for feed, xml_bytes in feeds.items():
            if f"epg_ripper_{feed}.xml.gz" in url:
                response.content = gzip.compress(xml_bytes)
                return response
        raise RuntimeError("Feed nicht erreichbar")
    return fake_get


def _epgshare_de_xml(kanaele):
    heute = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'
    for kid, name in kanaele:
        xml += f'<channel id="{kid}"><display-name>{name}</display-name></channel>\n'
        xml += (
            f'<programme start="{heute}180000 +0000" stop="{heute}190000 +0000" channel="{kid}">'
            f'<title>Sendung {name}</title><desc>Beschreibung</desc></programme>\n'
        )
    return (xml + "</tv>").encode("utf-8")


def test_epgshare_de_findet_exakt_alias_und_kern_aber_kein_fuzzy(_epgshare_de_cache_zuruecksetzen):
    feeds = {"DE1": _epgshare_de_xml([
        ("Das.Erste.de", "Das Erste"), ("kabel.eins.de", "kabel eins"),
        ("RTLZWEI.de", "RTLZWEI"), ("Sky.Sport.2.de", "Sky Sport 2"),
    ])}
    with patch("quellen.epgshare_de_epg.requests.get", side_effect=_epgshare_de_antworten(feeds)):
        assert epgshare_de_epg.epgshare_de_kanal_finden("ARD HD") == "DE1:Das.Erste.de"
        assert epgshare_de_epg.epgshare_de_kanal_finden("KABEL 1 HEVC") == "DE1:kabel.eins.de"
        assert epgshare_de_epg.epgshare_de_kanal_finden("RTL II") == "DE1:RTLZWEI.de"
        assert epgshare_de_epg.epgshare_de_kanal_finden("SKY SPORT 2 ᴴᴰ") == "DE1:Sky.Sport.2.de"
        # kein unscharfer Treffer: "Sky Sport 3" darf NICHT auf "Sky Sport 2" fallen
        assert epgshare_de_epg.epgshare_de_kanal_finden("SKY SPORT 3") is None
        assert epgshare_de_epg.epgshare_de_kanal_finden("BLOOMBERG") is None


def test_epgshare_de_erster_feed_gewinnt_bei_gleichem_namen(_epgshare_de_cache_zuruecksetzen):
    feeds = {
        "DE1": _epgshare_de_xml([("ORF.1.de", "ORF 1")]),
        "CH1": _epgshare_de_xml([("ORF1.ch", "ORF 1")]),
    }
    with patch("quellen.epgshare_de_epg.requests.get", side_effect=_epgshare_de_antworten(feeds)):
        site_id = epgshare_de_epg.epgshare_de_kanal_finden("ORF 1")
        assert site_id == "DE1:ORF.1.de"
        programme = epgshare_de_epg.epgshare_de_hole_programme(site_id, tage=1)
    assert len(programme) == 1
    assert programme[0]["title"] == "Sendung ORF 1"
    assert programme[0]["start"].tzinfo is not None


def test_epgshare_de_fehlgeschlagener_feed_laesst_andere_nutzbar_und_wirft_nie(_epgshare_de_cache_zuruecksetzen):
    feeds = {"AT1": _epgshare_de_xml([("PRO.7.at", "PRO 7")])}  # DE1/CH1 nicht erreichbar
    with patch("quellen.epgshare_de_epg.requests.get", side_effect=_epgshare_de_antworten(feeds)):
        assert epgshare_de_epg.epgshare_de_kanal_finden("PRO7") == "AT1:PRO.7.at"
        assert epgshare_de_epg.epgshare_de_hole_programme(None) == []
        assert epgshare_de_epg.epgshare_de_hole_programme("DE1:gibts.nicht") == []


def test_epgshare_de_alles_kaputt_gibt_none_statt_exception(_epgshare_de_cache_zuruecksetzen):
    with patch("quellen.epgshare_de_epg.requests.get", side_effect=RuntimeError("down")):
        assert epgshare_de_epg.epgshare_de_kanal_finden("ARD") is None
        assert epgshare_de_epg.epgshare_de_hole_programme("DE1:x") == []


def test_abgedeckte_minuten_zaehlt_ueberlappungen_nur_einmal_und_schneidet_am_fenster():
    utc = datetime.timezone.utc
    von = datetime.datetime(2026, 10, 4, 0, 0, tzinfo=utc)
    bis = von + datetime.timedelta(days=1)
    h = lambda stunde: von + datetime.timedelta(hours=stunde)
    intervalle = [(h(-2), h(1)), (h(0), h(2)), (h(10), h(12)), (h(23), h(27))]
    # 00-02 (2h, ueberlappend nur einmal) + 10-12 (2h) + 23-24 (1h, am Fenster geschnitten)
    assert abgedeckte_minuten(intervalle, von, bis) == 5 * 60
    assert abgedeckte_minuten([], von, bis) == 0


def test_epgshare_de_uebernimmt_sendepause_als_korrekte_daten(_epgshare_de_cache_zuruecksetzen):
    heute = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'
        '<channel id="Sky.Sport.2.de"><display-name>Sky Sport 2</display-name></channel>\n'
        f'<programme start="{heute}000000 +0000" stop="{heute}040000 +0000" channel="Sky.Sport.2.de">'
        '<title>Sendepause</title></programme>\n'
        f'<programme start="{heute}040000 +0000" stop="{heute}060000 +0000" channel="Sky.Sport.2.de">'
        '<title>Fussball: Bundesliga</title></programme>\n</tv>'
    ).encode("utf-8")
    with patch("quellen.epgshare_de_epg.requests.get", side_effect=_epgshare_de_antworten({"DE1": xml})):
        site_id = epgshare_de_epg.epgshare_de_kanal_finden("SKY SPORT 2")
        programme = epgshare_de_epg.epgshare_de_hole_programme(site_id, tage=1)
    assert [p["title"] for p in programme] == ["Sendepause", "Fussball: Bundesliga"]


def test_epgshare_de_ignoriert_klammerzusatz_und_sternchen_im_playlist_namen(_epgshare_de_cache_zuruecksetzen):
    feeds = {"DE1": _epgshare_de_xml([("Sky.Sport.10.de", "Sky Sport 10")])}
    with patch("quellen.epgshare_de_epg.requests.get", side_effect=_epgshare_de_antworten(feeds)):
        for name in (
            "SKY SPORT 10 HD (NUR WÄHREND DER LIVE SPIELE)",
            "SKY SPORT 10 FHD* (NUR WÄHREND DER LIVE SPIELE)",
            "SKY SPORT 10 HEVC",
        ):
            assert epgshare_de_epg.epgshare_de_kanal_finden(name) == "DE1:Sky.Sport.10.de", name


def test_epgshare_de_alias_sky_cinema_highlight_und_sky_sports_f1(_epgshare_de_cache_zuruecksetzen):
    feeds = {"DE1": _epgshare_de_xml([
        ("Sky.Cinema.Highlights.HD.de", "Sky Cinema Highlights HD"), ("Sky.Sport.F1.de", "Sky Sport F1"),
    ])}
    with patch("quellen.epgshare_de_epg.requests.get", side_effect=_epgshare_de_antworten(feeds)):
        assert epgshare_de_epg.epgshare_de_kanal_finden("SKY CINEMA HIGHLIGHT HD") == "DE1:Sky.Cinema.Highlights.HD.de"
        assert epgshare_de_epg.epgshare_de_kanal_finden("SKY CINEMA HIGHLIGHT HEVC") == "DE1:Sky.Cinema.Highlights.HD.de"
        assert epgshare_de_epg.epgshare_de_kanal_finden("SKY SPORTS F1 FHD") == "DE1:Sky.Sport.F1.de"


# ---------------------------------------------------------------------------
# Playlist-genaue Kanal-IDs (epg_lib.playlist_exakte_namen_sammeln /
# ids_auf_playlist_einschraenken)
# ---------------------------------------------------------------------------

import re as _re
from epg_lib import playlist_exakte_namen_sammeln, ids_auf_playlist_einschraenken

_SONDER = _re.compile("[\t\xa0\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")

_M3U_BEISPIEL = (
    "#EXTM3U\r\n"
    '#EXTINF:-1 tvg-id="" tvg-name="UK| BBC ONE" group-title="UK",UK| BBC ONE\r\n'
    "http://x/1\r\n"
    '#EXTINF:-1 tvg-id="" tvg-name="EN|  EPIX" group-title="EN",EN|  EPIX\r\n'
    "http://x/2\r\n"
    '#EXTINF:-1 tvg-id="x1" tvg-name="" group-title="US",US| NESN HD (bk) \r\n'
    "http://x/3\r\n"
    '#EXTINF:-1 tvg-id="" tvg-name="" group-title="NHL",NHL | 05 - Spiel, mit Komma\r\n'
    "http://x/4\r\n"
)


def test_playlist_namen_exakt_inkl_leerzeichen_komma_und_attribute():
    namen = playlist_exakte_namen_sammeln(_M3U_BEISPIEL)
    assert "UK| BBC ONE" in namen
    assert "EN|  EPIX" in namen            # zwei Leerzeichen bleiben erhalten
    assert "EN| EPIX" not in namen
    assert "US| NESN HD (bk) " in namen    # nachlaufendes Leerzeichen bleibt
    assert "NHL | 05 - Spiel, mit Komma" in namen
    assert "x1" in namen                   # tvg-id


def test_ids_einschraenken_behaelt_nur_playlist_varianten():
    namen = playlist_exakte_namen_sammeln(_M3U_BEISPIEL) | {f"n{i}" for i in range(10)}
    varianten = ["UK|BBC ONE", "UK| BBC ONE", "UK|  BBC ONE", "UK-NOWTV| BBC ONE", "UK-BBCI| BBC ONE"]
    assert ids_auf_playlist_einschraenken(varianten, namen, 5, _SONDER) == ["UK| BBC ONE"]


def test_ids_einschraenken_ohne_treffer_oder_zu_kleine_playlist_behaelt_alle():
    varianten = ["UK|X", "UK| X", "UK|  X"]
    namen = frozenset({"ganz anderer Name"} | {f"n{i}" for i in range(10)})
    assert ids_auf_playlist_einschraenken(varianten, namen, 5, _SONDER) == varianten      # kein Treffer
    assert ids_auf_playlist_einschraenken(varianten, frozenset({"UK| X"}), 5, _SONDER) == varianten  # Playlist zu klein
    assert ids_auf_playlist_einschraenken(["EINZIG"], namen, 5, _SONDER) == ["EINZIG"]    # nur eine Variante


def test_ids_einschraenken_laesst_sender_mit_sonderzeichen_oder_anfuehrungszeichen_unberuehrt(_=None):
    namen = frozenset({"US| THE BLAZE\xa0HD"} | {f"n{i}" for i in range(10)})
    # Die vom Player normalisierte Variante ("US| THE BLAZE HD") steht NICHT roh in der Playlist,
    # ist aber die, die TiviMate trifft -> Sender mit Sonderzeichen werden gar nicht eingeschraenkt.
    varianten = ["US| THE BLAZE\xa0HD", "US| THE BLAZE HD", "US|THE BLAZE HD"]
    assert ids_auf_playlist_einschraenken(varianten, namen, 5, _SONDER) == varianten
    namen2 = frozenset({'US| "X" Y'} | {f"n{i}" for i in range(10)})
    varianten2 = ['US| "X" Y', "US| ", "US|  "]
    assert ids_auf_playlist_einschraenken(varianten2, namen2, 5, _SONDER) == varianten2


def test_ids_einschraenken_laesst_header_kanaele_unveraendert():
    namen = frozenset({"##### 24/7 COMEDY VIP #####"} | {f"n{i}" for i in range(10)})
    varianten = ["##### 24/7 COMEDY VIP #####", "##### 24/7 COMEDY \u2c7d\u1d35\u1d3e #####"]
    assert ids_auf_playlist_einschraenken(varianten, namen, 5, _SONDER) == varianten
    namen2 = frozenset({"### WOW SPORT ###"} | {f"n{i}" for i in range(10)})
    varianten2 = ["### WOW SPORT ###", "### WOW SPORT  ###", "###  WOW SPORT ###"]
    assert ids_auf_playlist_einschraenken(varianten2, namen2, 5, _SONDER) == varianten2


# --- Regional Fernsehen Oberbayern (rfo.de), Oktober 2026 ---

def _rfo_html(eintraege):
    """Baut Mini-HTML mit doppelt escapten JSON-Eintraegen wie auf rfo.de,
    inklusive vorangestelltem fremdem Objekt (darf nie als Titel landen)."""
    teile = ['{"title":"Livestream","meta":[],"blocks":[{"x":1}]}']
    for titel, von, bis, beschr, datum in eintraege:
        teile.append(
            '{"title":"%s","from":"%s","to":"%s","description":"%s","date":"%s","time":"00:00:00.00"}'
            % (titel, von, bis, beschr, datum)
        )
    return "<html>" + ",".join(teile) + "</html>"


def test_rfo_kanal_treffer_nur_oberbayern():
    from quellen.rfo_epg import rfo_kanal_treffer
    assert rfo_kanal_treffer("REGIONAL FERNSEHEN OBERBAYERN ᴿᴬᵂ")
    assert rfo_kanal_treffer("Regional Fernsehen Oberbayern HD")
    assert not rfo_kanal_treffer("RFH Regionalfernsehen Harz")
    assert not rfo_kanal_treffer("ZDF")


def test_rfo_parst_doppelt_escapte_eintraege_mit_mitternacht_und_umlauten():
    from quellen import rfo_epg
    heute = datetime.datetime.now(rfo_epg.BERLIN_TZ).date()
    datum = heute.strftime("%Y.%m.%d")
    html_text = _rfo_html([
        ("S\\\\u00fcd Journal (Wh.)", "10:00", "10:10", "Beschr \\\\u201eA\\\\u201c", datum),
        ("S\\\\u00fcd Kultur", "23:45", "00:00", "", datum),
    ])
    antwort = MagicMock()
    antwort.text = html_text
    antwort.raise_for_status = lambda: None
    rfo_epg._programme_cache = None
    with patch("quellen.rfo_epg._http.mit_retry", return_value=antwort):
        programme = rfo_epg.rfo_hole_programme(7)
    rfo_epg._programme_cache = None
    assert [p["title"] for p in programme] == ["Süd Journal (Wh.)", "Süd Kultur"]
    assert programme[0]["beschreibung"] == "Beschr „A“"
    # Sendung ueber Mitternacht endet am Folgetag, nicht vor dem Start
    assert programme[1]["stop"] - programme[1]["start"] == datetime.timedelta(minutes=15)


def test_rfo_degradiert_bei_netzwerkfehler_auf_leere_liste():
    from quellen import rfo_epg
    rfo_epg._programme_cache = None
    with patch("quellen.rfo_epg._http.mit_retry", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert rfo_epg.rfo_hole_programme(7) == []
    rfo_epg._programme_cache = None


# --- epgshare01 RS1/BA1 fuer Ex-YU-Sender (epgshare_balkan_epg.py), Oktober 2026 ---

def _balkan_feed_gz(kanal_id, anzeigename, anzahl=12):
    start = datetime.datetime.now(datetime.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    teile = [f'<tv><channel id="{kanal_id}"><display-name>{anzeigename}</display-name></channel>']
    for i in range(anzahl):
        s = start + datetime.timedelta(hours=i)
        e = s + datetime.timedelta(hours=1)
        teile.append(
            f'<programme start="{s.strftime("%Y%m%d%H%M%S")} +0000" stop="{e.strftime("%Y%m%d%H%M%S")} +0000" '
            f'channel="{kanal_id}"><title>Sendung {i}</title></programme>'
        )
    teile.append("</tv>")
    return gzip.compress("".join(teile).encode("utf-8"))


def test_epgshare_balkan_normierung_ignoriert_zusaetze_und_diakritika():
    from quellen.epgshare_balkan_epg import _norm
    assert _norm("TV ZVEZDA ⱽᴵᴾ ᴿᴬᵂ") == _norm("Zvezda TV") == "ZVEZDA"
    assert _norm("ZADRUGA 2") == _norm("Zadruga Live 2 (BIH)") == "ZADRUGA2"
    assert _norm("UNA HD") == _norm("UNA TV") == "UNA"
    assert _norm("Šaržo Đurđev") == _norm("Sarzo Durdev")


def test_epgshare_balkan_findet_nur_exakt_und_nur_fuer_exyu_laender():
    from quellen import epgshare_balkan_epg as m
    antwort = MagicMock()
    antwort.content = _balkan_feed_gz("Zvezda.TV.rs", "Zvezda TV")
    antwort.raise_for_status = lambda: None
    m._daten_cache = None
    with patch("quellen.epgshare_balkan_epg._http.mit_retry", return_value=antwort):
        sid = m.epgshare_balkan_kanal_finden("TV ZVEZDA VIP RAW", "RS")
        assert sid is not None and sid.endswith(":Zvezda.TV.rs")
        assert len(m.epgshare_balkan_hole_programme(sid, 3)) >= 10
        assert m.epgshare_balkan_kanal_finden("TV ZVEZDA", "EXYU") == sid
        assert m.epgshare_balkan_kanal_finden("TV ZVEZDA", "BS") is None   # Film-Rubriken ausgeschlossen
        assert m.epgshare_balkan_kanal_finden("TV ZVEZDA", "DE") is None   # nur Ex-YU-Laender
        assert m.epgshare_balkan_kanal_finden("TV ZVEZDA PLUS", "RS") is None  # kein Fuzzy-Treffer
    m._daten_cache = None


def test_epgshare_balkan_degradiert_bei_netzwerkfehler():
    from quellen import epgshare_balkan_epg as m
    m._daten_cache = None
    with patch("quellen.epgshare_balkan_epg._http.mit_retry", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert m.epgshare_balkan_kanal_finden("TV ZVEZDA", "RS") is None
        assert m.epgshare_balkan_hole_programme("RS1:Zvezda.TV.rs", 3) == []
    m._daten_cache = None


# --- Generischer Platzhalter-Titel (schoener_sendername), Oktober 2026 ---

def test_schoener_sendername_entfernt_qualitaet_klammern_und_marker():
    from epg_lib import schoener_sendername as f
    assert f("STARS IN GEFAHR ᴿᴬᵂ") == "Stars in Gefahr"
    assert f("LANDLUST-TV-HD ᴿᴬᵂ") == "Landlust TV"
    assert f("NFL NETWORK (N573) ROANOKE") == "NFL Network Roanoke"
    assert f("COLORS HEVC FHD") == "Colors"
    assert f("DAZN BAR 1 FHD*") == "DAZN Bar 1"
    assert f("ESPN 2 ᴴᴰ ²⁵ᶠᵖˢ") == "ESPN 2"
    assert f("RTV USK ⱽᴵᴾ ᴿᴬᵂ") == "RTV USK"
    assert f("TV| A&E ᴿᴬᵂ") == "A&E"
    assert f("UK| BBC ONE EAST") == "BBC One East"


def test_schoener_sendername_grossschreibung_und_sonderfaelle():
    from epg_lib import schoener_sendername as f
    assert f("HBO EAST") == "HBO East" and f("CNN") == "CNN" and f("N1 HR") == "N1 HR"
    assert f("3SAT") == "3Sat" and f("ABC7 NEW YORK") == "ABC7 New York"
    assert f("US: ESPN+ PPV 1") == "US: ESPN+ PPV 1"
    # Bleibt nach der Bereinigung fast nichts uebrig, bleiben die Zusaetze stehen
    assert f("24 4K") == "24 4K"
    assert f("") == ""


def test_ist_automatischer_platzhaltertitel_nur_fuer_alte_auto_texte():
    from epg_lib import ist_automatischer_platzhaltertitel as g
    assert g("Sr Hd ᴸⁱᵛᵉ", "SR HD")
    assert g("20/20 ᴿᴬᵂ ᴸⁱᵛᵉ", "TV| 20/20 ᴿᴬᵂ")
    assert not g("MySports 2 - Kein Live Spiel", "MYSPORTS 2 HD")      # handgeschrieben
    assert not g("Sport Live ᴸⁱᵛᵉ", "SPORT1")        # anderer Name
    assert not g("", "SR HD")


def test_schnelle_zeit_parser_wie_strptime():
    """quellen/_zeit.py muss exakt dieselben Ergebnisse (und bei ungueltigen
    Texten dieselben Fehler) liefern wie datetime.strptime."""
    import random
    from datetime import datetime, timezone
    from quellen._zeit import xmltv_zeit_zu_utc, naive_zeit_sekunden, naive_zeit_minuten

    zufall = random.Random(42)
    for _ in range(2000):
        j = zufall.randint(2020, 2030)
        mo, t = zufall.randint(1, 12), zufall.randint(1, 28)
        h, mi, s = zufall.randint(0, 23), zufall.randint(0, 59), zufall.randint(0, 59)
        vz = zufall.choice("+-")
        oh, om = zufall.choice([(0, 0), (1, 0), (2, 0), (5, 30), (9, 45), (11, 0)])
        text = f"{j}{mo:02d}{t:02d}{h:02d}{mi:02d}{s:02d} {vz}{oh:02d}{om:02d}"
        erwartet = datetime.strptime(text, "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
        assert xmltv_zeit_zu_utc(text) == erwartet
        assert xmltv_zeit_zu_utc("  " + text + " ") == erwartet
        iso = f"{j}-{mo:02d}-{t:02d} {h:02d}:{mi:02d}:{s:02d}"
        assert naive_zeit_sekunden(iso) == datetime.strptime(iso, "%Y-%m-%d %H:%M:%S")
        iso2 = f"{j}-{mo:02d}-{t:02d} {h:02d}:{mi:02d}"
        assert naive_zeit_minuten(iso2) == datetime.strptime(iso2, "%Y-%m-%d %H:%M")


def test_schnelle_zeit_parser_sonderfaelle_und_fehler():
    from datetime import datetime, timezone
    import pytest
    from quellen._zeit import xmltv_zeit_zu_utc, naive_zeit_sekunden, naive_zeit_minuten

    # Offsetformen ausserhalb des schnellen Musters laufen ueber den Rueckfall
    assert xmltv_zeit_zu_utc("20261011200000 +0200") == datetime(2026, 10, 11, 18, 0, tzinfo=timezone.utc)
    assert xmltv_zeit_zu_utc("20261011200000 +02:00") == datetime(2026, 10, 11, 18, 0, tzinfo=timezone.utc)
    assert xmltv_zeit_zu_utc("20261011200000 -0500") == datetime(2026, 10, 12, 1, 0, tzinfo=timezone.utc)
    # Datumsgrenze
    assert xmltv_zeit_zu_utc("20261231233000 -0200") == datetime(2027, 1, 1, 1, 30, tzinfo=timezone.utc)
    # Ungueltiges wirft wie strptime (ValueError)
    for kaputt in ("", "abc", "20261311200000 +0200", "20261011250000 +0200", "20261011200000"):
        with pytest.raises(ValueError):
            xmltv_zeit_zu_utc(kaputt)
    with pytest.raises(ValueError):
        naive_zeit_sekunden("2026-10-11 20:15")      # ohne Sekunden: wie strptime ungueltig
    with pytest.raises(ValueError):
        naive_zeit_minuten("2026-10-11 20:15:30")    # mit Sekunden: wie strptime ungueltig
    with pytest.raises(ValueError):
        naive_zeit_minuten("2026-13-01 10:00")


def test_deswird_schnellpfad_und_vollparse_liefern_identische_sendungen():
    """Der schnelle Ladepfad (Kanalliste per ET, Programmbloecke als Rohbytes,
    erst bei Bedarf geparst) muss exakt dasselbe liefern wie der Voll-Parse,
    auch bei XML-Entities in der Kanal-ID (&amp;)."""
    from quellen import deswird_epg
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'
        '<channel id="A&amp;B.de"><display-name>A und B</display-name></channel>\n'
        '<channel id="C.de"><display-name>Cee</display-name></channel>\n'
        '<programme start="20261006233500 +0000" stop="20261007002000 +0000" channel="A&amp;B.de">\n'
        '<title>Serie</title><sub-title>Folge Eins</sub-title><desc>Text\n  mit   Umbruch</desc>'
        '<icon src="http://x/y.png"/></programme>\n'
        '<programme start="20261007002000 +0000" stop="20261007010000 +0000" channel="C.de">\n'
        '<title>Film \xc3\xa4</title></programme>\n'
        '<programme start="kaputt" stop="20261007010000 +0000" channel="C.de"><title>X</title></programme>\n'
        '</tv>\n'
    ).encode("latin-1").decode("utf-8", "ignore").encode("utf-8")

    def laden(schnell):
        deswird_epg._daten_cache = None
        antwort = MagicMock(content=xml)
        antwort.raise_for_status = lambda: None
        orig = deswird_epg._schnell_laden
        if not schnell:
            deswird_epg._schnell_laden = lambda b: (_ for _ in ()).throw(ValueError("aus"))
        try:
            with patch("quellen.deswird_epg._http.mit_retry", return_value=antwort):
                daten = deswird_epg._xml_laden()
            return daten, {k: deswird_epg._programme_fuer_kanal(daten, k) for k in ("A&B.de", "C.de", "gibt.es.nicht")}
        finally:
            deswird_epg._schnell_laden = orig
            deswird_epg._daten_cache = None

    d_schnell, p_schnell = laden(True)
    d_voll, p_voll = laden(False)
    assert d_schnell["roh"] and not d_voll["roh"]
    assert d_schnell["kanaele"] == d_voll["kanaele"]
    assert p_schnell == p_voll
    assert len(p_schnell["A&B.de"]) == 1 and len(p_schnell["C.de"]) == 1
    assert p_schnell["gibt.es.nicht"] == []


def _epgshare_testfeed():
    """Kleiner XMLTV-Feed: ein Kanal mit 12 gueltigen Sendungen und
    &apos; in der ID, ein Kanal mit nur 3 (Platzhalter), ein Kanal mit
    12 Eintraegen, von denen nur 9 gueltig sind (leerer Titel/stop<=start)."""
    zeilen = ['<?xml version="1.0" encoding="UTF-8"?>', "<tv>"]
    zeilen.append('<channel id="L&apos;Equipe.ch"><display-name>L\'Equipe</display-name></channel>')
    zeilen.append('<channel id="kurz.de"><display-name>Kurz</display-name></channel>')
    zeilen.append('<channel id="knapp.de"><display-name>Knapp</display-name></channel>')
    for i in range(12):
        zeilen.append(
            f'<programme start="2026101{i % 10}100000 +0000" stop="2026101{i % 10}110000 +0000" channel="L&apos;Equipe.ch">'
            f'<title>Sendung &amp; Co {i}</title><desc>Text {i}</desc></programme>'
        )
    for i in range(3):
        zeilen.append(
            f'<programme start="2026102{i}100000 +0000" stop="2026102{i}110000 +0000" channel="kurz.de"><title>K{i}</title></programme>'
        )
    for i in range(12):
        titel = "<title></title>" if i < 2 else f"<title>T{i}</title>"
        tag = 10 + i
        stop = f"202610{tag}100000 +0000" if i == 2 else f"202610{tag}110000 +0000"
        zeilen.append(
            f'<programme start="202610{tag}100000 +0000" stop="{stop}" channel="knapp.de">{titel}</programme>'
        )
    zeilen.append("</tv>")
    return "\n".join(zeilen).encode("utf-8")


def test_epgshare_schnellpfad_identisch_zum_vollparse():
    """_feed_parsen (lazy) muss Kanalliste (inkl. Mindestanzahl GUELTIGER
    Sendungen und &apos;-IDs) und Sendungen exakt wie der Voll-Parse liefern."""
    from quellen import epgshare_de_epg
    xml = _epgshare_testfeed()
    k_schnell, p_schnell = epgshare_de_epg._feed_parsen("DE1", xml)
    k_voll, p_voll = epgshare_de_epg._feed_parsen_voll("DE1", xml)
    assert p_schnell._roh and not p_voll._roh
    assert k_schnell == k_voll
    sites = {k["site_id"] for k in k_schnell}
    assert sites == {"DE1:L'Equipe.ch"}  # kurz.de (3) und knapp.de (9 gueltig) unter 10
    for schluessel in ("DE1:L'Equipe.ch", "DE1:kurz.de", "DE1:knapp.de", "DE1:gibt.es.nicht"):
        assert p_schnell.get(schluessel, []) == p_voll.get(schluessel, [])
    assert len(p_schnell.get("DE1:knapp.de")) == 9


def test_epgshare_schnellpfad_faellt_bei_unbekanntem_format_auf_vollparse_zurueck():
    from quellen import epgshare_de_epg
    xml = _epgshare_testfeed().replace(b'encoding="UTF-8"', b'encoding="ISO-8859-1"')
    kanaele, programme = epgshare_de_epg._feed_parsen("DE1", xml)
    assert not programme._roh
    assert {k["site_id"] for k in kanaele} == {"DE1:L'Equipe.ch"}
    assert len(programme.get("DE1:L'Equipe.ch")) == 12


def test_kanal_index_suchen_rtl_comedy_kein_fuzzy_auf_tnt_comedy():
    import epg_lib
    index = {"TNTCOMEDY": "tntcomedy", "COMEDYCENTRAL": "comedycentral"}
    assert epg_lib.kanal_index_suchen("RTL COMEDY", index) is None
    assert epg_lib.kanal_index_suchen("RTL Comedy HD", index) is None
    assert epg_lib.kanal_index_suchen("TNT Comedy", index) == "tntcomedy"


def test_fuzzy_treffer_plausibel_qualitaet_egal_aber_fremdkanaele_abgelehnt():
    import epg_lib
    ok = epg_lib.fuzzy_treffer_plausibel
    # Qualitaets-Suffixe und SPORT/SPORTS sind egal
    assert ok("SKY SPORTS F1 FHD", "SKYSPORTF1HD")
    assert ok("ANIMAL PLANET FHD", "ANIMALPLANETHD")
    assert ok("SKY SPORT NEWS HEVC", "SKYSPORTNEWSHD")
    # Fremdkanaele: andere Marke, andere Zahl, zu kurz
    assert not ok("RTL COMEDY", "TNTCOMEDY")
    assert not ok("NHL NETWORK", "NFLNETWORK")
    assert not ok("ARENA SPORT 2", "MAGENTASPORT")
    assert not ok("SKY SPORT AUSTRIA 2", "SKYSPORTAUSTRIA1")
    assert not ok("RTL 2", "RTL")
    assert not ok("ROCKY", "ROCK")
    assert not ok("PROSIEBEN FHD", "PROSIEBENFUN")
    assert not ok("PROSIEBEN", "PROSIEBENMAXX")


def test_ids_einschraenken_behaelt_standard_schreibweise_mit_einem_leerzeichen():
    import re, epg_lib
    varianten = ["UK|AMAZON UK EVENT 0", "UK| AMAZON UK EVENT 0",
                 "UK|  AMAZON UK EVENT 0", "UK-NOWTV| AMAZON UK EVENT 0"]
    playlist = frozenset(["UK|AMAZON UK EVENT 0"] + [f"x{i}" for i in range(6000)])
    sonder = re.compile("[​]")
    standard = re.compile(r"^[A-Za-z]{2,5}\| \S")
    # ohne immer_regex: nur die Playlist-Variante (bisheriges Verhalten)
    assert epg_lib.ids_auf_playlist_einschraenken(varianten, playlist, 5000, sonder) == [
        "UK|AMAZON UK EVENT 0"]
    # mit immer_regex: zusaetzlich die Ein-Leerzeichen-Standardvariante
    assert epg_lib.ids_auf_playlist_einschraenken(varianten, playlist, 5000, sonder, standard) == [
        "UK|AMAZON UK EVENT 0", "UK| AMAZON UK EVENT 0"]


def test_fuzzy_treffer_plausibel_echte_varianten_bleiben_erhalten():
    import epg_lib
    ok = epg_lib.fuzzy_treffer_plausibel
    # Regression 12.10.2026: diese echten Treffer wurden zu Unrecht abgelehnt
    assert ok("ARENA SPORT PREMIUM 1 VIP RAW", "ARENAPREMIUM1")
    assert ok("ARENA SPORT 3 PREMIUM", "ARENAPREMIUM3")
    assert ok("ARENA M1 PREMIUM FHD", "ARENAPREMIUM1")
    assert ok("COMEDY CENTRAL EAST HD", "COMEDYCENTRAL")
    assert ok("HAYAT FOLK", "HAYATFOLKBOX")
    assert ok("BHT", "BHT1")
    assert ok("NICKELODEON EAST", "NICKELODEON")
    # und die Fehltreffer bleiben abgelehnt
    assert not ok("PROSIEBEN", "PROSIEBENMAXX")
    assert not ok("RTL 2", "RTL")
    assert not ok("RTL2", "RTL")
    assert not ok("ARENA SPORT 3 PREMIUM", "ARENASPORT3")
    assert not ok("ARENA SPORT 2", "MAGENTASPORT")
    assert not ok("MYSPORTS 1", "SKYSPORTNEWS")
    assert not ok("NOW ROCK", "ROCK")


def test_kanal_index_suchen_alias_rtl_ii_und_zwel_auf_rtl_zwei():
    import epg_lib
    index = {"RTLZWEI": "rtlzwei", "RTL": "rtl"}
    kern = {"RTLZWEI": "rtlzwei", "RTL": "rtl"}
    assert epg_lib.kanal_index_suchen("RTL II HEVC", index, kern) == "rtlzwei"
    assert epg_lib.kanal_index_suchen("RTL ZWEL ᴿᴬᵂ", index, kern) == "rtlzwei"
    assert epg_lib.kanal_index_suchen("RTL ZWEI", index, kern) == "rtlzwei"
    # "RTL 2" (HR/MO) bleibt ein anderer Sender
    assert epg_lib.kanal_index_suchen("RTL 2", {"RTL": "rtl"}, {"RTL": "rtl"}) != "rtlzwei"


def test_fuzzy_treffer_plausibel_sky_uk_abkuerzungen():
    import epg_lib
    ok = epg_lib.fuzzy_treffer_plausibel
    n = epg_lib.normalisiere_sendername
    # Sky UK fuehrt Kanaele mit abgekuerzten Namen (12.10.2026)
    assert ok("SKY SPORTS F1 FHD", n("SkySp F1 HD"))
    assert ok("SKY SPORTS CRICKET HD", n("SkySpCricket HD"))
    assert ok("SKY SPORTS FOOTBALL", n("SkySp F'ball"))
    assert ok("SKY SPORTS + HD", n("SkySp+ HD"))
    assert ok("SKY CINEMA ACTION FHD", n("Sky Action HD"))
    assert ok("SKY CINEMA PREMIERE HD", n("SkyPremiereHD"))
    assert ok("SKY DOCUMENTARIES HD", n("SkyDocmntrsHD"))
    assert ok("SKY ARTS 1 FHD", n("Sky Arts HD"))
    assert ok("PREMIER SPORTS 1 FHD", n("Premier 1 HD"))
    # Fehltreffer bleiben abgelehnt
    assert not ok("SKY STORE PREMIERE 5", n("SkyPremiereHD"))
    assert not ok("SKY MAX FHD", n("Sky Mix HD"))
    assert not ok("SKY SPORTS ACTION HD", n("SkySp Racing HD"))
    assert not ok("RTL 2", "RTL")


def test_fuzzy_treffer_plausibel_tv_position_und_crime_investigation():
    import epg_lib
    ok = epg_lib.fuzzy_treffer_plausibel
    assert ok("SITEL", "TVSITEL")
    assert ok("JADRAN TV", "TVJADRAN")
    assert ok("SLO 3", "TVSLO3")
    assert ok("CRIME &amp; INVESTIGATION HD", "CRIMEPLUSINVESTIGATIOND")
    assert not ok("TV 21", "RTV21")
    assert not ok("SABORSKA TV", "SLAVONSKATV")


def test_epgshare_balkan_alias_zadruga_24h_auf_live():
    from quellen import epgshare_balkan_epg as b
    assert b._alias_schluessel(b._norm("ZADRUGA 24 H 1")) == "ZADRUGA1"
    assert b._alias_schluessel(b._norm("ZADRUGA 24 H 3")) == "ZADRUGA3"
    assert b._alias_schluessel(b._norm("ZADRUGA 2")) == "ZADRUGA2"
    assert b._alias_schluessel(b._norm("ZADRUGA LIVE")) == "ZADRUGA"


def test_zuordnung_luecken_bericht():
    import epg_lib
    m3u = (
        '#EXTM3U\n'
        '#EXTINF:-1 tvg-id="" tvg-name="DE| RTL" group-title="DE| ALLGEMEIN",DE| RTL\n'
        'http://x/1\n'
        '#EXTINF:-1 group-title="UK| AMAZON",UK| AMAZON UK EVENT 0\n'
        'http://x/2\n'
        '#EXTINF:-1 group-title="DE| ALLGEMEIN",DE| UNBEKANNT HD\n'
        'http://x/3\n'
        '#EXTINF:-1 group-title="X",##### HEADER #####\n'
        'http://x/4\n'
        '#EXTINF:-1 group-title="NETFLIX MOVIES",Film A\n'
        'http://h:80/movie/u/p/1.mkv\n'
        '#EXTINF:-1 group-title="SERIEN",Serie B\n'
        'http://h:80/series/u/p/2.mkv\n'
    )
    kanaele = epg_lib.playlist_kanaele_sammeln(m3u)
    assert [k["name"] for k in kanaele] == [
        "DE| RTL", "UK| AMAZON UK EVENT 0", "DE| UNBEKANNT HD", "##### HEADER #####"]
    assert kanaele[1]["gruppe"] == "UK| AMAZON"
    xml = ('<tv> <channel id="DE| RTL"> <display-name>DE| RTL</display-name> </channel> '
           '<channel id="UK|AMAZON UK EVENT 0"> <display-name>UK| AMAZON UK EVENT 0 x</display-name> </channel> </tv>')
    namen = epg_lib.xml_kanal_namen(xml)
    exakt, nicht = epg_lib.zuordnung_luecken(kanaele, namen)
    # Amazon: nur in anderer Schreibweise (ohne Leerzeichen) vorhanden -> exakt fehlt, tolerant ok
    assert [k["name"] for k in exakt] == ["UK| AMAZON UK EVENT 0", "DE| UNBEKANNT HD"]
    assert [k["name"] for k in nicht] == ["DE| UNBEKANNT HD"]
    text = epg_lib.zuordnung_luecken_bericht(kanaele, namen)
    assert "Playlist-Kanaele gesamt: 4" in text
    assert "DE| UNBEKANNT HD" in text and "HEADER" not in text


# --- rtvbn.tv (BN TV / BN2 / BN Music) ---

_RTVBN_HTML = """
<div class="row showHide showHide%d">
 <h3>Program BN</h3><div class="frequency_box"><ul>
  <li>
   <span>07:20</span>
   <b>Folklor magazin</b>
   <br>
   <em class="program-category">Muzicki program</em>
  </li>
  <li>
   <span>08:00</span>
   <b>Dnevnik</b>
  </li>
 </ul></div>
 <h3>Program BN 2</h3><div class="frequency_box"><ul>
  <li><span>08:50</span><b>Poreznik Gavro</b></li>
 </ul></div>
 <h3>Program BN Music</h3><div class="frequency_box"><ul>
  <li><span>09:00</span><b>Narodna muzika</b></li>
 </ul></div>
</div>
"""


@pytest.mark.parametrize("name,erwartet", [
    ("BN TV ⱽᴵᴾ ᴿᴬᵂ", "Program BN"),
    (" BN TV HD", "Program BN"),
    ("BN2 TV", "Program BN 2"),
    ("BN MUSIC", "Program BN Music"),
    ("BN Plus", None),
    ("BHT", None),
])
def test_rtvbn_kanal_finden(name, erwartet):
    from quellen.rtvbn_epg import rtvbn_kanal_finden
    assert rtvbn_kanal_finden(name) == erwartet


def test_rtvbn_parser_neues_layout(monkeypatch):
    from quellen import rtvbn_epg

    class _Antwort:
        text = "".join(_RTVBN_HTML % i for i in range(7))

        def raise_for_status(self):
            pass

    monkeypatch.setattr(rtvbn_epg._http, "mit_retry", lambda *a, **k: _Antwort())
    monkeypatch.setattr(rtvbn_epg, "_programme_cache", None)
    daten = rtvbn_epg._alle_tage_laden()
    assert len(daten["Program BN"]) == 14
    assert len(daten["Program BN 2"]) == 7
    assert len(daten["Program BN Music"]) == 7
    assert daten["Program BN"][0]["title"] in ("Folklor magazin", "Dnevnik")
    assert any("Muzicki program" in p["beschreibung"] for p in daten["Program BN"])
    monkeypatch.setattr(rtvbn_epg, "_programme_cache", None)


# --- Quellen-Ueberwachung ---

def test_quellen_gesundheit_einbruch_wird_gemeldet():
    from epg_lib import quellen_gesundheit_pruefen
    alt = {"BN (rtvbn.tv)": {"referenz": 5, "zuletzt_ok": "2026-10-14T01:00:00+00:00", "aktuell": 5}}
    neu, warn = quellen_gesundheit_pruefen(alt, {}, "2026-10-15T01:00:00+00:00")
    assert len(warn) == 1 and "BN (rtvbn.tv)" in warn[0]
    assert neu["BN (rtvbn.tv)"]["referenz"] == 5  # Referenz bleibt auf letztem guten Wert


def test_quellen_gesundheit_normal_und_kleine_quellen_still():
    from epg_lib import quellen_gesundheit_pruefen
    alt = {"A": {"referenz": 100, "zuletzt_ok": "2026-10-14T01:00:00+00:00", "aktuell": 100},
           "B": {"referenz": 2, "zuletzt_ok": "2026-10-14T01:00:00+00:00", "aktuell": 2}}
    neu, warn = quellen_gesundheit_pruefen(alt, {"A": 80, "B": 0}, "2026-10-15T01:00:00+00:00")
    assert warn == []  # A nur -20 %, B unter min_referenz
    assert neu["A"]["referenz"] == 80


def test_quellen_gesundheit_dauerhaft_wird_neue_referenz():
    from epg_lib import quellen_gesundheit_pruefen
    alt = {"A": {"referenz": 50, "zuletzt_ok": "2026-09-01T00:00:00+00:00", "aktuell": 0}}
    neu, warn = quellen_gesundheit_pruefen(alt, {"A": 10}, "2026-10-15T00:00:00+00:00")
    assert warn == [] and neu["A"]["referenz"] == 10


def test_quellen_gesundheit_kaputter_status_wirft_nicht():
    from epg_lib import quellen_gesundheit_pruefen
    neu, warn = quellen_gesundheit_pruefen("kaputt", {"A": 3}, "kein-datum")
    assert warn == [] and neu["A"]["aktuell"] == 3


def test_parser_layout_verdacht():
    from quellen import _status
    _status._meldungen.clear()
    _status.parser_meldung("ok", 90000, 120)
    _status.parser_meldung("kaputt", 180000, 0)
    _status.parser_meldung("leer", 100, 0)  # zu kleine Seite = kein Layout-Verdacht
    assert _status.layout_verdacht() == [("kaputt", 180000)]
    _status._meldungen.clear()


# --- idjtv.com (IDJ TV / IDJ MUZIKA 24/7) ---

@pytest.mark.parametrize("name,erwartet", [
    ("IDJ TV ⱽᴵᴾ ᴿᴬᵂ", 1),
    ("IDJ MUZIKA 24/7", 1),
    ("IDJ TV", 1),
    ("IDJ KIDS HD", None),
    ("IDJKids HD", None),
])
def test_idjtv_kanal_finden(name, erwartet):
    from quellen.idjtv_epg import idjtv_kanal_finden
    assert idjtv_kanal_finden(name) == erwartet


def test_idjtv_parser():
    import datetime as dt
    from quellen import idjtv_epg
    zeile = (
        '<div class="grid rounded-2xl px-3.5 py-5"><div class="x font-bold">%s</div>'
        '<h3 class="a">\n<a href="u">%s</a></h3><div>%s</div><h3><a href="u">%s</a></h3></div>'
    )
    panel = "".join([
        zeile % ("00:00h", "IDJMASH", "00:00h", "IDJMASH"),
        zeile % ("01:30h", "IDJ RAP", "01:30h", "IDJ RAP"),
    ])
    html_text = "<div x-tabs:panels>" + "".join("<div x-tabs:panel>" + panel for _ in range(7))
    programme, zeilen = idjtv_epg._html_parsen(html_text, dt.date(2026, 10, 16))
    assert zeilen == 14 and len(programme) == 14
    assert programme[0]["title"] == "IDJMASH"
    assert programme[0]["stop"] == programme[1]["start"]


def test_mts_zeit_doppelter_offset_wird_abgezogen():
    import datetime as dt
    from quellen.mts_epg import _zeit_parsen
    # Sommer: "Z"-Wert ist 4 h zu spaet (HBO Društvena mreža, 16.10.2026)
    assert _zeit_parsen("2026-10-16T05:38:00.000Z") == dt.datetime(2026, 10, 16, 1, 38, tzinfo=dt.timezone.utc)
    # Winter: doppelter Offset = 2 h
    assert _zeit_parsen("2026-12-16T03:38:00.000Z") == dt.datetime(2026, 12, 16, 1, 38, tzinfo=dt.timezone.utc)
    # zeitzonenlose Werte bleiben Belgrader Lokalzeit (unveraendert)
    assert _zeit_parsen("2026-10-16T03:38:00") == dt.datetime(2026, 10, 16, 1, 38, tzinfo=dt.timezone.utc)
    assert _zeit_parsen("") is None


# --- tvarenasport.mk (ARENA M1/M2/M3 PREMIUM, MK) ---

@pytest.mark.parametrize("name,erwartet", [
    ("ARENA M1 PREMIUM FHD", "M1"),
    ("ARENA M2 PREMIUM", "M2"),
    ("ARENA M3 VIP RAW", "M3"),
    ("ARENA M4", None),
    ("ARENA SPORT 1", None),
    ("ARENA PREMIUM 1", None),
])
def test_arenamk_kanal_finden(name, erwartet):
    from quellen.arenamk_epg import arenamk_kanal_finden
    assert arenamk_kanal_finden(name) == erwartet


def test_arenamk_parser():
    import datetime as dt
    from quellen import arenamk_epg
    zeile = (
        '<div class="tasmk-tvp__row"><span class="tasmk-tvp__time">%s</span>'
        '<span class="tasmk-tvp__sport">Фудбал</span><span class="tasmk-tvp__main">'
        '<span class="tasmk-tvp__title">%s<span class="tasmk-tvp__live">ВО ЖИВО</span></span>'
        '<span class="tasmk-tvp__comp">Лига</span></span></div>'
    )
    html_text = (
        '<section class="tasmk-tvp__ch" data-tvp-ch><img alt="Арена М2 Премиум">'
        '<div data-tvp-day="0" data-tvp-date="2026-10-16">'
        + zeile % ("20:00", "А – Б") + zeile % ("23:30", "В – Г") + zeile % ("00:30", "Д – Е")
        + '</div></section>'
    )
    ergebnis, zeilen = arenamk_epg._html_parsen(html_text)
    assert zeilen == 3 and len(ergebnis["M2"]) == 3
    erste = ergebnis["M2"][0]
    assert erste["title"] == "А – Б"
    # 20:00 Skopje (CEST) = 18:00 UTC; Dauer auf 3 h begrenzt, naechste Sendung 23:30
    assert erste["start"] == dt.datetime(2026, 10, 16, 18, 0, tzinfo=dt.timezone.utc)
    assert erste["stop"] == dt.datetime(2026, 10, 16, 21, 0, tzinfo=dt.timezone.utc)
    # 00:30 liegt nach Mitternacht -> naechster Kalendertag
    assert ergebnis["M2"][2]["start"] == dt.datetime(2026, 10, 16, 22, 30, tzinfo=dt.timezone.utc)
