"""Echte Programmdaten von der oeffentlichen Rakuten-TV-API (gizmo.rakuten.tv)
fuer Deutschland - AUTOMATISCH als zusaetzlicher, letzter Versuch in der
DE-Kaskade (siehe generate_epg.py), NACH deswird.org/Pluto TV/tvmovie.de/
hoerzu.de/Joyn-VOD/Magenta-myTeamTV/iptv-epg.org.

Nutzer lieferte einen Browser-Snapshot der Rakuten-TV-Kanalseite
(rakuten.tv/de/live_channels/...) als Hinweis auf echte Programmdaten.
Die zugrunde liegende, oeffentliche (kein Login/API-Key noetige) API
wurde daraufhin ueber ein vergleichbares Open-Source-Projekt
(github.com/dp247/rakuten-uk-epg) identifiziert - dieselbe API liefert
auch fuer market_code=de vollstaendige Kanal- und Sendungsdaten.

Besonderheit: EIN einziger Endpoint (`/v3/live_channels`) liefert pro
Seite (max. 50 Kanaele) sowohl die Kanalliste als auch bereits alle
Sendungen der naechsten Tage in einem Feld ("live_programs") - kein
separater Programmabruf pro Kanal noetig. Fuer Deutschland gibt es
aktuell 157 Kanaele (4 Seiten) - werden PARALLEL statt sequenziell
abgerufen (live gemessen: 27s sequenziell vs. 0.7s parallel bei 4
Workern - die API antwortet pro einzelnem sequenziellem Request
auffaellig langsam, parallele Requests umgehen das vollstaendig).

`classification_id=307` ("NC" - alle Inhalte, deutscher Marktstandard-
Wert) wurde ueber den zusaetzlichen, oeffentlichen `/v3/classifications`-
Endpoint ermittelt (marktspezifisch, der UK-Wert 18 funktioniert fuer
DE nicht).

Kanalzuordnung laeuft bewusst NUR ueber einen exakten Namensabgleich
(normalisiere_sendername(), kein Fuzzy-Anteil) - viele Kanalnamen sind
kurze, generische Begriffe (z.B. "Krimi", "Naruto"), bei denen ein
unscharfer Abgleich zu schnell falsch matchen wuerde.

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen: schlaegt der Download,
das Parsen oder die Kanalsuche fehl, bekommt der betroffene Sender in
generate_epg.py einfach die normale, kategoriebasierte generische
EPG-Generierung wie jeder andere Sender - dieses Modul darf einen Lauf
niemals zum Absturz bringen.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import threading
import requests
from quellen import _http

from epg_lib import normalisiere_sendername

BASIS_URL = "https://gizmo.rakuten.tv/v3/live_channels"

REQUEST_TIMEOUT_SEKUNDEN = 30
SEITENGROESSE = 50
MAX_SEITEN = 10  # Sicherheitsnetz gegen eine Endlosschleife bei kaputter Pagination
SEITEN_WORKER = 4

# Deutschland-spezifisch (siehe Modul-Docstring) - market_code/
# classification_id sind je Land unterschiedlich, aktuell nur DE
# unterstuetzt (einzige in sender.txt vorkommende Zielgruppe fuer diese
# Quelle: DE/JOYN/PRIME/WOW/GO-Sender).
MARKET_CODE = "de"
LOCALE = "de"
CLASSIFICATION_ID = 307

EPG_DAUER_TAGE = 2

# Modul-weiter Cache: {"kanaele": [...], "programme": {kanal_id: [...]}}
_daten_cache = None
_daten_cache_lock = threading.Lock()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def _basis_parameter():
    jetzt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    ende = jetzt + timedelta(days=EPG_DAUER_TAGE)
    return {
        "classification_id": CLASSIFICATION_ID,
        "device_identifier": "web",
        "device_stream_audio_quality": "2.0",
        "device_stream_hdr_type": "NONE",
        "device_stream_video_quality": "FHD",
        "epg_duration_minutes": 360,
        "epg_ends_at": ende.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "epg_ends_at_timestamp": ende.timestamp(),
        "epg_starts_at": jetzt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "epg_starts_at_timestamp": jetzt.timestamp(),
        "locale": LOCALE,
        "market_code": MARKET_CODE,
        "per_page": SEITENGROESSE,
    }


def _zeit_parsen(text):
    """Parst das von der API gelieferte Zeitformat
    'YYYY-MM-DDTHH:MM:SS.000+HH:MM' zu einem tz-aware datetime (UTC).
    None bei Parse-Fehler."""
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.000%z").astimezone(timezone.utc)
    except Exception:
        return None


def _seite_holen(seite):
    """Holt eine einzelne Ergebnisseite (bis zu SEITENGROESSE Kanaele
    inkl. ihrer Sendungen). Leere Liste bei jedem Fehler."""
    try:
        params = _basis_parameter()
        params["page"] = seite
        response = _http.mit_retry(
            requests.get, BASIS_URL, params=params, headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        return response.json().get("data", []) or []
    except Exception:
        return []


def _alle_kanaele_laden():
    """Laedt alle Seiten PARALLEL (siehe Modul-Docstring - sequenziell
    ist die API auffaellig langsam). Die erste Seite wird zuerst einzeln
    geholt, um die tatsaechliche Gesamtseitenzahl aus der Pagination-
    Meta-Info zu kennen, dann werden die restlichen Seiten parallel
    nachgeladen."""
    try:
        params = _basis_parameter()
        params["page"] = 1
        response = _http.mit_retry(
            requests.get, BASIS_URL, params=params, headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        antwort = response.json()
    except Exception as e:
        print(f"Rakuten-TV-EPG: Erstabruf fehlgeschlagen ({type(e).__name__}), ueberspringe.")
        return []

    erste_seite = antwort.get("data", []) or []
    gesamt_seiten = (
        antwort.get("meta", {}).get("pagination", {}).get("total_pages", 1)
    )
    gesamt_seiten = min(gesamt_seiten, MAX_SEITEN)

    alle_kanaele = list(erste_seite)
    if gesamt_seiten > 1:
        restliche_seiten = range(2, gesamt_seiten + 1)
        with ThreadPoolExecutor(max_workers=SEITEN_WORKER) as pool:
            for ergebnis in pool.map(_seite_holen, restliche_seiten):
                alle_kanaele.extend(ergebnis)

    return alle_kanaele


def _daten_laden():
    """Laedt und parst (und cached) alle deutschen Rakuten-TV-Kanaele
    inkl. Sendungen. Gibt {"kanaele": [...], "programme": {id: [...]}}
    zurueck - auch bei jedem Fehler als leeres, aber nicht-None
    Ergebnis (kein erneuter Download-Versuch bei jedem einzelnen
    Sender)."""
    global _daten_cache

    if _daten_cache is not None:
        return _daten_cache

    with _daten_cache_lock:
        if _daten_cache is not None:
            return _daten_cache

        try:
            roh_kanaele = _alle_kanaele_laden()

            kanaele = []
            programme = {}
            for kanal in roh_kanaele:
                kanal_id = kanal.get("id")
                name = kanal.get("title")
                if not kanal_id or not name:
                    continue
                kanaele.append({"site_id": kanal_id, "name": name})

                eintraege = []
                for sendung in kanal.get("live_programs") or []:
                    titel = sendung.get("title")
                    start = _zeit_parsen(sendung.get("starts_at"))
                    stop = _zeit_parsen(sendung.get("ends_at"))
                    if not titel or not start or not stop:
                        continue
                    eintraege.append({
                        "title": titel,
                        "beschreibung": sendung.get("description") or "",
                        "bild": None,
                        "start": start,
                        "stop": stop,
                    })
                eintraege.sort(key=lambda s: s["start"])
                if eintraege:
                    programme[kanal_id] = eintraege

            print(f"Rakuten-TV-EPG: {len(kanaele)} Kanaele, {len(programme)} Kanaele mit Sendungen geladen.")

            daten = {"kanaele": kanaele, "programme": programme}
            _daten_cache = daten
            return daten
        except Exception as e:
            print(f"Rakuten-TV-EPG: Laden/Parsen fehlgeschlagen ({type(e).__name__}), ueberspringe.")
            _daten_cache = {"kanaele": [], "programme": {}}
            return _daten_cache


# Bekannte Faelle, bei denen der sender.txt-Kurzname NICHT exakt dem
# vollen Rakuten-TV-Titel entspricht (z.B. "AMASIA" in sender.txt vs.
# "Amasia - The Finest Art of Asian Movies" bei Rakuten) - einzeln
# gepflegt statt eines generischen Fuzzy-Abgleichs, um bei den vielen
# kurzen/generischen Kanalnamen (siehe Modul-Docstring) kein
# Fehltreffer-Risiko einzugehen.
_BEKANNTE_ALIASE = {
    normalisiere_sendername("AMASIA"): normalisiere_sendername(
        "Amasia - The Finest Art of Asian Movies"
    ),
}


def rakuten_tv_kanal_finden(kanalname):
    """Sucht den Rakuten-TV-Kanal per EXAKTEM Namensabgleich (nach
    normalisiere_sendername(), kein Fuzzy-Anteil - siehe Modul-
    Docstring) oder ueber die feste Alias-Liste oben. Gibt die
    Kanal-ID zurueck oder None."""
    daten = _daten_laden()
    if not daten or not daten["kanaele"]:
        return None

    ziel_schluessel = normalisiere_sendername(kanalname)
    if not ziel_schluessel:
        return None
    ziel_schluessel = _BEKANNTE_ALIASE.get(ziel_schluessel, ziel_schluessel)

    name_index = {}
    for kanal in daten["kanaele"]:
        schluessel = normalisiere_sendername(kanal["name"])
        if schluessel:
            name_index.setdefault(schluessel, kanal["site_id"])

    return name_index.get(ziel_schluessel)


def rakuten_tv_hole_programme(site_id, tage=2):
    """Liefert die bereits geladenen Programmdaten fuer den gegebenen
    Kanal (site_id) zurueck - leere Liste, falls keine vorhanden sind.
    `tage` wird bewusst ignoriert (die API liefert ohnehin nur
    EPG_DAUER_TAGE Tage im Voraus, siehe _basis_parameter())."""
    if not site_id:
        return []
    daten = _daten_laden()
    if not daten:
        return []
    return daten["programme"].get(site_id, [])
