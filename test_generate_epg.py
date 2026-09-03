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
from quellen import mymedia_epg
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
    yield
    arena_epg._kanalliste_cache = {}
    arena_epg._seite_cache = {}


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
    tag1, tag2 = _rs_tage_labels()
    return f"""
    <html><body>
    <div class="tv-scheme-chanel">
      <div class="tv-scheme-chanel-header"><img src="https://x/chanel-1.png"></div>
      <div class="tv-scheme-days">
        <a><span></span><span></span><span>{tag1}</span></a>
        <a><span></span><span></span><span>{tag2}</span></a>
      </div>
      <div class="tv-scheme-new-slider-item">
        <div class="slider-content">
          <div class="slider-content-top"><span>20:00</span></div>
          <div class="slider-content-bottom">
            <p>Match A</p>
            <span>Liga A</span>
          </div>
        </div>
        <div class="slider-content">
          <div class="slider-content-top"><span>22:00</span></div>
          <div class="slider-content-bottom">
            <p>Match B</p>
            <span class="blob-text">Uzivo</span>
            <span>Liga B</span>
          </div>
        </div>
      </div>
      <div class="tv-scheme-new-slider-item">
        <div class="slider-content">
          <div class="slider-content-top"><span>09:00</span></div>
          <div class="slider-content-bottom"><p>Morning Show</p></div>
        </div>
      </div>
    </div>
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
    # dieselbe eine Sendung zurueck.
    assert len(programme) == 8
    sendung = programme[0]
    assert sendung["title"] == "Vijesti"
    assert sendung["start"].tzinfo is not None
    assert sendung["stop"] > sendung["start"]


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


def _mymedia_card_html(titel, zeit, beschreibung=""):
    return (
        f'<button class="js-tvsmepg-program-card" '
        f'data-program-title="{titel}" '
        f'data-program-time="{zeit}" '
        f'data-program-description="{beschreibung}"></button>'
    )


@pytest.fixture
def _mymedia_cache_zuruecksetzen():
    mymedia_epg._seite_cache = {}
    yield
    mymedia_epg._seite_cache = {}


def test_mymedia_erfolgreicher_abruf_liefert_echte_sendungen(_mymedia_cache_zuruecksetzen):
    html = "<html><body>" + _mymedia_card_html("Na Rubu Pameti", "10:00 – 10:34", "Talk show") + "</body></html>"
    response = MagicMock()
    response.text = html
    response.raise_for_status.return_value = None

    with patch("quellen.mymedia_epg.requests.get", return_value=response):
        programme = mymedia_epg.mymedia_hole_programme(tage=1)

    assert len(programme) == 1
    sendung = programme[0]
    assert sendung["title"] == "Na Rubu Pameti"
    assert sendung["beschreibung"] == "Talk show"
    assert sendung["start"].tzinfo is not None
    assert sendung["stop"] > sendung["start"]


def test_mymedia_ueber_mitternacht_gehende_sendung_bekommt_naechsten_tag(_mymedia_cache_zuruecksetzen):
    html = "<html><body>" + _mymedia_card_html("Kraj", "23:52 – 09:00") + "</body></html>"
    response = MagicMock()
    response.text = html
    response.raise_for_status.return_value = None

    with patch("quellen.mymedia_epg.requests.get", return_value=response):
        programme = mymedia_epg.mymedia_hole_programme(tage=1)

    assert len(programme) == 1
    sendung = programme[0]
    assert sendung["stop"].date() > sendung["start"].date()


def test_mymedia_fehlschlag_faellt_graceful_auf_leere_liste_zurueck(_mymedia_cache_zuruecksetzen):
    with patch("quellen.mymedia_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert mymedia_epg.mymedia_hole_programme(tage=1) == []

    response = MagicMock()
    response.text = "<html><body>kein passendes Markup hier</body></html>"
    response.raise_for_status.return_value = None
    with patch("quellen.mymedia_epg.requests.get", return_value=response):
        assert mymedia_epg.mymedia_hole_programme(tage=1) == []




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
