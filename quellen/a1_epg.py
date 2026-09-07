"""Echte Programmdaten von A1 Hrvatska (www.a1.hr/raspored/) - erster
Versuch fuer alle HR-Sender, VOR MojMaxTV/SportKlub (siehe
mojmaxtv_epg.py/sportklub_epg.py).

Oeffentliche, loginfreie JSON-API (kein Kunden-Login noetig, obwohl die
Seite selbst unter der A1-Hauptdomain haengt):
  - https://www.a1.hr/epg/api/channels  -> komplette Kanalliste
  - https://www.a1.hr/epg/api/entries?channels=<id>&date=YYYY-MM-DD
    -> Sendungen fuer einen Kanal/Tag

Gefunden ueber eine vom Nutzer als .mht gespeicherte Kopie der Seite
(die eigentliche App-Domain "a1xploretv.hr" ist nicht erreichbar/tot -
das war der Grund, warum eine fruehere Recherche daran scheiterte). Im
Vergleich zu MojMaxTV liefert A1 echte Beschreibungstexte (MojMaxTV:
immer leer), bereits normal geschriebene Titel (MojMaxTV: komplett
grossgeschrieben) und ein laengeres Vorschau-Fenster (~6-7 Tage statt
2) - deckt aber INSGESAMT weniger Kanaele ab als MojMaxTV (202 vs. 248,
Stand September 2026). Deshalb bewusst als ERSTER Versuch eingebaut,
MojMaxTV/SportKlub bleiben Fallback fuer alles, was A1 nicht kennt.

Degradiert an JEDER Stelle graceful auf None/[] statt zu werfen -
schlaegt Kanalsuche oder Programmabruf fehl, faellt generate_epg.py auf
die naechste Quelle in der Kette (MojMaxTV) bzw. am Ende auf die
normale generische EPG-Generierung zurueck.
"""

from datetime import datetime, timedelta, timezone

import re

import requests

from epg_lib import normalisiere_sendername, normalisiere_sendername_kern

# A1 fuehrt den kroatischen oeffentlich-rechtlichen Sender unter "HTV"
# statt "HRT" (z.B. "HTV1 HD" statt "HRT 1") - ohne diesen Alias matcht
# weder der exakte noch der unscharfe Abgleich, UND der unscharfe
# difflib-Fallback (Cutoff 0.72) fand fuer "HRT1" faelschlich den
# voellig anderen Kanal "RTV1" (nur 1 Zeichen Unterschied bei so
# kurzen Strings) - live verifiziert und behoben (September 2026).
# Fuer dieses Alias-Muster wird deshalb NUR ein exakter Treffer nach
# Umschreiben auf "HTV" akzeptiert, kein genereller Fuzzy-Fallback.
_HRT_ALIAS_PATTERN = re.compile(r"^HRT(?=\d|\s|$)", re.IGNORECASE)

API_BASE = "https://www.a1.hr/epg/api/"
CHANNELS_URL = API_BASE + "channels"
ENTRIES_URL = API_BASE + "entries"

REQUEST_TIMEOUT_SEKUNDEN = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

# Modul-weiter Cache: Kanalliste einmal pro Lauf, Sendungen pro
# (site_id, Datum)-Kombination (die API liefert nur einen Kanal/Tag pro
# Request).
_kanalliste_cache = None
_entries_cache = {}


def a1_hole_kanalliste():
    """Holt (und cached) die komplette A1-Kanalliste als Liste von
    {"site_id": int, "name": str}. Leere Liste bei jedem Fehler."""
    global _kanalliste_cache

    if _kanalliste_cache is not None:
        return _kanalliste_cache

    try:
        response = requests.get(CHANNELS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()
        daten = response.json()
        roh_kanaele = daten.get("channels", []) if isinstance(daten, dict) else []

        kanaele = []
        for kanal in roh_kanaele:
            site_id = kanal.get("id")
            titel = kanal.get("title")
            if site_id is None or not titel:
                continue
            kanaele.append({"site_id": site_id, "name": titel})

        _kanalliste_cache = kanaele
        return kanaele
    except Exception as e:
        print(f"A1-EPG: Kanalliste fehlgeschlagen ({e}), ueberspringe.")
        _kanalliste_cache = []
        return []


def a1_kanal_finden(kanalname):
    """Sucht den A1-Kanal, der exakt (nach normalisiere_sendername(),
    sonst nach normalisiere_sendername_kern() als zweitem, ebenfalls
    deterministischem Versuch ohne HD/FHD/UHD/SD-Qualitaetssuffix) zu
    kanalname passt, plus dem gezielten HRT->HTV-Alias oben.

    BEWUSST KEIN genereller unscharfer difflib-Fallback (anders als
    MojMaxTV/Sky/mts.rs): eine Stichprobe gegen alle echten HR-Zeilen
    in sender.txt (September 2026) zeigte mehrere echte Fehltreffer bei
    A1s eigenwilligen/abweichenden Kanalnamen, z.B. "DMC HD" -> "AMC
    HD", "OTV HD" -> "Nova TV HD", "RTL 1" -> "RTV1", "MTV 80s"/"MTV
    00s" -> "MTV 90s", "Viasat True Crime" -> "Viasat Nature",
    "SABORSKA TV" -> "Sportska TV" - alles inhaltlich komplett andere
    Sender. Der Kern-Vergleich ist davon nicht betroffen (kein
    Aehnlichkeits-Score, nur ein zusaetzliches, festes Suffix-Wort wird
    ignoriert) und wurde ebenfalls gegen alle echten HR-Zeilen
    verifiziert (37 zusaetzliche, ausschliesslich korrekte Treffer,
    z.B. "ARENA SPORT 1 ⱽᴵᴾ ᴿᴬᵂ" -> "Arena Sport 1 HD", "DMC HD" ->
    "DMC"). Lieber weniger Treffer als falsche Programmdaten unter
    einem falschen Sendernamen. Gibt die Kanal-ID (int) zurueck oder
    None."""
    kanaele = a1_hole_kanalliste()
    if not kanaele:
        return None

    name_index_roh = {}
    kern_index = {}
    for kanal in kanaele:
        schluessel = normalisiere_sendername(kanal["name"])
        if schluessel:
            name_index_roh.setdefault(schluessel, kanal["site_id"])
        kern = normalisiere_sendername_kern(kanal["name"])
        if kern:
            kern_index.setdefault(kern, kanal["site_id"])

    if _HRT_ALIAS_PATTERN.match(kanalname.strip()):
        htv_name = _HRT_ALIAS_PATTERN.sub("HTV", kanalname.strip())
        htv_schluessel = normalisiere_sendername(htv_name)
        return name_index_roh.get(htv_schluessel)

    ziel_schluessel = normalisiere_sendername(kanalname)
    if not ziel_schluessel:
        return None

    if ziel_schluessel in name_index_roh:
        return name_index_roh[ziel_schluessel]

    ziel_kern = normalisiere_sendername_kern(kanalname)
    return kern_index.get(ziel_kern)


def _zeit_parsen(wert):
    """Parst die von der A1-API gelieferten Zeitstempel (ISO 8601 mit
    Zeitzonen-Offset, z.B. '2026-09-05T18:16:00.236421+02:00') zu einem
    tz-aware UTC-datetime. None bei jedem Parse-Fehler."""
    if not wert:
        return None
    try:
        return datetime.fromisoformat(wert).astimezone(timezone.utc)
    except Exception:
        return None


def _hole_tag(site_id, datum):
    """Holt (und cached) die Sendungen fuer einen Kanal an einem
    einzelnen Tag. Leere Liste bei jedem Fehler (Netzwerk, HTTP-Status,
    kaputtes JSON) - wird ebenfalls gecacht, damit ein dauerhafter
    Fehler nicht bei jedem Sender erneut denselben Request ausloest."""
    datum_str = datum.strftime("%Y-%m-%d")
    cache_schluessel = (site_id, datum_str)

    if cache_schluessel in _entries_cache:
        return _entries_cache[cache_schluessel]

    ergebnis = []
    try:
        response = requests.get(
            ENTRIES_URL,
            params={"channels": site_id, "date": datum_str},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SEKUNDEN,
        )
        response.raise_for_status()
        daten = response.json()
        eintraege = daten.get("entries", []) if isinstance(daten, dict) else []

        for eintrag in eintraege:
            start = _zeit_parsen(eintrag.get("start"))
            stop = _zeit_parsen(eintrag.get("end"))
            titel = (eintrag.get("title") or "").strip()
            if not start or not stop or not titel:
                continue

            beschreibung = (eintrag.get("desc") or "").strip()

            ergebnis.append({
                "title": titel,
                "beschreibung": beschreibung,
                "start": start,
                "stop": stop,
            })
    except Exception as e:
        print(f"A1-EPG: Sendungen ({datum_str}, Kanal {site_id}) fehlgeschlagen ({e}), ueberspringe.")
        ergebnis = []

    _entries_cache[cache_schluessel] = ergebnis
    return ergebnis


def a1_hole_programme(site_id, tage=6):
    """Holt Programmdaten fuer den gegebenen A1-Kanal (site_id) fuer
    `tage` aufeinanderfolgende Tage ab heute (UTC, lokale Kalendertage
    passend zur von der API selbst zurueckgegebenen Ortszeit Europe/
    Zagreb). Liefert eine nach Startzeit sortierte Liste, leere Liste
    bei jedem Fehler oder fehlendem Kanal."""
    if site_id is None:
        return []

    heute = datetime.now(timezone.utc).date()
    ergebnis = []
    for i in range(tage):
        tag = heute + timedelta(days=i)
        ergebnis.extend(_hole_tag(site_id, tag))

    ergebnis.sort(key=lambda p: p["start"])
    return ergebnis
