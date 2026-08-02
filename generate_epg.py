from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo
import os
import re
import requests
import xml.etree.ElementTree as ET
import zlib

from epg_lib import (
    KATEGORIEN, KATEGORIE_PRIORITAET,
    DE_STANDARD, EXYU_STANDARD, EN_STANDARD,
    EXYU_LAENDER, UK_LAENDER, US_LAENDER, EN_LAENDER,
    ALTERSFREIGABE, DEFAULT_ALTERSFREIGABE,
    TAGESRASTER, FALLBACK_LABEL, SENDETITEL_VORLAGEN, WOCHENTAGE,
    sprache_fuer_land, sendetitel, beschreibung_fuer_sender,
    sender_anzeigename, standard_beschreibung, kategorie_label,
    parse_event_zeit, datumspraefix, vorbericht_text,
    kanalname_normal_geschrieben,
    normalisiere_sendername, baue_logo_index, finde_logo,
)


def segmente_ohne_ueberlappung(seg_start, seg_ende, ueberlappungs_fenster):
    """Schneidet aus [seg_start, seg_ende) alle ueberlappenden Fenster
    heraus und liefert die verbleibenden (ggf. mehreren) Teilstuecke
    zurueck. Ohne Ueberlappung kommt genau [(seg_start, seg_ende)] zurueck,
    bei voller Ueberdeckung eine leere Liste."""
    segmente = [(seg_start, seg_ende)]
    for fenster_start, fenster_ende in ueberlappungs_fenster:
        neue_segmente = []
        for s, e in segmente:
            if fenster_ende <= s or fenster_start >= e:
                neue_segmente.append((s, e))
                continue
            if fenster_start > s:
                neue_segmente.append((s, fenster_start))
            if fenster_ende < e:
                neue_segmente.append((fenster_ende, e))
        segmente = neue_segmente
    return segmente


def schreibe_programme_segmente(
    xml_teile, segmente, kanal, titel_text, beschr_text, lang_code,
    kategorie_key, land, ist_live,
):
    """Schreibt <programme>-Eintraege fuer die gegebenen Zeit-Segmente mit
    identischem Titel/Beschreibung/Kategorie - genutzt sowohl fuer den
    generischen Tagesraster-Block als auch fuer praezise erkannte Events,
    damit die Segmentierung (Luecken-/Ueberlappungsvermeidung) an einer
    Stelle gebuendelt ist."""
    label = kategorie_label(kategorie_key, land)
    category_tags = ""
    if label:
        category_tags += f' <category lang="{lang_code}">{escape(label)}</category>'
    if ist_live:
        live_label = {"de": "Live", "hr": "Uživo", "sl": "V živo", "mk": "Vo živo"}.get(lang_code, "Live")
        category_tags += f' <category lang="{lang_code}">{escape(live_label)}</category>'

    altersfreigabe = ALTERSFREIGABE.get(kategorie_key, DEFAULT_ALTERSFREIGABE)
    rating_tag = f' <rating system="FSK"><value>{altersfreigabe}</value></rating>'

    beschr_escaped = escape(beschr_text)
    desc_tag = f' <desc lang="{lang_code}">{beschr_escaped}</desc>'
    sub_title_tag = f' <sub-title lang="{lang_code}">{beschr_escaped}</sub-title>'

    for seg_start, seg_ende in segmente:
        seg_start_str = seg_start.strftime("%Y%m%d%H%M%S +0000")
        seg_ende_str = seg_ende.strftime("%Y%m%d%H%M%S +0000")
        xml_teile.append(
            f' <programme start="{seg_start_str}" stop="{seg_ende_str}" channel="{escape(kanal)}">'
            f' <title lang="{lang_code}">{titel_text}</title>'
            f'{sub_title_tag}'
            f'{desc_tag}{category_tags}{rating_tag} </programme> '
        )


def kern_und_event_extrahieren(voller_name):
    """Trennt einen rohen Kanalnamen in (Kurzname/Kern, Event-Text) nach
    der Pipe-Konvention: der Abschnitt NACH dem letzten Pipe-Zeichen gilt
    als stabiler Kern (z.B. "DE: DYN PPV 1" -> "DYN PPV 1"), alles davor
    als potenzieller Event-Text. Ohne Pipe wird auf das bekannte
    DYN-PPV/FLO-RACING-Doppelpunkt-Muster zurueckgefallen. Wird sowohl
    beim Einlesen von sender.txt als auch beim Auslesen der Live-
    Kanalnamen aus der EPG-Anbieter-Datei verwendet."""
    if "|" in voller_name:
        segmente = voller_name.split("|")
        kern_roh = segmente[-1].strip()
        event_teil = "|".join(segmente[:-1]).strip()
        # Ein reiner 2-4-Buchstaben-Code vor dem Pipe (z.B. "NA| Bakersfield
        # Condors") ist ein Land-/Regionskuerzel wie anderswo in sender.txt
        # ("US|", "DE|", ...), kein echter Event-Text - echte Event-Texte
        # sind immer deutlich laenger (Teamnamen, Uhrzeiten usw.).
        if re.fullmatch(r"[A-Za-z]{2,4}", event_teil):
            event_teil = ""
        kurzname = re.sub(r"^[A-Za-z]{2}\s*:\s*", "", kern_roh).strip()
        if not kurzname:
            kurzname = kern_roh
    else:
        kurzname_match = re.search(r"(DYN\s*PPV|FLO\s*RACING)\s*\d+", voller_name, re.IGNORECASE)
        if kurzname_match and kurzname_match.start() > 0:
            kurzname = kurzname_match.group(0)
            event_teil = voller_name[:kurzname_match.start()].strip(" :").strip()
        else:
            kurzname = voller_name
            event_teil = ""
    return kurzname, event_teil

# ==========================================================
# ZENTRALE KONFIGURATION
#
# Alle frei "tunbaren" Werte an einer Stelle statt ueber die Datei
# verstreut. Wer z.B. die EPG-Laenge, die Anzahl der DYN-PPV-Kanaele
# oder das Event-Zeitfenster anpassen will, muss nur hier suchen.
# ==========================================================

# Wie viele Tage im Voraus das Standard-EPG (Tagesraster-Bloecke)
# erzeugt wird.
ANZAHL_TAGE = 3

# Anzahl der DYN-PPV-Kanaele (DE| DYN PPV 1 HD ... DE| DYN PPV N HD).
DYN_PPV_ANZAHL = 20

# Wie lange ein per parse_event_zeit() erkanntes DYN/Flo-Racing-Event
# im EPG als Zeitfenster eingetragen wird (Stunden).
DYN_EVENT_DAUER_STUNDEN = 2

# Wie viele Tage im Voraus die "DYN Leerzeiten" (Platzhalter ohne
# erkanntes Live-Event) vorbefuellt werden. Bleibt bewusst identisch
# zu ANZAHL_TAGE, ist aber eigenstaendig konfigurierbar, falls die
# Leerzeiten mal laenger/kuerzer als das Standard-EPG laufen sollen.
DYN_LEERZEIT_TAGE = ANZAHL_TAGE

# Standard-Logo fuer DYN-PPV-Kanaele, falls kein individuelles Logo
# in dyn_ppv_logo_overrides hinterlegt ist.
DYN_STANDARD_LOGO = "https://www.dslweb.de/public/resources/images/anbieter/dyn/dyn-teaser.jpg"

# DYN Live-Events API: Liste von Endpunkten in Prioritaets-Reihenfolge.
# Der erste erreichbare Endpunkt (HTTP 200) wird verwendet. Aktuell ist
# nur der offizielle Endpunkt bekannt - die Liste ist aber vorbereitet,
# falls spaeter ein Spiegel-/Fallback-Endpunkt hinzukommt (einfach als
# weiteren String ergaenzen, keine Codeaenderung noetig).
DYN_API_ENDPUNKTE = [
    "https://streaming.contentdesk.sport/api/public/live-productions",
]
DYN_API_TIMEOUT_SEKUNDEN = 15

# Clubber-PPV (Irland, GAA-Club-Spiele): analog zur DYN-API, aber die
# Kernnamen der 50 echten Kanaele stehen VORNE im Kanalnamen (z.B.
# "(IE) (Clubber 01)"), nicht hinten wie bei DYN - deshalb kommt hier
# KEINE Playlist-Namen-Extraktion zum Einsatz, sondern ausschliesslich
# die API, per Kernname-Regex den 50 echten Sendern zugeordnet.
CLUBBER_API_ENDPUNKTE = [
    "https://prodgameservicecontainer.azurewebsites.net/api/Game/GetUpcomingGames",
]
CLUBBER_API_TIMEOUT_SEKUNDEN = 15

# Clubber liefert keine Endzeit, nur Datum+Uhrzeit (irische Lokalzeit) -
# angenommene feste Spieldauer.
CLUBBER_EVENT_DAUER_STUNDEN = 2.5

# Zeitzone der Clubber-API-Zeitangaben (Irland).
CLUBBER_ZEITZONE = ZoneInfo("Europe/Dublin")

# Bekannte Leerlauf-Platzhalter-Texte fuer NAME:-Sender (Pipe-
# Konvention, siehe Einlese-Logik weiter unten). Enthaelt der
# Event-Teil eines Kanalnamens einen dieser Texte (Gross-/
# Kleinschreibung egal), gilt der Sender als "kein Event laeuft" -
# es bleibt beim generischen Standardtext statt des Kanalnamen-
# Fragments. Neue Anbieter mit eigenem Platzhaltertext (z.B. in
# einer anderen Sprache) koennen hier einfach ergaenzt werden, ohne
# die Einlese-Logik selbst anfassen zu muessen.
LEERLAUF_MARKER = ["no event", "kein event", "nema eventa", "ni dogodka"]

# Status-Marker, die manche Anbieter (z.B. myepg.top) als erstes
# Pipe-Segment vor den eigentlichen Event-Namen setzen ("NEXT | ...",
# "End | ..."). Werden erkannt und in verstaendlichen deutschen
# EPG-Text uebersetzt statt den rohen englischen Marker anzuzeigen.
EVENT_MARKER_NEXT = ["next"]
EVENT_MARKER_ENDE = ["end", "ended", "endet"]
EVENT_ENDE_TEXT = (
    "Spiel ist beendet, danke, dass Sie zugeschaut haben. Ihr DYN Sport Team"
)


def formatiere_event_text(event_teil):
    """Erkennt einen bekannten Status-Marker (NEXT/END) im ersten Pipe-
    Segment eines rohen Event-Texts und baut daraus verstaendlichen
    deutschen EPG-Text: "NEXT | X" -> "Es folgt: X", "End | X" -> festen
    Abmoderationstext. Ohne erkannten Marker (z.B. bei "Live | ...")
    bleibt der Text unveraendert."""
    segmente = [s.strip() for s in event_teil.split("|")]
    marker = segmente[0].lower() if segmente else ""

    if marker in EVENT_MARKER_ENDE:
        return EVENT_ENDE_TEXT

    if marker in EVENT_MARKER_NEXT:
        rest = " | ".join(s for s in segmente[1:] if s).strip()
        if rest:
            return f"Es folgt: {rest}"
        return "Es folgt in Kürze ein neues Event"

    return event_teil

# Automatische Logo-Suche: fehlt einem Sender in sender.txt/
# logo_only.txt ein Logo, wird versucht, es automatisch ueber die
# oeffentliche iptv-org-Kanaldatenbank zu finden (per Namensabgleich).
# Kein Bezug zu einer konkreten IPTV-Quelle - rein oeffentliche
# Metadaten (Kanalname -> Logo-URL). Bei Nichterreichbarkeit wird die
# Suche automatisch uebersprungen (siehe Try/Except weiter unten).
LOGO_AUTO_SUCHE_AKTIV = True
LOGO_DB_CHANNELS_URL = "https://iptv-org.github.io/api/channels.json"
LOGO_DB_LOGOS_URL = "https://iptv-org.github.io/api/logos.json"
LOGO_DB_TIMEOUT_SEKUNDEN = 30
LOGO_MATCH_MIN_SCORE = 0.72

# Schluesselwort, das explizit ins Logo-Feld geschrieben werden muss,
# damit die automatische Suche fuer GENAU diesen Sender ausgeloest
# wird (z.B. "DE|Pro7||AUTO"). Ein einfach leeres Logo-Feld (wie es
# bei den meisten 2-Pipe-Eintraegen "DE| Pro7" der Fall ist, wo das
# Logo bisher schon direkt aus der Playlist selbst kommt) loest KEINE
# automatische Suche aus - nur wer wirklich Hilfe beim Logo braucht,
# schreibt das Schluesselwort explizit dazu.
LOGO_AUTO_MARKER = "AUTO"

# ==========================================================
# XML starten (Teile werden gesammelt und am Ende gejoint,
# statt bei jedem Schritt einen neuen String zu bauen)
# ==========================================================

xml_teile = ['<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n']

sender_daten = []

# ==========================================================
# sender.txt lesen
#
# Format (bis zu 4 Spalten, alles nach Sender ist optional):
#
# Land|Sender
# Land|Sender|Beschreibung
# Land|Sender|Beschreibung|Logo-URL
#
# Wird kein Logo angegeben, wird KEIN <icon>-Tag erzeugt -
# der Player/die Playlist behält dann ihr eigenes Logo.
# ==========================================================

try:
    with open("sender.txt", "r", encoding="utf-8") as f:
        zeilen = f.readlines()
except FileNotFoundError:
    raise SystemExit("Fehler: sender.txt wurde nicht gefunden.")

for zeile in zeilen:

    zeile = zeile.strip()

    if not zeile or zeile.startswith("#"):
        continue

    # NAME:-Präfix: für Sender, deren echter Playlist-Name selbst
    # Pipe-Zeichen enthält (z.B. "- NO EVENT STREAMING - | 8K
    # EXCLUSIVE | DE: DYN PPV 1"). Normales Land|Sender|Beschreibung|
    # Logo-Format würde so einen Namen an den falschen Stellen
    # zerschneiden. Bei "NAME:" wird stattdessen nur am LETZTEN Pipe
    # der Zeile getrennt - alles davor ist der komplette, unveränderte
    # Kanalname (wird 1:1 als id/display-name verwendet, keine
    # Land|Sender-Rekonstruktion), alles danach das Logo.
    if zeile.upper().startswith("NAME:"):
        rest = zeile[5:]
        teile_name = rest.rsplit("|", 1)

        if len(teile_name) != 2:
            continue

        voller_name = teile_name[0].strip()
        logo = teile_name[1].strip()

        if not voller_name:
            continue

        # Für den Sendungstitel NICHT den kompletten Rohnamen
        # wiederverwenden - der ist fast identisch mit dem Kanalnamen
        # selbst (nur andere Groß-/Kleinschreibung). Viele Player
        # (u.a. TiviMate) interpretieren einen Sendungstitel, der
        # praktisch gleich dem Kanalnamen ist, als "keine echten
        # Daten" und zeigen dann trotz vorhandener <title>/<desc>
        # nur "Keine Information" an. Stattdessen wird der stabile
        # Kern des Namens herausgelöst, falls vorhanden - das
        # unterscheidet sich klar vom Kanalnamen.
        #
        # STANDARDISIERTE PIPE-KONVENTION (funktioniert automatisch
        # fuer JEDEN Sender im NAME:-Format, unabhaengig vom Anbieter -
        # kein hartcodiertes Anbieter-Muster wie "DYN PPV"/"FLO RACING"
        # mehr noetig):
        #
        # Der Abschnitt NACH dem LETZTEN Pipe-Zeichen im Kanalnamen
        # (vor dem Logo-Pipe) gilt als der feste, sich nicht
        # aendernde "Kern" des Senders - z.B.
        #   "ENDED | DEUTSCHLAND - GUINEA | IHF U18 WOMEN'S... | DE: DYN PPV 1"
        #                                                         ^^^^^^^^^^^^^ Kern
        # Alles DAVOR gilt automatisch als potenzieller Event-Text.
        # Wer also einen neuen Sender (DAZN, ESPN, etc.) im NAME:-
        # Format mit derselben Pipe-Konvention in sender.txt eintraegt
        # ("<Event-Text, falls vorhanden> | ... | <Land>: <Kern-Sendername>|<Logo>"),
        # bekommt automatisch dieselbe Event-Extraktion - ohne
        # Code-Aenderung noetig.
        #
        # Ausnahme: Namen OHNE jegliches Pipe-Zeichen (z.B. Flo Racing
        # im Doppelpunkt-Format "Sa 14:00 : Flo Racing 05" oder im
        # Leerlauf nur "Flo Racing 03") - hier greift die Pipe-
        # Konvention nicht, daher Fallback auf das bekannte
        # DYN-PPV/FLO-RACING-Muster (siehe kern_und_event_extrahieren()).
        kurzname, event_teil = kern_und_event_extrahieren(voller_name)

        # Land-Praefix wie "NA|", "US|" am ANFANG des Namens (nicht zu
        # verwechseln mit echtem Event-Text vor dem Pipe) wird als Land
        # fuer Sprache/Kategorie-Erkennung genutzt - z.B. bekommen
        # NA-Sender dadurch englische statt deutsche Beschreibungen.
        # Der Kanalname/die ID selbst bleibt trotzdem exakt der rohe
        # Originaltext (wichtig fuers Playlist-Matching, falls dort ein
        # Leerzeichen nach dem Pipe steht). Nur wenn kein echtes Event
        # erkannt wurde (event_teil leer) greift das, sonst waere ein
        # Land-Kuerzel vor einem echten Event faelschlich als Land
        # missverstanden.
        land = "DE"
        land_praefix_match = re.match(r"^([A-Za-z]{2,4})\|", voller_name)
        if land_praefix_match and not event_teil:
            land = land_praefix_match.group(1).upper()

        beschreibung, kategorie_key = standard_beschreibung(land, kurzname)

        # Clubber-PPV-Kanaele explizit als SPORT einordnen: das
        # Kurzwort "CLUB" (Teil von "CLUBBER") ist bereits als
        # MUSIK-Keyword belegt (z.B. "NRJ Club") und steht in der
        # Kategorie-Prioritaet vor SPORT - eine globale Erweiterung der
        # Keyword-Liste wuerde diese Kollision fuer alle Sender
        # riskieren, daher wird hier gezielt nur fuer Clubber die
        # SPORT-Kategorie mit dem echten Kurznamen nachgebaut (gleiche
        # Logik wie in standard_beschreibung(), nur fest auf SPORT).
        if re.search(r"CLUBBER\s*\d+", kurzname, re.IGNORECASE):
            kategorie_key = "SPORT"
            sport_daten = KATEGORIEN["SPORT"]
            hash_wert_sport = sum(ord(c) for c in kurzname)
            varianten_sport = sport_daten["DE"]
            beschreibung = varianten_sport[hash_wert_sport % len(varianten_sport)].format(
                sender=kurzname, label=sport_daten["label"]["DE"]
            )

        # Steht vor dem Kern zusaetzlicher, nicht-generischer Text ->
        # Event laeuft, dieser Text wird als Sendungstitel/-
        # beschreibung uebernommen. Steht nichts oder nur ein
        # bekannter "NO EVENT"-Platzhalter davor -> Leerlauf, es
        # bleibt beim generischen Standardtext (beschreibung s.o.).
        event_titel = None

        if event_teil and not any(marker in event_teil.lower() for marker in LEERLAUF_MARKER):
            event_titel = formatiere_event_text(event_teil)

        sender_daten.append({
            "kanal": voller_name,
            "land": land,
            "sender": kurzname,
            "beschreibung": beschreibung,
            "logo": logo,
            "exakter_name": True,
            "event_titel": event_titel,
            "kategorie": kategorie_key
        })
        continue

    teile = [x.strip() for x in zeile.split("|")]

    while len(teile) < 4:
        teile.append("")

    land = teile[0]
    sender = teile[1]
    beschreibung = teile[2]
    logo = teile[3]
    kanal = f"{land}|{sender}"

    auto_beschreibung, kategorie_key = standard_beschreibung(land, sender)

    if beschreibung == "":
        beschreibung = auto_beschreibung

    # DAZN-Sender: im Gegensatz zu DYN PPV/Flo Racing aendert sich der
    # Kanalname bei DAZN NICHT dynamisch (kein Event-Text im Namen
    # selbst). Trotzdem soll hier nicht die generische, kategorie-
    # basierte Standardbeschreibung erscheinen, sondern schlicht der
    # eigentliche Kanalname selbst (z.B. "DAZN Bar 1 HD"), damit im
    # EPG-Raster erkennbar ist, um welchen konkreten DAZN-Sender es
    # sich handelt statt eines generischen Sport-Textes.
    dazn_event_titel = kanalname_normal_geschrieben(sender) if "DAZN" in sender.upper() else None

    sender_daten.append({
        "kanal": kanal,
        "land": land,
        "sender": sender,
        "beschreibung": beschreibung,
        "logo": logo,
        "exakter_name": False,
        "event_titel": dazn_event_titel,
        "kategorie": kategorie_key
    })

# ==========================================================
# logo_only.txt lesen (optional)
#
# Für Sender, bei denen NUR das Logo gesetzt/geändert werden
# soll - z.B. weil das eigentliche EPG (die Programme) von
# einer anderen Quelle kommt und nicht überschrieben werden soll.
#
# Zwei Zeilenformate werden unterstützt:
#
# 1) Normale Sender (Land + Sendername getrennt):
#    Land|Sender|Logo-URL
#    Land|Sender||Logo-URL   (gleiches Schema wie sender.txt)
#
# 2) Kanalnamen mit Pipe-Zeichen im Namen selbst (z.B. Namen wie
#    "- NO EVENT STREAMING - | 8K EXCLUSIVE | DE: DYN PPV 1"):
#    NAME:<kompletter Kanalname exakt wie in der Playlist>|Logo-URL
#    Hier wird NUR das letzte "|" in der Zeile als Trenner zur
#    Logo-URL verwendet - alles davor (nach "NAME:") ist der Name,
#    egal wie viele Pipes darin vorkommen.
#
#    Das gilt auch für Sender mit täglich wechselndem Namen (z.B.
#    Live-Event-Kanäle wie "(Victory+ 001) | VNL Men's Live Matches :
#    France vs Belgium"). Hier reicht der stabile Teil in Klammern:
#    NAME:(Victory+ 001)|Logo-URL
#    oder kurz (funktioniert automatisch, sobald nur ein "|" in der
#    Zeile vorkommt):
#    (Victory+ 001)|Logo-URL
#
#    Ablauf für dieses Format:
#    a) Zuerst wird per TEILSTRING-Suche (Groß-/Kleinschreibung egal)
#       geprüft, ob ein Sender aus sender.txt diesen Text enthält.
#       Bei Treffer(n) wird dort NUR das Logo überschrieben.
#    b) Kein Treffer? Dann wird ein eigenständiger <channel>-Block
#       angelegt - mit mehreren <display-name>-Varianten (mit und
#       ohne Klammern), damit der Player den Sender trotz wechselndem
#       vollen Namen per Teilstring zuordnen kann.
#
# - Steht der Sender bereits in sender.txt (Format 1), wird dort
#   nur das Logo überschrieben (kein zusätzlicher Eintrag).
# - Sonst wird nur ein <channel>-Block mit Icon angelegt - OHNE
#   <programme>-Platzhalter, damit das echte EPG dieser Quelle
#   erhalten bleibt.
# ==========================================================

kanal_index = {d["kanal"]: d for d in sender_daten}
logo_only_channels = []
gesehene_logo_only_kanaele = set()

# Logo-Overrides für die fest eingebauten DYN-PPV-Kanäle (1-20).
# Diese Kanäle existieren bereits als eigener <channel>-Block mit
# eigener id ("DE| DYN PPV {i} HD") und bekommen dort auch ihre
# Programme (Live-Events/Leerzeiten) zugewiesen. Ein Logo-Eintrag
# in logo_only.txt für einen DYN-PPV-Sender darf deshalb KEINEN
# eigenständigen neuen Channel erzeugen (sonst gehen die Programme
# an der falschen, neuen Channel-id vorbei) - stattdessen wird hier
# nur das Logo für die passende Nummer gemerkt.
dyn_ppv_logo_overrides = {}
DYN_PPV_MUSTER = re.compile(r"DYN\s*PPV\s*(\d+)", re.IGNORECASE)

try:
    with open("logo_only.txt", "r", encoding="utf-8") as f:
        logo_only_zeilen = f.readlines()
except FileNotFoundError:
    logo_only_zeilen = []

for zeile in logo_only_zeilen:

    zeile = zeile.strip()

    if not zeile or zeile.startswith("#"):
        continue

    ist_name_praefix = zeile.upper().startswith("NAME:")
    roh_teile = zeile.split("|")

    if ist_name_praefix or len(roh_teile) == 2:
        # Kompletter/kurzer Name + Logo-URL, getrennt durch das LETZTE
        # Pipe-Zeichen in der Zeile. "NAME:" Präfix ist optional - wird
        # automatisch erkannt, wenn die Zeile nur ein einziges Pipe hat
        # (z.B. "DE: DYN PPV 1|https://...") oder wenn "NAME:" davor steht
        # (für Namen, die selbst mehrere Pipes enthalten).
        rest = zeile[5:] if ist_name_praefix else zeile
        teile_name = rest.rsplit("|", 1)

        if len(teile_name) != 2:
            continue

        voller_name = teile_name[0].strip()
        logo = teile_name[1].strip()

        if not voller_name or not logo:
            continue

        # a) Teilstring-Treffer gegen bereits bekannte Sender aus
        # sender.txt suchen (z.B. wenn nur "(Victory+ 001)" angegeben
        # wird, der volle Sendername in sender.txt aber
        # "(Victory+ 001) | VNL Men's Live Matches : ..." lautet).
        suchtext = voller_name.lower()
        treffer = [
            d for d in sender_daten
            if suchtext in d["sender"].lower()
        ]

        if treffer:
            for d in treffer:
                d["logo"] = logo
            print(
                f"logo_only.txt: '{voller_name}' per Teilstring auf "
                f"{len(treffer)} Sender aus sender.txt angewendet."
            )
            continue

        # b) Kein Treffer in sender.txt: prüfen, ob es sich um einen
        # DYN-PPV-Sender handelt (z.B. "DE: DYN PPV 1"). Diese Kanäle
        # gibt es weiter unten bereits fest mit eigener Channel-id und
        # eigenen Programmen - hier deshalb NUR das Logo überschreiben,
        # statt einen zweiten, konkurrierenden Channel anzulegen.
        dyn_match = DYN_PPV_MUSTER.search(voller_name)
        if dyn_match:
            nummer = int(dyn_match.group(1))
            dyn_ppv_logo_overrides[nummer] = logo
            print(
                f"logo_only.txt: '{voller_name}' als DYN-PPV-Logo-Override "
                f"für Kanal {nummer} übernommen."
            )
            continue

        # Sonst: eigenständigen Channel anlegen. Klammerinhalt zusätzlich
        # als Alias ohne Klammern herauslösen, damit der Player mehr
        # Chancen zur Zuordnung per Teilstring hat.
        kanal = voller_name

        if kanal not in gesehene_logo_only_kanaele:
            aliase = [voller_name]

            klammer_match = re.search(r"\(([^)]+)\)", voller_name)
            if klammer_match:
                klammer_inhalt = klammer_match.group(1).strip()
                if klammer_inhalt and klammer_inhalt not in aliase:
                    aliase.append(klammer_inhalt)

            ohne_klammern = re.sub(r"[()]", "", voller_name).strip()
            if ohne_klammern and ohne_klammern not in aliase:
                aliase.append(ohne_klammern)

            logo_only_channels.append({
                "kanal": kanal,
                "voller_name": voller_name,
                "aliase": aliase,
                "logo": logo
            })
            gesehene_logo_only_kanaele.add(kanal)

        continue

    # Format 1: Land|Sender|Logo bzw. Land|Sender||Logo
    teile = [x.strip() for x in zeile.split("|")]

    # Gleiches Spaltenschema wie sender.txt: Land|Sender|Beschreibung|Logo
    # Die Beschreibung-Spalte wird hier ignoriert, das Logo ist immer
    # die letzte (4.) Spalte. Wird nur "Land|Sender|Logo" mit 3 Spalten
    # angegeben, ist das Logo dann Spalte 3.
    while len(teile) < 4:
        teile.append("")

    land = teile[0]
    sender = teile[1]
    logo = teile[3] if teile[3] else teile[2]

    if not logo:
        continue

    kanal = f"{land}|{sender}"

    if kanal in kanal_index:
        # Logo für bereits vorhandenen Sender überschreiben
        kanal_index[kanal]["logo"] = logo
    elif kanal not in gesehene_logo_only_kanaele:
        # Neuer, eigenständiger Channel NUR mit Icon, ohne Programme
        logo_only_channels.append({
            "kanal": kanal,
            "land": land,
            "sender": sender,
            "logo": logo
        })
        gesehene_logo_only_kanaele.add(kanal)

# ==========================================================
# AUTOMATISCHE LOGO-SUCHE (siehe LOGO_AUTO_SUCHE_AKTIV oben)
#
# Fuer alle Sender, die auch nach sender.txt UND logo_only.txt immer
# noch kein Logo haben, wird hier versucht, automatisch ein
# passendes Logo aus der oeffentlichen iptv-org-Kanaldatenbank zu
# finden (Namensabgleich, kein Bezug zu einer konkreten IPTV-Quelle).
# Manuelle Eintraege (sender.txt/logo_only.txt) haben IMMER Vorrang -
# hier wird nur das Luecken-Ausfuellen fuer Sender ohne Logo gemacht.
# Ist die Datenbank nicht erreichbar (kein Internet, Rate-Limit,
# etc.), wird die Suche einfach uebersprungen - bestehende Sender
# bleiben dann wie bisher ohne <icon>, es gibt keinen Fehlerabbruch.
# ==========================================================

if LOGO_AUTO_SUCHE_AKTIV and any(
    d["logo"].strip().upper() == LOGO_AUTO_MARKER for d in sender_daten
):
    logo_name_index = None
    logo_by_id = None

    try:
        channels_response = requests.get(LOGO_DB_CHANNELS_URL, timeout=LOGO_DB_TIMEOUT_SEKUNDEN)
        logos_response = requests.get(LOGO_DB_LOGOS_URL, timeout=LOGO_DB_TIMEOUT_SEKUNDEN)

        if channels_response.status_code == 200 and logos_response.status_code == 200:
            logo_name_index, logo_by_id = baue_logo_index(
                channels_response.json(), logos_response.json()
            )
        else:
            print(
                "Automatische Logo-Suche uebersprungen: Kanal-Datenbank "
                f"nicht erreichbar (HTTP {channels_response.status_code}/"
                f"{logos_response.status_code})."
            )
    except Exception as e:
        print("Automatische Logo-Suche uebersprungen (Fehler beim Abruf):", e)

    if logo_name_index:
        anzahl_gefunden = 0
        anzahl_angefragt = 0
        for daten in sender_daten:
            # NUR Sender mit explizitem "AUTO"-Marker im Logo-Feld
            # werden angefragt - ein einfach leeres Logo-Feld (der
            # Normalfall bei 2-Pipe-Eintraegen, wo TiviMate das Logo
            # bereits direkt aus der Playlist zeigt) loest KEINE Suche
            # aus, um bestehende Playlist-Logos nicht zu "stoeren".
            if daten["logo"].strip().upper() != LOGO_AUTO_MARKER:
                continue

            anzahl_angefragt += 1
            gefundenes_logo = finde_logo(
                daten["sender"], daten.get("land", ""),
                logo_name_index, logo_by_id,
                min_score=LOGO_MATCH_MIN_SCORE
            )
            # Wird nichts gefunden, darf das Wort "AUTO" NICHT als
            # (ungueltige) Logo-URL im XML landen - dann bleibt das
            # Feld leer, wie es ein Sender ohne Logo-Angabe auch waere.
            daten["logo"] = gefundenes_logo if gefundenes_logo else ""
            if gefundenes_logo:
                anzahl_gefunden += 1

        print(
            f"Automatische Logo-Suche: {anzahl_gefunden} von "
            f"{anzahl_angefragt} angefragten Sender(n) ein Logo zugeordnet."
        )

# ==========================================================
# <channel>-Blöcke schreiben (sender.txt, mit ggf.
# überschriebenem Logo aus logo_only.txt)
# ==========================================================

for daten in sender_daten:

    # So wie er in der Playlist als tvg-name steht (z.B. "DE| RTL"),
    # unverändert übernommen - das ist entscheidend für die
    # automatische Sender-Zuordnung in TiviMate.
    # Ausnahme: Einträge mit "exakter_name" (aus NAME:-Zeilen in
    # sender.txt) haben ihren kompletten, echten Playlist-Namen
    # bereits direkt in "kanal" stehen - hier NICHT aus Land+Sender
    # neu zusammenbauen, sonst geht der Name kaputt.
    if daten.get("exakter_name"):
        playlist_name = daten["kanal"]
    else:
        playlist_name = f"{daten['land']}| {daten['sender']}"

    xml_teile.append(
        f' <channel id="{escape(daten["kanal"])}"> <display-name>{escape(playlist_name)}</display-name> '
    )

    # Icon wird NUR erzeugt, wenn ein Logo angegeben ist
    # (aus sender.txt oder als Override aus logo_only.txt)
    if daten["logo"]:
        xml_teile.append(f' <icon src="{escape(daten["logo"])}"/>\n')

    xml_teile.append("</channel>\n")

# ==========================================================
# <channel>-Blöcke für reine Logo-Einträge (kein Sender in
# sender.txt) - nur Icon, keine Programme
# ==========================================================

for daten in logo_only_channels:
    if "voller_name" in daten:
        namen = daten.get("aliase") or [daten["voller_name"]]
    else:
        namen = [f"{daten['land']}| {daten['sender']}"]

    xml_teile.append(f' <channel id="{escape(daten["kanal"])}">')

    for name in namen:
        xml_teile.append(f' <display-name>{escape(name)}</display-name>')

    xml_teile.append(
        f' <icon src="{escape(daten["logo"])}"/> </channel>\n'
    )

# ==========================================================
# DYN PPV CHANNELS
# ==========================================================

for i in range(1, DYN_PPV_ANZAHL + 1):
    kanal = f"DE| DYN PPV {i} HD"
    logo_fuer_kanal = dyn_ppv_logo_overrides.get(i, DYN_STANDARD_LOGO)
    xml_teile.append(
        f' <channel id="{escape(kanal)}"> <display-name>DYN PPV {i} HD</display-name> <icon src="{escape(logo_fuer_kanal)}"/> </channel> '
    )

# ==========================================================
# DYN LIVE EVENTS
# ==========================================================

# Generischer Index ALLER NAME:-Sender (nicht nur DYN PPV) nach
# normalisiertem Kernnamen - ermoeglicht es, den EPG-Anbieter-Abgleich
# (siehe "DYN LIVE-KANALNAMEN VOM EPG-ANBIETER" weiter unten) spaeter
# auch fuer weitere Kategorien (z.B. "US: SOCCER PPV" oder andere) ohne
# erneute Codeaenderung zu nutzen: es reicht, den neuen Sender per
# NAME:-Zeile in sender.txt einzutragen, sofern sein Kernname (Teil
# nach dem letzten Pipe-Zeichen bzw. nach "Land: ") exakt mit dem
# Kernnamen uebereinstimmt, den der Anbieter selbst im Kanalnamen fuehrt.
name_pipe_kanal_index = {}
for daten in sender_daten:
    if daten.get("exakter_name"):
        normalisierter_kern = re.sub(r"\s+", " ", daten["sender"]).strip().upper()
        name_pipe_kanal_index[normalisierter_kern] = daten

# Zeitfenster der API-Events je synthetischem "DE| DYN PPV N HD"-Kanal
# (1-20), analog zu api_event_fenster fuer die echten 1-50-Sender -
# wird unten bei den DYN LEERZEITEN gebraucht, um den ueberlappenden
# Teil der stuendlichen Platzhalter auszuschneiden.
dyn_synth_api_fenster = {}

try:
    response = None
    letzter_fehler = None

    for endpunkt in DYN_API_ENDPUNKTE:
        try:
            versuch = requests.get(endpunkt, timeout=DYN_API_TIMEOUT_SEKUNDEN)
            if versuch.status_code == 200:
                response = versuch
                break
            else:
                letzter_fehler = f"{endpunkt} -> HTTP {versuch.status_code}"
        except requests.RequestException as e:
            letzter_fehler = f"{endpunkt} -> {e}"

    if response is None:
        raise RuntimeError(
            f"Alle DYN-API-Endpunkte nicht erreichbar. Letzter Fehler: {letzter_fehler}"
        )

    if response.status_code == 200:
        daten = response.json()

        if len(daten) == 0:
            print("Keine DYN Live-Events - Standardtext wird erstellt")
        else:
            kanal_nummer = 1
            real_kanal_nummer = 1

            for event in daten:
                titel = event.get("title", "Dyn Sport")

                # Die API liefert kein eigenes Wettbewerb/Runde-Feld,
                # aber "streamingUrl" enthaelt den vollen Eventnamen als
                # Slug (z.B. ".../Spanien_Deutschland_IHF_U18_Womens_
                # Junior_WM_Vorrunde_102341") - das entspricht (bis auf
                # Satzzeichen) dem, was auch im echten Playlist-
                # Kanalnamen steht. Falls vorhanden, wird daraus ein
                # reichhaltigerer Titel gebaut statt des kurzen
                # "title"-Felds.
                streaming_url = event.get("streamingUrl")
                if streaming_url:
                    slug = streaming_url.rstrip("/").rsplit("/", 1)[-1]
                    slug = re.sub(r"_\d+$", "", slug)
                    voller_titel = slug.replace("_", " ").strip()
                    if voller_titel:
                        titel = voller_titel

                beschreibung = event.get("description", titel)

                start = event.get("scheduledAt")
                ende = event.get("scheduledEnd")

                if not start or not ende:
                    continue

                start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                ende_dt = datetime.fromisoformat(ende.replace("Z", "+00:00"))

                startzeit = start_dt.strftime("%Y%m%d%H%M%S +0000")
                endzeit = ende_dt.strftime("%Y%m%d%H%M%S +0000")

                kanal = f"DE| DYN PPV {kanal_nummer} HD"

                xml_teile.append(
                    f' <programme start="{startzeit}" stop="{endzeit}" channel="{escape(kanal)}">'
                    f' <title>{escape(titel)}</title> <desc>{escape(beschreibung)}</desc> </programme> '
                )

                dyn_synth_api_fenster.setdefault(kanal_nummer, []).append(
                    (start_dt, ende_dt)
                )

                kanal_nummer += 1
                if kanal_nummer > DYN_PPV_ANZAHL:
                    kanal_nummer = 1

except Exception as e:
    print("DYN Fehler:", e)

# ==========================================================
# LIVE-KANALNAMEN VOM EPG-ANBIETER (alle NAME:-Sender, z.B. DYN PPV)
# ==========================================================
#
# Statt Events per Round-Robin zu raten (unzuverlaessig - siehe
# Clubber, wo sich das als falsch erwiesen hat), werden hier die
# echten Live-Kanalnamen direkt aus der EPG-Datei des Nutzer-eigenen
# EPG-Anbieters gelesen. Dieser Anbieter spiegelt die tatsaechlichen
# Live-Playlist-Kanalnamen (inkl. Event-Text) direkt in seine
# <channel>-Definitionen (bestaetigt am Beispiel "US: SOCCER PPV") -
# das ist die echte, korrekte Zuordnung statt eines Ratens. Der
# Abgleich laeuft ueber name_pipe_kanal_index und ist NICHT auf DYN PPV
# beschraenkt: jeder Sender, der per NAME:-Zeile in sender.txt
# eingetragen ist (Kernname exakt wie beim Anbieter), wird automatisch
# erfasst - fuer weitere Kategorien (z.B. "US: SOCCER PPV") reicht ein
# neuer NAME:-Eintrag in sender.txt, ohne dass hier Code geaendert
# werden muss.
#
# Sicherheit: Die URLs enthalten persoenliche Zugangsdaten (uid/key) des
# Nutzers und werden NIEMALS im Code/Repo hinterlegt, sondern kommen
# ausschliesslich ueber Umgebungsvariablen (als GitHub Actions Secrets
# gesetzt). Fehlt eine Variable (z.B. beim lokalen Testen), wird sie
# einfach uebersprungen.
#
# Der Anbieter (myepg.top) liefert zwei getrennte Dateien - "World" und
# "EU" - die unterschiedliche Kategorien abdecken (z.B. DYN PPV nur in
# der EU-Datei, "US: SOCCER PPV" nur in der World-Datei). Damit der
# Abgleich unabhaengig davon funktioniert, welche Kategorie in welcher
# Datei steckt, werden beide abgefragt und die Treffer zusammengefuehrt.
#
# Jede Datei ist riesig (>150 MB entpackt), enthaelt aber ALLE
# <channel>-Definitionen VOR dem allerersten <programme>-Tag - daher
# wird nur gestreamt entpackt, bis das erste <programme> auftaucht,
# und die Verbindung dann abgebrochen, statt die komplette Datei
# herunterzuladen.

DYN_EPG_PROVIDER_TIMEOUT_SEKUNDEN = 30
# Grosszuegige Obergrenze fuer den gestreamten Bereich, falls das erste
# <programme>-Tag aus irgendeinem Grund fehlt/sich stark verschiebt -
# verhindert, dass versehentlich die komplette 150+MB-Datei geladen wird.
DYN_EPG_PROVIDER_MAX_ZEICHEN = 20_000_000


def epg_anbieter_datei_abgleichen(url, quelle_name):
    """Laedt die <channel>-Definitionen einer EPG-Anbieter-Datei und
    uebertraegt fuer jeden per Kernname matchenden NAME:-Sender (siehe
    name_pipe_kanal_index) den aktuellen Live-Kanalnamen als
    Sendungstitel. Gibt (Anzahl Treffer, Gesamtanzahl NAME:-Sender)
    zurueck."""
    response = requests.get(url, timeout=DYN_EPG_PROVIDER_TIMEOUT_SEKUNDEN, stream=True)
    response.raise_for_status()

    dekomprimierer = zlib.decompressobj(16 + zlib.MAX_WBITS)
    gepuffert = ""
    for chunk in response.iter_content(chunk_size=65536):
        gepuffert += dekomprimierer.decompress(chunk).decode("utf-8", errors="ignore")
        if "<programme" in gepuffert or len(gepuffert) > DYN_EPG_PROVIDER_MAX_ZEICHEN:
            break
    response.close()

    kanal_bereich = gepuffert.split("<programme", 1)[0]

    aktualisiert = 0
    aktualisierte_sender = []
    for channel_match in re.finditer(r"<channel[^>]*>(.*?)</channel>", kanal_bereich, re.DOTALL):
        for name_match in re.finditer(
            r"<display-name>([^<]*)</display-name>", channel_match.group(1)
        ):
            voller_name = name_match.group(1).strip()
            kurzname, event_teil = kern_und_event_extrahieren(voller_name)
            normalisierter_kern = re.sub(r"\s+", " ", kurzname).strip().upper()

            real_daten = name_pipe_kanal_index.get(normalisierter_kern)
            if real_daten is None:
                continue

            # TEST: Bei DYN PPV wird der Leerlauf-Text ("- NO EVENT
            # STREAMING - | 8K EXCLUSIVE") NICHT herausgefiltert,
            # sondern ebenfalls direkt uebernommen - so laesst sich
            # sichtbar bestaetigen, dass der aktuelle Live-Kanalname
            # wirklich aus der Anbieter-Datei gelesen wird (auch ohne
            # laufendes Event), statt nur beim generischen Platzhalter
            # zu bleiben.
            ist_dyn_ppv = bool(re.match(r"^DYN\s*PPV\s*\d+$", kurzname, re.IGNORECASE))

            if event_teil and (
                ist_dyn_ppv
                or not any(marker in event_teil.lower() for marker in LEERLAUF_MARKER)
            ):
                real_daten["event_titel"] = formatiere_event_text(event_teil)
                aktualisiert += 1
                aktualisierte_sender.append(
                    f'{real_daten["sender"]} (roher Live-Kanalname: {voller_name!r})'
                )
            break

    if aktualisierte_sender:
        print(f"EPG-Anbieter ({quelle_name}) Treffer:")
        for eintrag in aktualisierte_sender:
            print(" -", eintrag)

    return aktualisiert


if name_pipe_kanal_index:
    for env_name, quelle_name in (
        ("DYN_EPG_PROVIDER_URL", "World"),
        ("DYN_EPG_PROVIDER_URL_EU", "EU"),
    ):
        url = os.environ.get(env_name)
        if not url:
            continue
        try:
            treffer = epg_anbieter_datei_abgleichen(url, quelle_name)
            print(
                f"EPG-Anbieter ({quelle_name}): {treffer} von "
                f"{len(name_pipe_kanal_index)} NAME:-Kanaelen mit "
                f"Live-Kanalnamen aktualisiert"
            )
        except Exception as e:
            print(f"EPG-Anbieter ({quelle_name}) Fehler:", e)

# ==========================================================
# CLUBBER LIVE EVENTS
# ==========================================================

# Echte Clubber-PPV-1-50-Sender (aus sender.txt, NAME:-Eintraege) per
# Kernname "Clubber N" indizieren - der Kernname steht bei Clubber
# VORNE im Kanalnamen (z.B. "(IE) (Clubber 01)"), daher genuegt eine
# einfache Regex-Suche statt der DYN-Pipe-Konvention.
clubber_real_kanal_index = {}
for daten in sender_daten:
    if daten.get("exakter_name"):
        treffer = re.search(r"CLUBBER\s*(\d+)", daten["sender"], re.IGNORECASE)
        if treffer:
            clubber_real_kanal_index[int(treffer.group(1))] = daten
clubber_real_kanal_anzahl = max(clubber_real_kanal_index.keys(), default=0)

if clubber_real_kanal_anzahl:
    try:
        response = None
        letzter_fehler = None

        for endpunkt in CLUBBER_API_ENDPUNKTE:
            try:
                versuch = requests.get(endpunkt, timeout=CLUBBER_API_TIMEOUT_SEKUNDEN)
                if versuch.status_code == 200:
                    response = versuch
                    break
                else:
                    letzter_fehler = f"{endpunkt} -> HTTP {versuch.status_code}"
            except requests.RequestException as e:
                letzter_fehler = f"{endpunkt} -> {e}"

        if response is None:
            raise RuntimeError(
                f"Alle Clubber-API-Endpunkte nicht erreichbar. Letzter Fehler: {letzter_fehler}"
            )

        antwort = response.json()
        spiele = antwort.get("result") or []

        if len(spiele) == 0:
            print("Keine Clubber-Spiele - Standardtext wird erstellt")
        else:
            clubber_kanal_nummer = 1

            for spiel in spiele:
                club = spiel.get("club") or ""
                gegner = spiel.get("teams", {}).get("competitorClubName") or ""
                county = spiel.get("county") or ""

                if club and gegner:
                    titel = f"{county}: {club} vs {gegner}" if county else f"{club} vs {gegner}"
                else:
                    titel = club or gegner or "Clubber Sport"

                datum = spiel.get("date")
                uhrzeit = spiel.get("time")

                if not datum or not uhrzeit:
                    continue

                start_lokal = datetime.strptime(
                    f"{datum} {uhrzeit}", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=CLUBBER_ZEITZONE)
                start_dt = start_lokal.astimezone(timezone.utc)
                ende_dt = start_dt + timedelta(hours=CLUBBER_EVENT_DAUER_STUNDEN)

                startzeit = start_dt.strftime("%Y%m%d%H%M%S +0000")
                endzeit = ende_dt.strftime("%Y%m%d%H%M%S +0000")

                real_daten = clubber_real_kanal_index.get(clubber_kanal_nummer)
                if real_daten is not None:
                    xml_teile.append(
                        f' <programme start="{startzeit}" stop="{endzeit}" channel="{escape(real_daten["kanal"])}">'
                        f' <title>{escape(titel)}</title> <desc>{escape(titel)}</desc> </programme> '
                    )
                    real_daten["event_titel"] = None
                    real_daten.setdefault("api_event_fenster", []).append(
                        (start_dt, ende_dt)
                    )

                clubber_kanal_nummer += 1
                if clubber_kanal_nummer > clubber_real_kanal_anzahl:
                    clubber_kanal_nummer = 1

    except Exception as e:
        print("Clubber Fehler:", e)

# ==========================================================
# STANDARD-EPG (variable Tagesraster-Bloecke, als Platzhalter).
# Statt starrer 2h-Slots orientieren sich die Blocklaengen an
# einem realistischen Tagesablauf (Nacht/Morgen/Vormittag/
# Mittag/Nachmittag/Abend/Spaetabend). Zeitraum: ANZAHL_TAGE
# (siehe zentrale Konfiguration oben).
# ==========================================================

starttag = datetime.now(timezone.utc).replace(
    hour=0, minute=0, second=0, microsecond=0
)

for tag_index in range(ANZAHL_TAGE):

    tag_start = starttag + timedelta(days=tag_index)
    stunden_cursor = 0

    for block_index, (dauer, tageszeit) in enumerate(TAGESRASTER):

        start = tag_start + timedelta(hours=stunden_cursor)
        ende = start + timedelta(hours=dauer)
        stunden_cursor += dauer

        for daten in sender_daten:
            # DYN PPV 1-50 (NAME:-Einträge): hat sich der Kanalname wegen
            # eines laufenden Events geändert (siehe Erkennung weiter
            # oben beim Einlesen), wird dieser Event-Name hier als
            # Sendungstitel/-beschreibung übernommen. Ohne Event bleibt
            # es beim bisherigen kategoriebasierten Text.
            event_titel = daten.get("event_titel")
            kategorie_key = daten.get("kategorie")
            hash_wert = sum(ord(c) for c in daten["sender"])

            # DYN/Flo-Racing-Zeit-Automatisierung: steht im Event-Namen
            # eine erkennbare Uhrzeit (z.B. "Sa 14:00 : Flo Racing 05"),
            # wird das Event NUR fuer den heutigen Tag (tag_index==0)
            # zeitlich praezise (Standard: 2 Stunden) statt ueber den
            # ganzen, oft mehrstuendigen Tagesraster-Block hinweg
            # angezeigt. Faellt die erkannte Uhrzeit nicht in den
            # aktuellen Block, wird in diesem Block stattdessen der
            # generische kategoriebasierte Text gezeigt (statt den
            # Event-Titel ueber den kompletten Tag zu "schmieren") -
            # AUSSER das Event steht in einem spaeteren Block noch
            # bevor: dann wird ein "Vorbericht"-Hinweis mit der
            # Uhrzeit gezeigt statt des generischen Kategorietexts.
            # Fuer Folgetage (tag_index>0, Uhrzeit/Datum des Events dann
            # nicht mehr sicher zuordenbar) bleibt es beim bisherigen
            # Verhalten: Event-Titel gilt fuer den ganzen Tag.
            verwende_event = bool(event_titel)
            event_start_dt = None
            event_ende_dt = None
            vorbericht_titel = None
            vorbericht_lang_code = None

            if verwende_event and tag_index == 0:
                geparste_zeit = parse_event_zeit(event_titel)
                if geparste_zeit:
                    stunde, minute = geparste_zeit
                    kandidat_start = tag_start.replace(
                        hour=stunde, minute=minute, second=0, microsecond=0
                    )
                    kandidat_ende = kandidat_start + timedelta(hours=DYN_EVENT_DAUER_STUNDEN)

                    if start <= kandidat_start < ende:
                        event_start_dt = kandidat_start
                        event_ende_dt = kandidat_ende
                    else:
                        # Erkannte Uhrzeit gehoert zu einem anderen
                        # Block des Tages - hier generischen Text zeigen.
                        verwende_event = False
                        if kandidat_start >= ende:
                            # Event steht noch bevor (spaeterer Block
                            # heute) - sprachabhaengiger Vorbericht statt
                            # generischem Kategorietext. Ist dies der
                            # Block UNMITTELBAR vor dem Event-Block, wird
                            # "in Kuerze" statt der festen Uhrzeit gezeigt.
                            naechster_index = block_index + 1
                            ist_naechster_block = False
                            if naechster_index < len(TAGESRASTER):
                                naechste_dauer = TAGESRASTER[naechster_index][0]
                                if ende <= kandidat_start < ende + timedelta(hours=naechste_dauer):
                                    ist_naechster_block = True

                            uhrzeit_str = f"{stunde:02d}:{minute:02d}"
                            vorbericht_sprache = sprache_fuer_land(daten["land"])
                            vorbericht_lang_code = {
                                "DE": "de", "EXYU": "hr", "SI": "sl", "MK": "mk", "EN": "en"
                            }[vorbericht_sprache]
                            vorbericht_titel = vorbericht_text(
                                vorbericht_sprache, event_titel, uhrzeit_str,
                                ist_naechster_block
                            )

            if event_start_dt is not None:
                # Praezises Event: eigener Programme-Eintrag im engeren
                # Event-Zeitfenster (mit "Live"-Tag). Das Fenster wird
                # danach in api_event_fenster eingetragen, damit sowohl
                # der Rest DIESES Blocks als auch spaetere Bloecke
                # desselben Tages (naechste block_index-Iterationen fuer
                # denselben Sender) den Ueberlapp automatisch heraus-
                # schneiden statt ihn zu duplizieren (behebt die vorher
                # bestehende Luecke vor bzw. Ueberlappung nach dem Event).
                event_segmente = segmente_ohne_ueberlappung(
                    event_start_dt, event_ende_dt, daten.get("api_event_fenster", [])
                )
                schreibe_programme_segmente(
                    xml_teile, event_segmente, daten["kanal"],
                    escape(event_titel), event_titel, "de",
                    kategorie_key, daten["land"], True,
                )
                daten.setdefault("api_event_fenster", []).append(
                    (event_start_dt, event_ende_dt)
                )

                # Block-Rest (vor/nach dem engeren Event-Zeitfenster,
                # aber noch innerhalb dieses Tagesraster-Blocks) bekommt
                # weiterhin den generischen Kategorietext statt einer
                # Luecke mit "Keine Information".
                block_titel_text = escape(
                    sendetitel(
                        kategorie_key, daten["land"], hash_wert, tageszeit,
                        tag_index=tag_index
                    )
                )
                block_beschr_text, block_lang_code = beschreibung_fuer_sender(
                    kategorie_key, daten["land"], daten["sender"], hash_wert,
                    tag_index=tag_index
                )
                block_segmente = segmente_ohne_ueberlappung(
                    start, ende, daten.get("api_event_fenster", [])
                )
                schreibe_programme_segmente(
                    xml_teile, block_segmente, daten["kanal"],
                    block_titel_text, block_beschr_text, block_lang_code,
                    kategorie_key, daten["land"], False,
                )
            else:
                if verwende_event:
                    titel_text = escape(event_titel)
                    beschr_text = event_titel
                    lang_code = "de"
                elif vorbericht_titel:
                    titel_text = escape(vorbericht_titel)
                    beschr_text = vorbericht_titel
                    lang_code = vorbericht_lang_code
                else:
                    titel_text = escape(
                        sendetitel(
                            kategorie_key, daten["land"], hash_wert, tageszeit,
                            tag_index=tag_index
                        )
                    )
                    beschr_text, lang_code = beschreibung_fuer_sender(
                        kategorie_key, daten["land"], daten["sender"], hash_wert,
                        tag_index=tag_index
                    )

                # Ueberschneidet sich dieser Block mit einem bereits per
                # DYN-API/Clubber-API bzw. praezisem Event (siehe oben)
                # geschriebenen Zeitfenster, wird NUR der ueberlappende
                # Teil herausgeschnitten - der Rest bekommt weiterhin den
                # obigen Text, statt den kompletten Block wegzulassen.
                segmente = segmente_ohne_ueberlappung(
                    start, ende, daten.get("api_event_fenster", [])
                )
                schreibe_programme_segmente(
                    xml_teile, segmente, daten["kanal"],
                    titel_text, beschr_text, lang_code,
                    kategorie_key, daten["land"], False,
                )

# ==========================================================
# DYN LEERZEITEN
# ==========================================================

jetzt = datetime.now(timezone.utc).replace(
    hour=0, minute=0, second=0, microsecond=0
)

for i in range(1, DYN_PPV_ANZAHL + 1):
    kanal = f"DE| DYN PPV {i} HD"
    api_fenster = dyn_synth_api_fenster.get(i, [])

    for stunde in range(24 * DYN_LEERZEIT_TAGE):
        block_start = jetzt + timedelta(hours=stunde)
        block_ende = block_start + timedelta(hours=1)

        # Nur den mit einem API-Event ueberlappenden Teil dieser Stunde
        # ausschneiden (siehe segmente_ohne_ueberlappung weiter oben) -
        # der Rest bekommt weiterhin den Leerzeit-Platzhalter, statt
        # eine ganze Stunde vor/nach dem Event wegzulassen.
        for start, ende in segmente_ohne_ueberlappung(block_start, block_ende, api_fenster):
            start_str = start.strftime("%Y%m%d%H%M%S +0000")
            ende_str = ende.strftime("%Y%m%d%H%M%S +0000")

            xml_teile.append(
                f' <programme start="{start_str}" stop="{ende_str}" channel="{escape(kanal)}">'
                f' <title>Im Moment keine Live Events, bleib dran</title>'
                f' <desc>Im Moment keine Live Events, bleib dran.</desc> </programme> '
            )

# ==========================================================
# XML ABSCHLIESSEN
# ==========================================================

xml_teile.append("\n</tv>")

xml_inhalt = "".join(xml_teile)

# ==========================================================
# XML-Validitätsprüfung
#
# Bevor die Datei geschrieben (und später committet) wird, wird
# geprüft, ob das erzeugte XML überhaupt wohlgeformt ist. Bricht das
# Skript hier ab, bleibt die zuletzt funktionierende Epg_365_Tage.xml
# unangetastet erhalten, statt durch eine kaputte Datei ersetzt zu
# werden.
# ==========================================================

try:
    ET.fromstring(xml_inhalt)
except ET.ParseError as e:
    raise SystemExit(f"Fehler: Erzeugtes XML ist ungültig, Abbruch ohne Schreiben: {e}")

with open("Epg_365_Tage.xml", "w", encoding="utf-8") as f:
    f.write(xml_inhalt)

print(f"EPG erfolgreich erstellt ({len(sender_daten)} Sender).")
