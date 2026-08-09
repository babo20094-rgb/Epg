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
- Poster-Zuordnung je Kategorie
"""

import datetime
from unittest.mock import patch, MagicMock

import pytest

from epg_lib import (
    KATEGORIEN,
    KATEGORIE_PRIORITAET,
    standard_beschreibung,
    kategorie_label,
    sprache_fuer_land,
    sendetitel,
    datumspraefix,
)

import telemach_epg
import mtel_epg
import sky_epg
import arena_epg
import magenta_epg


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

    with patch("telemach_epg.requests.post", return_value=login_response), \
         patch("telemach_epg.requests.get", side_effect=[channels_response, epg_response, epg_response, epg_response]):
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
    with patch("telemach_epg.requests.post", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert telemach_epg.telemach_login() is None
        assert telemach_epg.telemach_hole_kanalliste("ba") == []
        assert telemach_epg.telemach_kanal_finden("BHT 1", "ba") is None
        assert telemach_epg.telemach_hole_programme("42", "ba", tage=3) == []


def test_telemach_kein_kanal_treffer_gibt_none():
    """Kein passender Kanal in der Telemach-Liste -> None statt
    Exception oder falschem Treffer."""
    login_response = _mock_response({"access_token": "abc123"})
    channels_response = _mock_response([{"id": "1", "name": "Voellig anderer Sender"}])

    with patch("telemach_epg.requests.post", return_value=login_response), \
         patch("telemach_epg.requests.get", return_value=channels_response):
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

    with patch("mtel_epg.requests.get", side_effect=[channels_response, epg_response, epg_response]):
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
    mtel_hole_kanalliste()/mtel_kanal_finden()/mtel_hole_programme() NIE
    werfen, sondern muessen graceful auf leere Ergebnisse zurueckfallen -
    das ist die Grundlage fuer den generischen Fallback in
    generate_epg.py, auch wenn schon Telemach fehlgeschlagen ist."""
    with patch("mtel_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert mtel_epg.mtel_hole_kanalliste() == []
        assert mtel_epg.mtel_kanal_finden("BHT 1") is None
        assert mtel_epg.mtel_hole_programme("iptv#111", tage=2) == []


def test_mtel_kein_kanal_treffer_gibt_none():
    """Kein passender Kanal in der Mtel-Liste -> None statt Exception
    oder falschem Treffer."""
    channels_response = _mock_response({"products": [{"code": "1", "name": "Voellig anderer Sender"}]})

    with patch("mtel_epg.requests.get", return_value=channels_response):
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

    with patch("telemach_epg.requests.post", return_value=telemach_login_response), \
         patch("telemach_epg.requests.get", side_effect=router):
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

    with patch("telemach_epg.requests.post", return_value=telemach_login_response), \
         patch("telemach_epg.requests.get", side_effect=_side_effect):
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

    with patch("telemach_epg.requests.post", return_value=telemach_login_response), \
         patch("telemach_epg.requests.get", side_effect=_side_effect):
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
        "sky_epg.requests.get",
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

    with patch("sky_epg.requests.get", side_effect=[regions_response, services_response]):
        assert sky_epg.sky_kanal_finden("Nicht Existierender Kanal XYZ", "DE") is None

    sky_epg._kanalliste_cache = {}

    with patch("sky_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")):
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

    with patch("sky_epg.requests.get", side_effect=AssertionError("sky_epg haette nicht kontaktiert werden duerfen")):
        for daten in sky_sender_leer:
            sky_epg.sky_kanal_finden(daten["sender"], "DE")

    # Kein Aufruf erfolgt -> kein Fehler ausgeloest, Liste bleibt leer.
    assert sky_sender_leer == []


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
    echte Sendungen mit Titel/Zeiten liefern, inkl. des absichtlichen
    Titel/Beschreibung-Tauschs bei vorhandener Beschreibung."""
    html_response = _mock_html_response(_hr_fixture_html())

    with patch("arena_epg.requests.get", return_value=html_response):
        site_id = arena_epg.arena_kanal_finden("Arena Sport 1", "HR")
        assert site_id == "1"

        programme = arena_epg.arena_hole_programme(site_id, "HR", tage=2)

    assert len(programme) >= 1
    erste = programme[0]
    # "Description A" wird zum Titel, "Match A" zur Beschreibung (Tausch).
    assert erste["title"] == "Description A"
    assert erste["beschreibung"] == "Match A"
    assert erste["start"].tzinfo is not None
    assert erste["stop"] > erste["start"]


def test_arena_rs_erfolgreicher_abruf_liefert_echte_sendungen():
    """Erfolgreiche Kanalsuche + Programmabruf (RS/tvarenasport.com) muss
    echte Sendungen mit Titel inkl. Liga-Praefix und Live-Markierung
    liefern."""
    html_response = _mock_html_response(_rs_fixture_html())

    with patch("arena_epg.requests.get", return_value=html_response):
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

    with patch("arena_epg.requests.get", return_value=html_response):
        assert arena_epg.arena_kanal_finden("Nicht Existierender Kanal XYZ", "HR") is None

    arena_epg._kanalliste_cache = {}
    arena_epg._seite_cache = {}

    with patch("arena_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")):
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

    with patch("arena_epg.requests.get", side_effect=AssertionError("arena_epg haette nicht kontaktiert werden duerfen")):
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

    with patch("magenta_epg.requests.get", side_effect=router), \
         patch("magenta_epg.requests.post", side_effect=AssertionError("alte API haette nicht kontaktiert werden duerfen")):
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

    with patch("magenta_epg.requests.get", side_effect=_get_side_effect), \
         patch("magenta_epg.requests.post", side_effect=_post_side_effect):
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
    with patch("magenta_epg.requests.get", side_effect=Exception("Netzwerk nicht erreichbar")), \
         patch("magenta_epg.requests.post", side_effect=Exception("Netzwerk nicht erreichbar")):
        assert magenta_epg.magenta_hole_kanalliste() == []
        assert magenta_epg.magenta_kanal_finden("RTL") is None


def test_magenta_ohne_magenta_zeilen_werden_keine_requests_ausgeloest():
    """sender.txt ganz ohne MAGENTA:-Zeilen darf magenta_epg's Request-
    Funktionen ueberhaupt nicht kontaktieren (Zero-Risk-Garantie, analog
    zum SKY:-Guard in generate_epg.py: `magenta_sender = [d for d in
    sender_daten if d.get("magenta")]` bleibt leer, die for-Schleife
    darueber laeuft dann nie)."""
    magenta_sender_leer = []

    with patch("magenta_epg.requests.get", side_effect=AssertionError("magenta_epg haette nicht kontaktiert werden duerfen")), \
         patch("magenta_epg.requests.post", side_effect=AssertionError("magenta_epg haette nicht kontaktiert werden duerfen")):
        for daten in magenta_sender_leer:
            magenta_epg.magenta_kanal_finden(daten["sender"])

    assert magenta_sender_leer == []
