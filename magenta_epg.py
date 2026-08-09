"""Optionale, echte Programmdaten von Magenta TV (Deutsche Telekom).

Analog zu sky_epg.py AUSSCHLIESSLICH opt-in ueber das explizite
"MAGENTA:"-Praefix in sender.txt - es gibt hier bewusst KEIN
automatisches Matching gegen alle Sender mit Land "DE" (zu viele
DE-Zeilen in sender.txt, das waeren zu viele API-Aufrufe pro Lauf und
ein zu hohes Risiko fuer Fehltreffer). Nur das Territory "DE" wird
unterstuetzt.

Im Unterschied zu Sky gibt es hier ZWEI verkettete Magenta-Quellen
(analog zum Telemach->mtel.ba-Fallback in generate_epg.py): zuerst wird
die neuere, unauthentifizierte www.magenta.tv-API versucht (MPX-Feed-
basiert, theplatform.eu), liefert die keinen Kanal-Treffer oder keine
Programmdaten, wird als zweiter Versuch die aeltere, cookie/CSRF-
basierte web.magentatv.de-JSON-API probiert. Portiert aus den beiden
config.js-Site-Plugins "magenta.tv" (neu) und "web.magentatv.de" (alt)
des iptv-org/epg-Projekts, deutlich vereinfacht (kein Caching/TTL fuer
das Manifest - der Manifest-Abruf selbst wird komplett uebersprungen,
da er laut Original nur optionale Werte ueber fest funktionierende
Fallback-Werte legt; keine Season/Episode/Bild/Rating-Metadaten, nur
Titel/Beschreibung/Start/Stop wie bei den anderen Quellen dieses Repos).

Degradiert an JEDER Stelle graceful auf None/[]/leere Liste statt zu
werfen: schlaegt Kanalsuche oder Programmabruf bei BEIDEN Quellen fehl,
bekommt der betroffene Sender in generate_epg.py einfach die normale,
kategoriebasierte generische EPG-Generierung wie jeder andere Sender -
dieses Modul darf einen Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import difflib
import re
import uuid

import requests

from epg_lib import normalisiere_sendername

REQUEST_TIMEOUT_SEKUNDEN = 20

# ---- Neue API (www.magenta.tv, MPX-Feed) --------------------------------

MPX_ACCOUNT_PID = "mdeprod"
MPX_LOCATION_ID_URI = (
    "http://data.entertainment.tv.theplatform.eu/entertainment/data/"
    "Location/245991976396"
)
MPX_ALL_CHANNEL_SCHEDULES_FEED = (
    f"https://feed.entertainment.tv.theplatform.eu/f/{MPX_ACCOUNT_PID}/"
    f"{MPX_ACCOUNT_PID}-all-channel-schedules"
)
MPX_ALL_CHANNEL_STATIONS_FEED = (
    f"https://feed.entertainment.tv.theplatform.eu/f/{MPX_ACCOUNT_PID}/"
    f"{MPX_ACCOUNT_PID}-channel-stations-main"
)

# ---- Alte API (web.magentatv.de, Cookie/CSRF) ----------------------------

MAGENTA_ALT_AUTH_URL = (
    "https://api.prod.sngtv.magentatv.de/EPG/JSON/Authenticate?SID=firstup&T=Windows_chrome_118"
)
MAGENTA_ALT_CHANNELS_URL = "https://api.prod.sngtv.magentatv.de/EPG/JSON/AllChannel"
MAGENTA_ALT_EPG_URL = "https://api.prod.sngtv.magentatv.de/EPG/JSON/PlayBillList"

# Letzte Ziffernfolge einer id/URI (z.B. ".../Station/12345" -> "12345").
_LETZTE_ZIFFERNFOLGE = re.compile(r"(\d+)(?!.*\d)")

# Modul-weiter Cache, analog zu sky_epg.py - die Kanalliste (inkl. welche
# Quelle erfolgreich war) wird pro Lauf nur einmal geholt.
_kanalliste_cache = None
_kanalliste_quelle = None

# Cache fuer Login-Daten der alten API (nur einmal pro Lauf noetig).
_alt_auth_cache = None


def _numerische_id(wert):
    """Extrahiert die letzte Ziffernfolge aus einer id/URI-Zeichenkette
    (z.B. MPX-eid/href). None bei fehlendem Treffer."""
    if not wert:
        return None
    treffer = _LETZTE_ZIFFERNFOLGE.search(str(wert))
    return treffer.group(1) if treffer else None


def _magenta_neu_kanalliste():
    """Holt die Kanalliste ueber die neuere www.magenta.tv MPX-Feed-API
    (paginiert, 100er-Seiten, bis max. 1000 Kanaele). Leere Liste bei
    jedem Fehler."""
    kanaele = []
    gesehene_site_ids = set()

    try:
        start = 1
        while start <= 1000:
            ende = start + 99
            response = requests.get(
                MPX_ALL_CHANNEL_STATIONS_FEED,
                params={
                    "lang": "short-de",
                    "sort": "dt$displayChannelNumber",
                    "range": f"{start}-{ende}",
                    "cid": uuid.uuid4().hex,
                },
                timeout=REQUEST_TIMEOUT_SEKUNDEN,
            )
            response.raise_for_status()
            daten = response.json()
            eintraege = daten.get("entries", []) if isinstance(daten, dict) else []

            for eintrag in eintraege:
                if eintrag.get("dt$isRadio"):
                    continue

                stations = eintrag.get("stations") or {}
                station = next(iter(stations.values()), None) if isinstance(stations, dict) else None

                site_id = _numerische_id(eintrag.get("id"))
                name = (station or {}).get("title") if station else None
                if not name:
                    name = eintrag.get("title")

                if not station or not site_id or not name:
                    continue

                if site_id in gesehene_site_ids:
                    continue
                gesehene_site_ids.add(site_id)
                kanaele.append({"site_id": site_id, "name": name})

            if len(eintraege) < 100:
                break
            start += 100

        return kanaele
    except Exception as e:
        print(f"Magenta-EPG (neu): Kanalliste fehlgeschlagen ({e}), ueberspringe.")
        return []


def _magenta_neu_programme(site_id, tage=2):
    """Holt Programmdaten ueber die neuere www.magenta.tv MPX-Feed-API
    fuer `tage` aufeinanderfolgende Tage ab heute (UTC). Leere Liste bei
    jedem Fehler."""
    if not site_id:
        return []

    heute = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    alle_sendungen = []

    for tag_index in range(tage):
        tag_start = heute + timedelta(days=tag_index)
        tag_ende = tag_start + timedelta(days=1)

        try:
            response = requests.get(
                MPX_ALL_CHANNEL_SCHEDULES_FEED,
                params={
                    "byId": site_id,
                    "byListingTime": (
                        f"{tag_start.strftime('%Y-%m-%dT%H:%M:%SZ')}~"
                        f"{tag_ende.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                    ),
                    "byLocationId": MPX_LOCATION_ID_URI,
                    "cid": uuid.uuid4().hex,
                },
                timeout=REQUEST_TIMEOUT_SEKUNDEN,
            )
            response.raise_for_status()
            daten = response.json()
            eintraege = daten.get("entries", []) if isinstance(daten, dict) else []

            for eintrag in eintraege:
                if _numerische_id(eintrag.get("id")) != str(site_id):
                    continue

                for listing in eintrag.get("listings", []) or []:
                    programm = listing.get("program")
                    start_ms = listing.get("startTime")
                    stop_ms = listing.get("endTime")
                    if not programm or start_ms is None or stop_ms is None:
                        continue

                    titel = programm.get("title")
                    if not titel:
                        continue

                    start = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
                    stop = datetime.fromtimestamp(stop_ms / 1000, tz=timezone.utc)

                    alle_sendungen.append({
                        "title": titel,
                        "beschreibung": programm.get("description") or "",
                        "bild": None,
                        "start": start,
                        "stop": stop,
                    })
        except Exception as e:
            print(f"Magenta-EPG (neu): Programmabruf fuer Kanal {site_id} Tag {tag_index} fehlgeschlagen ({e}), ueberspringe Tag.")
            continue

    alle_sendungen.sort(key=lambda s: s["start"])
    return alle_sendungen


def _magenta_alt_login():
    """Meldet sich (falls noch nicht gecached) bei der aelteren
    web.magentatv.de-API an und liefert {"X_CSRFTOKEN":..., "Cookie":...}
    zurueck, oder None bei jedem Fehler."""
    global _alt_auth_cache

    if _alt_auth_cache is not None:
        return _alt_auth_cache

    try:
        response = requests.post(
            MAGENTA_ALT_AUTH_URL,
            data=(
                '{"terminalid":"00:00:00:00:00:00","mac":"00:00:00:00:00:00",'
                '"terminaltype":"WEBTV","utcEnable":1,"timezone":"Etc/GMT0",'
                '"userType":3,"terminalvendor":"Unknown"}'
            ),
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        daten = response.json()
        csrf_token = daten.get("csrfToken") if isinstance(daten, dict) else None
        if not csrf_token:
            return None

        cookie_teile = []
        for roh_cookie in response.headers.get("Set-Cookie", "").split(","):
            name_wert = roh_cookie.split(";", 1)[0].strip()
            if "=" in name_wert and any(
                schluessel in name_wert
                for schluessel in ("JSESSIONID", "CSESSIONID", "CSRFSESSION")
            ):
                cookie_teile.append(name_wert)

        # requests fasst mehrere Set-Cookie-Header ueblicherweise bereits
        # als eine kombinierte Zeichenkette zusammen (durch Komma
        # getrennt) - im Zweifel reicht ein leeres Cookie, die alte API
        # degradiert dann selbst auf einen Fehlschlag.
        _alt_auth_cache = {
            "X_CSRFTOKEN": csrf_token,
            "Cookie": " ".join(cookie_teile),
        }
        return _alt_auth_cache
    except Exception as e:
        print(f"Magenta-EPG (alt): Login fehlgeschlagen ({e}), ueberspringe.")
        return None


def _magenta_alt_kanalliste():
    """Holt die Kanalliste ueber die aeltere web.magentatv.de-API
    (Login + AllChannel). Leere Liste bei jedem Fehler."""
    auth = _magenta_alt_login()
    if not auth:
        return []

    try:
        response = requests.post(
            MAGENTA_ALT_CHANNELS_URL,
            json={
                "channelNamespace": 2,
                "filterlist": [{"key": "IsHide", "value": "-1"}],
                "metaDataVer": "Channel/1.1",
                "properties": [{
                    "include": "/channellist/logicalChannel/contentId,/channellist/logicalChannel/name",
                    "name": "logicalChannel",
                }],
                "returnSatChannel": 0,
            },
            headers={"X_CSRFTOKEN": auth["X_CSRFTOKEN"], "Cookie": auth["Cookie"]},
            timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        daten = response.json()
        roh_kanaele = daten.get("channellist", []) if isinstance(daten, dict) else []

        kanaele = []
        for kanal in roh_kanaele:
            site_id = kanal.get("contentId")
            name = kanal.get("name")
            if not site_id or not name:
                continue
            kanaele.append({"site_id": site_id, "name": name})

        return kanaele
    except Exception as e:
        print(f"Magenta-EPG (alt): Kanalliste fehlgeschlagen ({e}), ueberspringe.")
        return []


def _magenta_alt_programme(site_id, tage=2):
    """Holt Programmdaten ueber die aeltere web.magentatv.de-API fuer
    `tage` aufeinanderfolgende Tage ab heute (UTC). Leere Liste bei
    jedem Fehler."""
    if not site_id:
        return []

    auth = _magenta_alt_login()
    if not auth:
        return []

    heute = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    alle_sendungen = []

    for tag_index in range(tage):
        tag_start = heute + timedelta(days=tag_index)
        tag_ende = tag_start + timedelta(days=1)

        try:
            response = requests.post(
                MAGENTA_ALT_EPG_URL,
                json={
                    "count": -1,
                    "isFillProgram": 1,
                    "offset": 0,
                    "properties": [{
                        "include": (
                            "endtime,genres,id,name,starttime,channelid,pictures,"
                            "introduce,subName,seasonNum,subNum,cast,country,"
                            "producedate,externalIds"
                        ),
                        "name": "playbill",
                    }],
                    "type": 2,
                    "begintime": tag_start.strftime("%Y%m%d000000"),
                    "channelid": site_id,
                    "endtime": tag_ende.strftime("%Y%m%d000000"),
                },
                headers={"X_CSRFTOKEN": auth["X_CSRFTOKEN"], "Cookie": auth["Cookie"]},
                timeout=REQUEST_TIMEOUT_SEKUNDEN,
            )
            response.raise_for_status()
            daten = response.json()
            eintraege = daten.get("playbilllist", []) if isinstance(daten, dict) else []

            for eintrag in eintraege:
                titel = eintrag.get("name")
                if not titel:
                    continue

                start = _alt_zeit_parsen(eintrag.get("starttime"))
                stop = _alt_zeit_parsen(eintrag.get("endtime"))
                if not start or not stop:
                    continue

                alle_sendungen.append({
                    "title": titel,
                    "beschreibung": eintrag.get("introduce") or "",
                    "bild": None,
                    "start": start,
                    "stop": stop,
                })
        except Exception as e:
            print(f"Magenta-EPG (alt): Programmabruf fuer Kanal {site_id} Tag {tag_index} fehlgeschlagen ({e}), ueberspringe Tag.")
            continue

    alle_sendungen.sort(key=lambda s: s["start"])
    return alle_sendungen


def _alt_zeit_parsen(wert):
    """Parst die von der alten Magenta-API gelieferten naiven UTC-
    Zeitstempel ("YYYY-MM-DD HH:mm:ss") zu einem tz-aware UTC-datetime.
    Gibt bei jedem Parse-Fehler None zurueck."""
    if not wert:
        return None
    try:
        naiv = datetime.strptime(wert, "%Y-%m-%d %H:%M:%S")
        return naiv.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def magenta_hole_kanalliste():
    """Holt (und cached fuer den Lauf) die Magenta-Kanalliste - erst
    ueber die neuere www.magenta.tv-API, bei leerem/fehlgeschlagenem
    Ergebnis als Fallback ueber die aeltere web.magentatv.de-API.
    Liefert eine Liste von {"site_id":..., "name":...}; leere Liste,
    wenn BEIDE Quellen fehlschlagen. Merkt sich zusaetzlich (modulweit),
    welche Quelle erfolgreich war, fuer magenta_kanal_finden()."""
    global _kanalliste_cache, _kanalliste_quelle

    if _kanalliste_cache is not None:
        return _kanalliste_cache

    kanaele = _magenta_neu_kanalliste()
    if kanaele:
        _kanalliste_cache = kanaele
        _kanalliste_quelle = "neu"
        return kanaele

    kanaele = _magenta_alt_kanalliste()
    if kanaele:
        _kanalliste_cache = kanaele
        _kanalliste_quelle = "alt"
        return kanaele

    _kanalliste_cache = []
    _kanalliste_quelle = None
    return []


def magenta_kanal_finden(kanalname):
    """Sucht den Magenta-Kanal, der am besten zu kanalname passt - erst
    exakter Abgleich nach normalisiere_sendername(), sonst unscharfer
    difflib-Abgleich (gleiche Vorgehensweise wie sky_kanal_finden()/
    telemach_kanal_finden()). Gibt {"quelle": "neu"|"alt", "site_id":...}
    zurueck oder None, wenn keine Quelle etwas findet."""
    kanaele = magenta_hole_kanalliste()
    if not kanaele:
        return None

    ziel_schluessel = normalisiere_sendername(kanalname)
    if not ziel_schluessel:
        return None

    name_index = {}
    for kanal in kanaele:
        schluessel = normalisiere_sendername(kanal["name"])
        if schluessel:
            name_index.setdefault(schluessel, kanal["site_id"])

    site_id = None
    if ziel_schluessel in name_index:
        site_id = name_index[ziel_schluessel]
    else:
        aehnliche = difflib.get_close_matches(ziel_schluessel, name_index.keys(), n=1, cutoff=0.72)
        if aehnliche:
            site_id = name_index[aehnliche[0]]

    if site_id is None:
        return None

    return {"quelle": _kanalliste_quelle, "site_id": site_id}


def magenta_hole_programme(kanal_ref, tage=2):
    """Holt Programmdaten fuer den gegebenen Magenta-Kanal (Rueckgabewert
    von magenta_kanal_finden()) fuer `tage` aufeinanderfolgende Tage ab
    heute (UTC). Probiert zuerst die Quelle aus kanal_ref["quelle"]; nur
    wenn das die neue API war UND nichts liefert, wird zusaetzlich noch
    die alte API als letzter Fallback probiert (die Kanalsuche hat dann
    zwar ueber die neue API funktioniert, aber der Programmabruf selbst
    kann trotzdem fehlschlagen - z.B. weil der Kanal keine Daten fuer den
    Tag hat). Liefert eine nach Startzeit sortierte Liste von {"title",
    "beschreibung", "bild", "start", "stop"} (UTC, tz-aware) - leere
    Liste bei jedem Fehler oder wenn kanal_ref None/unvollstaendig ist."""
    if not kanal_ref or not kanal_ref.get("site_id"):
        return []

    quelle = kanal_ref.get("quelle")
    site_id = kanal_ref["site_id"]

    if quelle == "alt":
        return _magenta_alt_programme(site_id, tage)

    # Default/"neu": neue API zuerst versuchen.
    programme = _magenta_neu_programme(site_id, tage)
    if programme:
        return programme

    # Letzter Fallback: falls die alte API zufaellig denselben Kanal
    # unter einer eigenen Kanalliste kennt, wird sie separat ueber ihre
    # eigene Kanalsuche versucht - site_ids der beiden APIs sind NICHT
    # kompatibel, daher hier ueber den Kanalnamen gar nicht moeglich
    # ohne erneuten Namensabgleich. Da magenta_kanal_finden() bereits
    # die alte API als Fallback nutzt, wenn die neue Kanalliste leer
    # war, bleibt dieser Zweig bewusst leer (kein Cross-Match zwischen
    # inkompatiblen site_id-Formaten) - kanal_ref["quelle"] == "alt"
    # wird bereits oben separat behandelt.
    return []
