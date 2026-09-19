"""Echte Programmdaten fuer "RTL Adria" (RS + HR, gleicher Kanal in
beiden Laendern - regionaler Balkan-Kanal von RTL Kroatien) von
rtl.hr - AUTOMATISCH fuer jeden RS/HR-Sender, dessen Name auf
"RTL ADRIA" passt (mit oder ohne HD/FHD/VIP/RAW-Zusaetzen). Kein
eigenes Praefix noetig.

https://www.rtl.hr/tv-raspored/kanal/rtl-adria liefert - server-seitig
bereits gerendert - den KOMPLETTEN Sendeplan der naechsten 8 Kalender-
tage (Reiter "Danas"/"Sutra"/Wochentage) in EINEM Seitenabruf, aufgeteilt
in drei feste Tageszeit-Abschnitte ("morning"/"noon"/"evening", je ein
<div id=...>), jeder Abschnitt enthaelt die Eintraege ALLER 8 Tage
hintereinander (nicht die Eintraege EINES Tages).

Tages-Trennung ist pro Abschnitt unterschiedlich, da nur "evening" ueber
Mitternacht hinaus laeuft:
- "morning"/"noon": ein neuer Tag beginnt, sobald die Uhrzeit gegenueber
  der vorherigen Sendung zurueckspringt (normaler Mitternacht-Ueberlauf
  kommt hier nicht vor, diese Abschnitte enden vor Mitternacht).
- "evening": der Sender fuehrt einen expliziten Platzhalter-Eintrag
  "Kraj programa" ("Ende des Programms") kurz nach Mitternacht - GENAU
  dieser Eintrag markiert das Tagesende (nicht die Uhrzeit selbst, die
  waere wegen des Mitternacht-Ueberlaufs sonst nicht von einem echten
  Tageswechsel unterscheidbar). "Kraj programa" selbst ist kein echter
  Sendungstitel und wird am Ende verworfen, dient aber als Endzeit-Anker
  fuer die letzte echte Sendung des Tages.

Wird nur EINMAL pro Lauf geladen und geparst (Modul-weiter Cache) und
dann auf die angefragten Kalendertage projiziert (Tag-Index 0 = heute,
Europe/Zagreb).

Degradiert nach dem gleichen Zero-Risk-Prinzip an JEDER Stelle graceful
auf None/[]/leere Ergebnisse statt zu werfen - dieses Modul darf einen
Lauf niemals zum Absturz bringen.
"""

from datetime import datetime, timedelta, timezone

import re
import unicodedata

import requests
from quellen import _http
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

BASIS_URL = "https://www.rtl.hr/tv-raspored/kanal/{slug}"

# Sendername-Praefix-Schluessel -> rtl.hr-Kanal-Slug.
_SLUGS = {
    "adria": "rtl-adria",
}

REQUEST_TIMEOUT_SEKUNDEN = 20

TZ_ZAGREB = ZoneInfo("Europe/Zagreb")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

_RTL_ADRIA_PATTERN = re.compile(r"^RTL\s*ADRIA\b", re.IGNORECASE)

_TAGESENDE_MARKER = "kraj programa"

# Modul-weiter Cache je Schluessel: {"adria": [...]}
_programme_cache = {}


def _vip_raw_hd_entfernen(name):
    """Entfernt die playlist-eigenen Deko-Marker "VIP"/"RAW"/"HD"/"FHD"
    (auch in hochgestellter Unicode-Schreibweise wie "ⱽᴵᴾ ᴿᴬᵂ" - NFKD
    zerlegt diese zu normalen Buchstaben)."""
    zerlegt = unicodedata.normalize("NFKD", name)
    zerlegt = "".join(z for z in zerlegt if not unicodedata.combining(z))
    return re.sub(r"\bVIP\b|\bRAW\b|\bF?HD\b", " ", zerlegt, flags=re.IGNORECASE).strip()


def rtl_hr_kanal_finden(kanalname):
    """Erkennt "RTL Adria" (mit beliebigen Whitespace-/HD/FHD/VIP/RAW-
    Zusaetzen, egal ob RS- oder HR-Sender-Zeile) und gibt den passenden
    Schluessel ("adria") zurueck, sonst None. Einfacher Praefix-
    Vergleich (kein Fuzzy-Abgleich, kein Fehltreffer-Risiko)."""
    name = _vip_raw_hd_entfernen(kanalname.strip())
    name = re.sub(r"\s+", " ", name)

    if _RTL_ADRIA_PATTERN.match(name):
        return "adria"

    return None


def _zeit_zu_minuten(zeit_text):
    treffer = re.match(r"^(\d{1,2}):(\d{2})$", zeit_text.strip())
    if not treffer:
        return None
    return int(treffer.group(1)) * 60 + int(treffer.group(2))


def _abschnitt_eintraege(soup, anchor_id):
    """Liest alle (Uhrzeit, Titel)-Paare aus dem <div id=anchor_id>...
    Abschnitt, bis der naechste morning-/noon-/evening-Anker beginnt."""
    anker = soup.find(id=anchor_id)
    if anker is None:
        return []

    eintraege = []
    for element in anker.find_all_next():
        if element.name == "div" and element.get("id") in ("morning", "noon", "evening"):
            break
        if element.name == "a" and (element.get("onclick") or "").startswith("return app.epg.load"):
            label = element.select_one("label")
            titel_tag = element.select_one("h2")
            if not label or not titel_tag:
                continue
            zeit_text = label.get_text(strip=True)
            titel = re.sub(r"\s+", " ", titel_tag.get_text(" ", strip=True)).strip()
            if zeit_text and titel:
                eintraege.append((zeit_text, titel))
    return eintraege


def _in_tagesbloecke_normalisieren(bloecke, erwartete_anzahl):
    """Erzwingt genau `erwartete_anzahl` Bloecke: ueberzaehlige Bloecke
    werden an den letzten gueltigen Block angehaengt (best effort statt
    Datenverlust), fehlende Bloecke werden als leere Liste ergaenzt."""
    if len(bloecke) > erwartete_anzahl:
        ueberschuss = bloecke[erwartete_anzahl:]
        bloecke = bloecke[:erwartete_anzahl]
        if bloecke:
            for extra in ueberschuss:
                bloecke[-1].extend(extra)
    while len(bloecke) < erwartete_anzahl:
        bloecke.append([])
    return bloecke


def _nach_ruecksprung_teilen(eintraege, erwartete_anzahl):
    """Fuer "morning"/"noon": neuer Tag beginnt, sobald die Uhrzeit
    gegenueber der vorherigen Sendung zurueckspringt (kein Mitternacht-
    Ueberlauf in diesen Abschnitten)."""
    bloecke = []
    aktuell = []
    letzte_minute = -1
    for zeit_text, titel in eintraege:
        minute = _zeit_zu_minuten(zeit_text)
        if minute is None:
            continue
        if aktuell and minute < letzte_minute:
            bloecke.append(aktuell)
            aktuell = []
        aktuell.append((zeit_text, titel))
        letzte_minute = minute
    if aktuell:
        bloecke.append(aktuell)
    return _in_tagesbloecke_normalisieren(bloecke, erwartete_anzahl)


def _nach_tagesende_marker_teilen(eintraege, erwartete_anzahl):
    """Fuer "evening": ein Tag endet erst beim expliziten "Kraj
    programa"-Eintrag (nicht bei der Uhrzeit selbst, die durch den
    Mitternacht-Ueberlauf sonst nicht von einem echten Tageswechsel
    unterscheidbar waere)."""
    bloecke = []
    aktuell = []
    for zeit_text, titel in eintraege:
        aktuell.append((zeit_text, titel))
        if titel.strip().lower() == _TAGESENDE_MARKER:
            bloecke.append(aktuell)
            aktuell = []
    if aktuell:
        bloecke.append(aktuell)
    return _in_tagesbloecke_normalisieren(bloecke, erwartete_anzahl)


def _laden(schluessel):
    """Laedt und parst (und cached) den 8-Tage-Sendeplan fuer den
    gegebenen Schluessel. Liefert eine Liste von {"title", "beschreibung",
    "bild", "start", "stop"}-Dicts (UTC), oder [] bei jedem Fehler."""
    if schluessel in _programme_cache:
        return _programme_cache[schluessel]

    slug = _SLUGS.get(schluessel)
    if not slug:
        return []

    try:
        url = BASIS_URL.format(slug=slug)
        response = _http.mit_retry(requests.get, url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        tab_container = soup.select_one("#epg_top")
        anzahl_tage = len(tab_container.select("span.font-normal")) if tab_container else 0
        if not anzahl_tage:
            print("RTL-Adria-EPG: keine Tages-Reiter gefunden, ueberspringe.")
            _programme_cache[schluessel] = []
            return []

        heute = datetime.now(TZ_ZAGREB).date()
        tag_daten = [heute + timedelta(days=i) for i in range(anzahl_tage)]

        morgen_bloecke = _nach_ruecksprung_teilen(_abschnitt_eintraege(soup, "morning"), anzahl_tage)
        mittag_bloecke = _nach_ruecksprung_teilen(_abschnitt_eintraege(soup, "noon"), anzahl_tage)
        abend_bloecke = _nach_tagesende_marker_teilen(_abschnitt_eintraege(soup, "evening"), anzahl_tage)

        rohe_eintraege = []
        for tag_index, tag_datum in enumerate(tag_daten):
            tages_eintraege = morgen_bloecke[tag_index] + mittag_bloecke[tag_index] + abend_bloecke[tag_index]

            aktuelles_datum = tag_datum
            letzte_minute = -1
            for zeit_text, titel in tages_eintraege:
                minute = _zeit_zu_minuten(zeit_text)
                if minute is None:
                    continue
                if letzte_minute != -1 and minute < letzte_minute:
                    aktuelles_datum = aktuelles_datum + timedelta(days=1)
                letzte_minute = minute

                stunde, teil_minute = divmod(minute, 60)
                start_lokal = datetime(
                    aktuelles_datum.year, aktuelles_datum.month, aktuelles_datum.day,
                    stunde, teil_minute, tzinfo=TZ_ZAGREB,
                )
                rohe_eintraege.append({"start_lokal": start_lokal, "titel": titel})

        programme = []
        for i, eintrag in enumerate(rohe_eintraege):
            if eintrag["titel"].strip().lower() == _TAGESENDE_MARKER:
                continue

            start = eintrag["start_lokal"].astimezone(timezone.utc)
            if i + 1 < len(rohe_eintraege):
                stop = rohe_eintraege[i + 1]["start_lokal"].astimezone(timezone.utc)
            else:
                stop = start + timedelta(hours=1)
            if stop <= start:
                continue

            programme.append({
                "title": eintrag["titel"],
                "beschreibung": eintrag["titel"],
                "bild": None,
                "start": start,
                "stop": stop,
            })

        print(f"RTL-Adria-EPG: {len(programme)} Sendungen ueber {anzahl_tage} Tage geladen.")
        _programme_cache[schluessel] = programme
        return programme
    except Exception as e:
        print(f"RTL-Adria-EPG: Laden/Parsen fehlgeschlagen ({e}), ueberspringe.")
        _programme_cache[schluessel] = []
        return []


def rtl_hr_hole_programme(schluessel, tage=2):
    """Liefert die bereits geladenen Programmdaten fuer die naechsten
    `tage` Tage ab heute (Europe/Zagreb). Leere Liste bei jedem Fehler."""
    if not schluessel:
        return []

    eintraege = _laden(schluessel)
    if not eintraege:
        return []

    heute = datetime.now(TZ_ZAGREB).date()
    erlaubte_tage = {heute + timedelta(days=i) for i in range(tage)}

    return [
        p for p in eintraege
        if p["start"].astimezone(TZ_ZAGREB).date() in erlaubte_tage
        or p["stop"].astimezone(TZ_ZAGREB).date() in erlaubte_tage
    ]
