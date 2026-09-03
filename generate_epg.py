from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape
import gzip
import os
import re
import requests
import xml.etree.ElementTree as ET

from epg_lib import (
    KATEGORIEN, KATEGORIE_PRIORITAET,
    DE_STANDARD, EXYU_STANDARD, EN_STANDARD,
    EXYU_LAENDER, UK_LAENDER, US_LAENDER, EN_LAENDER,
    ALTERSFREIGABE, DEFAULT_ALTERSFREIGABE,
    TAGESRASTER,
    sender_anzeigename, standard_beschreibung, kategorie_label,
    sender_hash,
    kanalname_normal_geschrieben,
    normalisiere_sendername, baue_logo_index, finde_logo,
)
from quellen.telemach_epg import telemach_kanal_finden, telemach_hole_programme
from quellen.mtel_epg import mtel_kanal_finden, mtel_hole_programme
from quellen.mymedia_epg import mymedia_hole_programme
from quellen.klix_epg import klix_kanal_finden, klix_hole_programme
from quellen.mts_epg import mts_kanal_finden, mts_hole_programme
from quellen.mojmaxtv_epg import mojmaxtv_kanal_finden, mojmaxtv_hole_programme
from quellen.sportklub_epg import sportklub_kanal_finden, sportklub_hole_programme
from quellen.magenta_myteam_epg import magenta_myteam_kanal_finden, magenta_myteam_hole_programme
from quellen.siol_epg import siol_kanal_finden, siol_hole_programme
from quellen.sky_epg import sky_kanal_finden, sky_hole_programme
from quellen.magenta_epg import magenta_kanal_finden, magenta_hole_programme
from quellen.arena_epg import arena_kanal_finden, arena_hole_programme
from quellen.dazn_epg import dazn_kanal_finden, dazn_hole_programme
from quellen.freeview_epg import freeview_kanal_finden, freeview_hole_programme
from quellen.tvguide_epg import tvguide_kanal_finden, tvguide_hole_programme
from quellen.tvpassport_epg import tvpassport_kanal_finden, tvpassport_hole_programme
from quellen.tvmovie_epg import tvmovie_kanal_finden, tvmovie_hole_programme
from quellen.plutotv_epg import plutotv_kanal_finden, plutotv_hole_programme
from quellen.hoerzu_epg import hoerzu_kanal_finden, hoerzu_hole_programme
from quellen.samsungtv_epg import samsungtv_kanal_finden, samsungtv_hole_programme
from quellen.deswird_epg import deswird_kanal_finden, deswird_hole_programme
from quellen.tubi_epg import tubi_kanal_finden, tubi_hole_programme, tubi_kanal_icon


def kanal_id_varianten(kanal):
    """Gibt fuer eine Kanal-ID im "Land|Sender"-Muster (z.B. "UK|
    AMAZON UK EVENT 0" oder "UK|AMAZON UK EVENT 0") BEIDE moeglichen
    Schreibweisen zurueck - mit UND ohne Leerzeichen direkt nach dem
    Pipe-Zeichen. Grund: TiviMate matcht EPG-Kanaele beim automatischen
    Zuordnen offenbar (auch) nach exaktem Namensvergleich mit der
    eigenen Playlist - und in derselben Playlist schreiben
    unterschiedliche Sender-Gruppen das uneinheitlich (manche
    "DE| Sender", andere "DE|Sender", ohne erkennbares Muster). Damit
    die automatische Zuordnung unabhaengig von der jeweils genutzten
    Schreibweise funktioniert, wird derselbe Kanal/dieselbe Sendung
    unter BEIDEN Varianten im EPG ausgegeben (Bug September 2026
    behoben: einzelne Sender-Gruppen wie "UK|AMAZON UK EVENT" wurden
    nie automatisch zugeordnet, weil unsere generierte ID immer das
    Leerzeichen hatte, die Playlist des Nutzers dort aber keins).
    Kanal-IDs ohne dieses "XX|..."-Muster (z.B. NAME:-Sender wie
    "24/7 ALL RISE" oder "DE: DYN PPV 1" mit Doppelpunkt statt Pipe)
    bleiben unveraendert - dort gibt es keine sinnvolle Alternativ-
    Schreibweise."""
    match = re.match(r"^([A-Za-z]{2,4})\|(\s*)(.+)$", kanal)
    if not match:
        return [kanal]
    land, _leerzeichen, rest = match.groups()
    ohne = f"{land}|{rest}"
    mit = f"{land}| {rest}"
    if ohne == mit:
        return [kanal]
    return [ohne, mit]


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
    # Bei Live-Events/Vorberichten (DYN PPV, Clubber, ...) sind Titel und
    # Beschreibung derselbe generierte Satz - ein zusaetzliches <sub-title>
    # mit demselben Text liesse ihn im EPG-Raster doppelt erscheinen
    # (manche Player wie TiviMate zeigen Titel UND Untertitel als eigene
    # Zeile). Nur setzen, wenn sich Untertitel/Beschreibung tatsaechlich
    # vom Titel unterscheiden (z.B. beim generischen Tagesraster-Block).
    sub_title_tag = (
        f' <sub-title lang="{lang_code}">{beschr_escaped}</sub-title>'
        if beschr_escaped != titel_text else ""
    )

    kanal_ids = kanal_id_varianten(kanal)
    for seg_start, seg_ende in segmente:
        seg_start_str = seg_start.strftime("%Y%m%d%H%M%S +0000")
        seg_ende_str = seg_ende.strftime("%Y%m%d%H%M%S +0000")
        for kanal_id in kanal_ids:
            xml_teile.append(
                f' <programme start="{seg_start_str}" stop="{seg_ende_str}" channel="{escape(kanal_id)}">'
                f' <title lang="{lang_code}">{titel_text}</title>'
                f'{sub_title_tag}'
                f'{desc_tag}{category_tags}{rating_tag} </programme> '
            )


def ueberlappt_intervall(intervalle, start, ende):
    """Prueft, ob der Zeitraum [start, ende) mit irgendeinem (start, stop)-
    Intervall aus `intervalle` echt zeitlich ueberlappt - NICHT nur, ob sie
    auf denselben Kalendertag fallen. Wird fuer die "bereits echte Daten
    vorhanden"-Sperre im generischen Tagesraster verwendet: manche echten
    Quellen (z.B. tvmovie.de, laut Doku nur ca. 05:00-20:00 Uhr statt des
    vollen Tages) decken nur einen TEIL eines Tages ab. Eine reine
    Tages-Pruefung wuerde dann faelschlich den KOMPLETTEN Tag sperren und
    die generische Fuellung fuer die unbedeckte Restzeit (z.B. den Abend)
    verhindern - es bliebe dort komplett leer ("Keine Information")."""
    for real_start, real_stop in intervalle:
        if start < real_stop and ende > real_start:
            return True
    return False


# Ordnet jedem "hat eine echte Quelle aktiv"-Flag in daten die zugehoerigen
# *_intervalle-Felder zu (mehrere bei Faellen mit Fallback-Kette, z.B.
# Telemach -> mtel.ba -> mymedia.ba -> klix.ba oder PlutoTV -> tvmovie.de).
_ECHTE_QUELLEN_INTERVALLE = {
    "telemach": ["telemach_intervalle", "mtel_intervalle", "mymedia_intervalle", "klix_intervalle"],
    "sky": ["sky_intervalle"],
    "magenta": ["magenta_intervalle"],
    "arena": ["arena_intervalle"],
    "dazn": ["dazn_intervalle"],
    "freeview": ["freeview_intervalle"],
    "tvguide": ["tvguide_intervalle"],
    "tvpassport": ["tvpassport_intervalle"],
    "mts": ["mts_intervalle"],
    "mojmaxtv": ["mojmaxtv_intervalle", "sportklub_intervalle"],
    "siol": ["siol_intervalle"],
    "plutotv": ["deswird_intervalle", "plutotv_intervalle", "tvmovie_intervalle", "hoerzu_intervalle", "samsungtv_intervalle", "magenta_myteam_intervalle"],
    "tubi": ["tubi_intervalle"],
}


def hat_aktive_echte_quelle(daten):
    """True, wenn fuer diesen Sender mindestens eine echte EPG-Quelle
    (Telemach, Sky, Magenta, Pluto TV/tvmovie.de, Tubi, ...) aktiv ist -
    unabhaengig davon, ob sie fuer den aktuell betrachteten Zeitblock
    tatsaechlich Daten geliefert hat."""
    return any(daten.get(flag) for flag in _ECHTE_QUELLEN_INTERVALLE)


def alle_echten_intervalle(daten):
    """Sammelt alle (start, stop)-Intervalle aller fuer diesen Sender
    aktiven echten Quellen in einer Liste, fuer den Ueberlappungs-Check
    gegen einen einzelnen Zeitblock."""
    ergebnis = []
    for flag, felder in _ECHTE_QUELLEN_INTERVALLE.items():
        if daten.get(flag):
            for feld in felder:
                ergebnis.extend(daten.get(feld, []))
    return ergebnis


def kern_und_event_extrahieren(voller_name):
    """Trennt einen rohen Kanalnamen in (Kurzname/Kern, Event-Text) nach
    der Pipe-Konvention: der Abschnitt NACH dem letzten Pipe-Zeichen gilt
    als stabiler Kern (z.B. "DE: DYN PPV 1" -> "DYN PPV 1"), alles davor
    als potenzieller Event-Text. Ohne Pipe wird auf das bekannte
    DYN-PPV/FLO-RACING-Doppelpunkt-Muster zurueckgefallen. Wird sowohl
    beim Einlesen von sender.txt als auch beim Auslesen der Live-
    Kanalnamen aus der EPG-Anbieter-Datei verwendet."""
    # Super League Plus-Sonderfall: die Event-Nummer steckt mal mit,
    # mal ohne Pipe direkt hinter "Super League Plus" (Leerlauf:
    # "Super League Plus | Event 5", live: "Super League Plus Event 1
    # | Leeds Rhinos v Bradford Bulls | ..."). Ein fester Regex auf die
    # Nummer macht den Kern in beiden Schreibweisen identisch
    # ("Super League Plus Event N"), damit Leerlauf-Eintrag und
    # Live-Playlist-Name zuverlaessig zusammenfinden - analog zum
    # DYN-PPV/FLO-RACING-Muster unten, nur mit Pipe-Toleranz.
    super_league_match = re.search(
        r"SUPER\s*LEAGUE\s*PLUS.*?EVENT\s*0*(\d+)", voller_name, re.IGNORECASE
    )
    if super_league_match:
        kurzname = f"Super League Plus Event {super_league_match.group(1)}"
        event_teil = voller_name[super_league_match.end():].strip(" |").strip()
        return kurzname, event_teil

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
        # Laender-Praefix ("DE: ", "US: ", ...) NUR bei DYN PPV/FLO
        # RACING entfernen - das ist die historische Sonderkonvention
        # dieser beiden Anbieter, deren sender.txt-Kernname schon immer
        # OHNE Land gefuehrt wurde (siehe Sonderfall unten im
        # No-Pipe-Zweig). Bei allen anderen "Land: Name N"-Sendern
        # (SOCCER PPV, DAZN PPV, ESPN+ PPV, ...) bleibt das Land Teil
        # des Kerns - sonst wuerden z.B. "DE: SOCCER PPV 43" und
        # "US: SOCCER PPV 43" (zwei echte, aber verschiedene Kanaele
        # unterschiedlicher Laender) auf denselben Index-Schluessel
        # kollidieren und sich beim Live-Abgleich gegenseitig
        # ueberschreiben (Bug September 2026 behoben).
        kern_ohne_land = re.sub(r"^[A-Za-z]{2}\s*:\s*", "", kern_roh).strip()
        if re.fullmatch(r"(DYN\s*PPV|FLO\s*RACING)\s*\d+", kern_ohne_land, re.IGNORECASE):
            kurzname = kern_ohne_land
        else:
            kurzname = kern_roh
    else:
        kurzname_match = re.search(r"(DYN\s*PPV|FLO\s*RACING)\s*\d+", voller_name, re.IGNORECASE)
        if kurzname_match:
            # Immer den sauber erkannten Kern verwenden (Text NACH dem
            # Muster, z.B. ein angehaengtes " :" wie bei "Flo Racing 01 :",
            # wird bewusst verworfen statt Teil des Kerns zu bleiben) -
            # sonst wuerde z.B. "Flo Racing 01 :" (Leerlauf-Schreibweise
            # in sender.txt) NIE mit dem echten Live-Kern "Flo Racing  01"
            # (aus einem Event-Namen wie "PBR RidePass :Flo Racing  01")
            # uebereinstimmen, weil einmal der Rohtext samt Doppelpunkt
            # und einmal nur der reine Kern normalisiert wuerde.
            kurzname = kurzname_match.group(0)
            event_teil = voller_name[:kurzname_match.start()].strip(" :").strip()
            # Wie im Pipe-Zweig oben: bleibt nach dem Abschneiden nur ein
            # reines 2-4-Buchstaben-Laenderkuerzel uebrig (z.B. "DE" aus
            # "DE: DYN PPV 6"), ist das kein echter Event-Text, sondern
            # nur das Laenderkuerzel vor dem Kern.
            if re.fullmatch(r"[A-Za-z]{2,4}", event_teil):
                event_teil = ""
        else:
            # Generisches Kern-AM-ENDE-Muster ohne Pipe (z.B. Milb, Flo
            # College, Tennis, MLS, NBA Summer League): der stabile Kern
            # steht als ":<Name(n)> <Nummer>" ganz am Zeilenende, alles
            # davor ist der wechselnde Event-Text (z.B. "TAMIU vs West
            # Alabama @ Aug 31 5:00 PM :Flo College  01" -> Kern
            # "Flo College  01"). Ans Zeilenende ($) verankert, damit eine
            # Uhrzeitangabe im Event-Text selbst (z.B. "5:00 PM") nicht
            # faelschlich als Trenner genommen wird - nur der LETZTE
            # Doppelpunkt vor einer schliessenden Zahl zaehlt. Ein
            # erfolgloser Versuch hier ist risikofrei: der anschliessende
            # Index-Lookup in name_pipe_kanal_index() schlaegt einfach
            # fehl, wenn kein passender Sender registriert ist - kein
            # Fehltreffer-Risiko wie bei einem unscharfen Abgleich.
            ende_match = re.search(
                r":\s*([A-Za-z][A-Za-z0-9+.]*(?:\s+[A-Za-z0-9+.]+)*\s+0*\d+)\s*$",
                voller_name,
            )
            # WICHTIG (Bug September 2026 behoben): ein blosses 2-4-Buchstaben-
            # Laenderkuerzel VOR dem gefundenen Doppelpunkt (z.B. "DE: RTL+ PPV
            # 28", "US: ESPN+ PPV 7") ist die weit verbreitete "Land: Name PPV
            # N"-Konvention OHNE Pipe (RTL+/SOCCER/ESPN+/DAZN/NETFLIX/MLS/FIFA+/
            # B/R MAX SPORTS PPV usw., tausende Zeilen) - die faellt NICHT unter
            # das neue Kern-am-Ende-Muster (das ist fuer Faelle mit echtem
            # Event-Text VOR dem Kern gedacht, z.B. Milb/Flo College). Ohne
            # diese Ausnahme wurde "DE"/"US" faelschlich als "Event-Text"
            # interpretiert (sichtbares Symptom: der Sendungstitel zeigte nur
            # noch "DE"/"US" statt des Kanalnamens) UND der eigentliche Kern
            # verlor sein Laenderkuerzel, wodurch alle nachfolgenden Live-
            # Playlist-Treffer fuer diese Sender-Gruppen ausblieben.
            ende_match_land_praefix = (
                ende_match
                and re.fullmatch(r"[A-Za-z]{2,4}", voller_name[:ende_match.start()].strip(" :").strip())
            )
            if ende_match and not ende_match_land_praefix:
                kurzname = ende_match.group(1).strip()
                event_teil = voller_name[:ende_match.start()].strip(" :").strip()
            else:
                # Laender-Praefix bleibt hier bewusst Teil des Kerns
                # (siehe Pipe-Zweig oben: nur DYN PPV/FLO RACING sind die
                # Sonderfaelle ohne Land) - der Pipe-Zweig verwendet
                # dieselbe Regel, damit z.B. "US: ESPN+ PPV 1" (sender.txt-
                # Kernname) und der beim Live-Playlist-Abgleich aus
                # "... | US: ESPN+ PPV 1" extrahierte Kern exakt
                # uebereinstimmen, OHNE mit "DE: ESPN+ PPV 1" zu kollidieren.
                kurzname = voller_name
                event_teil = ""
    return kurzname, event_teil


def kern_vorne_und_event_extrahieren(voller_name):
    """Gegenstueck zu kern_und_event_extrahieren() fuer Anbieter, die den
    stabilen Kern VORNE im Kanalnamen fuehren statt hinten (z.B. Clubber:
    "(IE) (Clubber 01) | Kerry GAA: Abbeydorney vs St Brendans (...)" ->
    Kern "(IE) (Clubber 01)", Event-Text der Rest). Wird beim EPG-
    Anbieter-Abgleich zusaetzlich zur Hinten-Konvention probiert, damit
    beide Namensschemata ueber denselben generischen Mechanismus laufen,
    ohne dass die Zuordnung anbieterspezifisch im Code verdrahtet ist.
    Ohne Pipe im Namen gibt es keinen Kandidaten (None, ""), ausser fuer
    bekannte Kern-vorne-Anbieter mit DOPPELPUNKT statt Pipe (z.B.
    DirtVision: "DIRTVISION 01 : Knoxville Raceway 7:15 pm" -> Kern
    "DIRTVISION 01", Event "Knoxville Raceway 7:15 pm"). Dafuer wird
    gezielt nach bekannten Kern-Keywords gesucht, statt am ERSTEN
    Doppelpunkt zu trennen - sonst wuerde eine Uhrzeitangabe im Event-
    Text selbst (z.B. "7:15 pm") faelschlich als Trenner genommen."""
    if "|" in voller_name:
        segmente = voller_name.split("|")
        kurzname = segmente[0].strip()
        event_teil = "|".join(segmente[1:]).strip()
        return kurzname, event_teil

    match = re.match(r"^\s*(DIRTVISION\s*\d+|FA\s*PLAYER\s*\d+)\s*:\s*(.*)$", voller_name, re.IGNORECASE)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    # Generisches Kern-VORNE-Muster ohne Pipe (z.B. NCAAF: "NCAAF 01:
    # North Texas vs Charlotte @ Oct 24 7:00 PM" -> Kern "NCAAF 01").
    # An ^ verankert, damit nur der ALLERERSTE Doppelpunkt der Zeile als
    # Trenner zaehlt - eine Uhrzeitangabe im Event-Text (z.B. "7:00 PM")
    # kommt immer erst NACH dem Kern und wird dadurch nie faelschlich
    # als Trenner genommen. Ein erfolgloser Versuch ist risikofrei: der
    # anschliessende Index-Lookup schlaegt einfach fehl, wenn kein
    # passender Sender registriert ist.
    generisch_match = re.match(
        r"^\s*([A-Za-z][A-Za-z0-9+.]*(?:\s+[A-Za-z0-9+.]+)*\s+0*\d+)\s*:\s*(.*)$",
        voller_name,
    )
    if generisch_match:
        return generisch_match.group(1).strip(), generisch_match.group(2).strip()

    return None, ""

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
EVENT_MARKER_LIVE = ["live"]
EVENT_MARKER_ENDE = ["end", "ended", "endet"]
# Bewusst anbieterneutral formuliert (kein Marken-Signatur wie "Ihr DYN
# Sport Team") - formatiere_event_text() wird generisch fuer ALLE
# NAME:-Sendergruppen verwendet (ESPN+/SOCCER/DAZN PPV usw.), nicht nur
# fuer DYN PPV. Eine DYN-spezifische Signatur zeigte sich faelschlich
# auch bei Sendern anderer Anbieter (Bug September 2026 behoben).
EVENT_ENDE_TEXT = "Spiel ist beendet, danke, dass Sie zugeschaut haben."


def normalisiere_grossschreibung(text):
    """Wandelt grossgeschriebene WOERTER (nicht den ganzen Text auf
    einmal - viele Anbieter-Kanalnamen mischen bereits normal
    geschriebene Teamnamen mit durchgaengig grossgeschriebenen
    Zusaetzen wie "8K EXCLUSIVE") in normale Gross-/Kleinschreibung um,
    statt sie "schreiend" im EPG-Raster anzuzeigen. Kurze Kuerzel
    (Laendercodes, Formatangaben wie "HD") und Woerter mit Ziffern
    (z.B. "8K", "4K") bleiben unveraendert. Bereits gemischt oder klein
    geschriebene Woerter (z.B. echte Eigennamen) werden nicht
    angefasst."""
    if not text:
        return text

    def wandel_wort(wort):
        kern = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ]", "", wort)
        if (
            not kern
            or kern != kern.upper()
            or any(zeichen.isdigit() for zeichen in wort)
            or len(kern) <= 3
        ):
            return wort
        return wort.capitalize()

    return " ".join(wandel_wort(w) for w in text.split(" "))


def formatiere_event_text(event_teil):
    """Erkennt einen bekannten Status-Marker (NEXT/END) im ersten Pipe-
    Segment eines rohen Event-Texts und baut daraus verstaendlichen
    deutschen EPG-Text: "NEXT | X" -> "Es folgt: X", "End | X" -> festen
    Abmoderationstext. Ohne erkannten Marker (z.B. bei "Live | ...")
    bleibt der Text unveraendert. Komplett grossgeschriebener Text wird
    dabei normalisiert (siehe normalisiere_grossschreibung())."""
    event_teil = normalisiere_grossschreibung(event_teil)
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


def dyn_next_team_namen(event_teil, status_suffix="ᴸⁱᵛᵉ"):
    """Extrahiert bei einem erkannten NEXT-/LIVE-Marker die Team-/Gegner-
    Namen aus dem rohen Event-Text (z.B. "NEXT | Deutschland - Guinea |
    Fri 21 Aug 18:10 CEST (DE) | 8K Exclusive" -> "Deutschland vs.
    Guinea 18:10 Uhr ᴺᵉˣᵗ"), ohne Status-Marker, Wochentag/Datum oder
    Wettbewerbs-/Rundenangabe. status_suffix haengt den erkannten Status
    ans Ende an (ᴺᵉˣᵗ bei "NEXT", ᴸⁱᵛᵉ bei "LIVE" - vom Aufrufer
    vorgegeben). Gibt None zurueck, wenn kein zweites Pipe-Segment
    vorhanden ist (Fallback bleibt dem Aufrufer ueberlassen)."""
    segmente = [s.strip() for s in event_teil.split("|") if s.strip()]
    if len(segmente) < 2:
        return None
    teams = normalisiere_grossschreibung(segmente[1])
    teams = re.sub(r"\s+-\s+", " vs. ", teams).strip()
    if not teams:
        return None

    uhrzeit_treffer = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", event_teil)
    if uhrzeit_treffer:
        return f"{teams} {uhrzeit_treffer.group(0)} Uhr {status_suffix}"
    return f"{teams} {status_suffix}"

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

        # Kein Kern-hinten-Muster erkannt (kurzname unveraendert) ->
        # zusaetzlich Kern-VORNE probieren (Clubber-Pipe-Konvention oder
        # DirtVision-Doppelpunkt-Konvention, siehe
        # kern_vorne_und_event_extrahieren()). Nur uebernehmen, wenn
        # dabei wirklich ein Kern erkannt wurde (kein Ratschlag), sonst
        # bleibt es beim bisherigen kurzname/event_teil.
        if kurzname == voller_name:
            kern_vorne, event_vorne = kern_vorne_und_event_extrahieren(voller_name)
            if kern_vorne:
                kurzname, event_teil = kern_vorne, event_vorne

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
            hash_wert_sport = sender_hash(kurzname)
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

        # DYN-PPV-Kanaele mit erkanntem "NEXT"- oder "LIVE"-Marker: statt
        # des rohen Anbietertexts (z.B. "Live| Team A - Team B | Fri 21
        # Aug 18:10 CEST (DE) | 8K Exclusive") wird NUR "Team A vs. Team
        # B HH:MM Uhr ᴸⁱᵛᵉ" angezeigt (siehe dyn_next_team_namen()) -
        # ohne generischen "Dyn Sport (N)"-Praefix und ohne Datum/
        # Zeitzone/Zusatztext. Ohne extrahierbare Teamnamen faellt es auf
        # den generischen "Dyn Sport (N) ᴺᵉˣᵗ"-Text zurueck.
        if event_titel is not None:
            dyn_ppv_next_match = re.match(r"^DYN\s*PPV\s*0*(\d+)$", kurzname, re.IGNORECASE)
            if dyn_ppv_next_match:
                roh_segmente = [s.strip() for s in event_teil.split("|")]
                roh_marker = roh_segmente[0].lower() if roh_segmente else ""
                if roh_marker in EVENT_MARKER_NEXT:
                    team_namen = dyn_next_team_namen(event_teil, status_suffix="ᴺᵉˣᵗ")
                    event_titel = team_namen or f"Dyn Sport ({dyn_ppv_next_match.group(1)}) ᴺᵉˣᵗ"
                elif roh_marker in EVENT_MARKER_LIVE:
                    team_namen = dyn_next_team_namen(event_teil, status_suffix="ᴸⁱᵛᵉ")
                    event_titel = team_namen or f"Dyn Sport ({dyn_ppv_next_match.group(1)}) ᴸⁱᵛᵉ"
                elif roh_marker in EVENT_MARKER_ENDE:
                    # Kein fixer Abmoderationstext bei DYN PPV - stattdessen
                    # bleiben die Teamnamen stehen, nur mit "ᴮᵉᵉⁿᵈᵉᵗ" statt
                    # ᴺᵉˣᵗ/ᴸⁱᵛᵉ als Suffix. Ohne extrahierbare Teamnamen faellt
                    # es auf "Dyn Sport (N) ᴺᵒ ᴸⁱᵛᵉ" zurueck (siehe unten).
                    team_namen = dyn_next_team_namen(event_teil, status_suffix="ᴮᵉᵉⁿᵈᵉᵗ")
                    event_titel = team_namen

        # DYN-PPV-Kanaele ohne erkanntes Event: statt des rohen
        # Anbieter-Platzhaltertexts ("- NO EVENT STREAMING - | 8K
        # EXCLUSIVE") oder der generischen kategoriebasierten
        # Beschreibung wird "Dyn Sport (N) ᴺᵒ ᴸⁱᵛᵉ" angezeigt - gleiche
        # Konvention wie bei DirtVision/Flo Racing unten.
        if event_titel is None:
            dyn_ppv_match = re.match(r"^DYN\s*PPV\s*0*(\d+)$", kurzname, re.IGNORECASE)
            if dyn_ppv_match:
                event_titel = f"Dyn Sport ({dyn_ppv_match.group(1)}) ᴺᵒ ᴸⁱᵛᵉ"

        # DirtVision-Kanaele ohne erkanntes Event: statt der generischen
        # kategoriebasierten Beschreibung (s.o.) wird "Kanalname (Nr) ᴸⁱᵛᵉ"
        # angezeigt (z.B. "DirtVision (1) ᴺᵒ ᴸⁱᵛᵉ") - gleiche Konvention wie
        # bei den manuell eingetragenen Sendern in sender.txt.
        if event_titel is None:
            dirtvision_match = re.match(r"^DIRTVISION\s*0*(\d+)$", kurzname, re.IGNORECASE)
            if dirtvision_match:
                event_titel = f"DirtVision ({dirtvision_match.group(1)}) ᴺᵒ ᴸⁱᵛᵉ"

        # Flo Racing-Kanaele ohne erkanntes Event: gleiche Konvention wie
        # DirtVision oben (z.B. "Flo Racing (1) ᴺᵒ ᴸⁱᵛᵉ").
        if event_titel is None:
            flo_racing_match = re.match(r"^FLO\s*RACING\s*0*(\d+)$", kurzname, re.IGNORECASE)
            if flo_racing_match:
                event_titel = f"Flo Racing ({flo_racing_match.group(1)}) ᴺᵒ ᴸⁱᵛᵉ"

        # FA Player-Kanaele ohne erkanntes Event: gleiche Konvention wie
        # DirtVision/Flo Racing oben (z.B. "FA Player (1) ᴺᵒ ᴸⁱᵛᵉ").
        if event_titel is None:
            fa_player_match = re.match(r"^FA\s*PLAYER\s*0*(\d+)$", kurzname, re.IGNORECASE)
            if fa_player_match:
                event_titel = f"FA Player ({fa_player_match.group(1)}) ᴺᵒ ᴸⁱᵛᵉ"

        # Super League Plus-Kanaele ohne erkanntes Event: gleiche
        # Konvention wie oben (z.B. "Super League Plus (1) ᴺᵒ ᴸⁱᵛᵉ").
        if event_titel is None:
            super_league_idle_match = re.match(
                r"^Super League Plus Event (\d+)$", kurzname
            )
            if super_league_idle_match:
                event_titel = f"Super League Plus ({super_league_idle_match.group(1)}) ᴺᵒ ᴸⁱᵛᵉ"

        # Sport-Deutschland-PPV-Kanaele ohne erkanntes Event: gleiche
        # Konvention wie DYN PPV/FA Player/Super League Plus oben (z.B.
        # "Sport Deutschland Ppv 1 ᴺᵒ ᴸⁱᵛᵉ") statt des generischen
        # "... ᴸⁱᵛᵉ"-Fallbacks weiter unten - auf Nutzerwunsch.
        if event_titel is None:
            sport_deutschland_match = re.search(
                r"SPORT\s*DEUTSCHLAND\s*PPV\s*0*(\d+)", kurzname, re.IGNORECASE
            )
            if sport_deutschland_match:
                event_titel = f"Sport Deutschland Ppv {sport_deutschland_match.group(1)} ᴺᵒ ᴸⁱᵛᵉ"

        # Alle uebrigen NAME:-Sender ohne bekanntes Anbieter-Muster
        # (z.B. "Premier League+ 1", kein Pipe-/Event-Mechanismus
        # vorhanden) UND ohne erkanntes Event: statt der generischen,
        # kategoriebasierten Beschreibung (s.o.) wird "<Kurzname> ᴸⁱᵛᵉ"
        # angezeigt - gleiche Konvention wie bei normalen sender.txt-
        # Zeilen ohne echte Quelle (siehe CLAUDE.md), nur eben fuer
        # Sender, deren exakter Playlist-Name per NAME:-Format
        # uebernommen wird.
        if event_titel is None:
            event_titel = f"{kanalname_normal_geschrieben(kurzname)} ᴸⁱᵛᵉ"

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

    # TELEMACH:-Präfix: opt-in für EINZELNE Sender, die echte
    # Programmdaten von der Telemach BA/ME-EPG-API bekommen sollen
    # (siehe telemach_epg.py), statt der generischen kategoriebasierten
    # Platzhaltertexte - z.B. weil der Sender in der eigenen TiviMate-
    # Playlist gar kein EPG mitbringt. KEIN automatisches Matching
    # gegen alle bosnischen/montenegrinischen Sender - nur Sender mit
    # dieser Zeile bekommen die echten Daten.
    #
    # SYNTAX (3 Felder, analog zum bestehenden Land|Sender|...-Schema,
    # nur mit Präfix und fest auf Land+Name+Logo begrenzt):
    #
    #   TELEMACH:<Land BA oder ME, optional, Default BA>|<Kanalname wie bei Telemach>|<Logo-URL>
    #
    # Beispiel:
    #   TELEMACH:BA|BHT 1|https://example.com/logo.png
    #   TELEMACH:|Sport Klub 1|                      (Land leer -> BA, ohne Logo)
    #
    # Der Kanalname (2. Feld) wird 1:1 als <channel> id/display-name
    # verwendet (wie bei NAME:) UND als Suchbegriff gegen die Telemach-
    # Kanalliste (telemach_kanal_finden(), erst exakt normalisiert,
    # dann difflib-Fuzzy-Match). Fuer die ersten bis zu 3 Tage werden -
    # sofern Login/Kanalsuche/Programmabruf gelingen - echte Sendungen
    # eingetragen; alle weiteren Tage (und bei jedem Fehlschlag der
    # Telemach-Anfrage) fallen exakt auf die normale, generische
    # Generierung zurück wie bei jedem anderen Sender.
    if zeile.upper().startswith("TELEMACH:"):
        rest = zeile[len("TELEMACH:"):]
        teile_telemach = [x.strip() for x in rest.split("|")]

        while len(teile_telemach) < 3:
            teile_telemach.append("")

        telemach_land = teile_telemach[0].upper() or "BA"
        if telemach_land not in ("BA", "ME"):
            telemach_land = "BA"

        telemach_kanalname = teile_telemach[1]
        telemach_logo = teile_telemach[2]

        if not telemach_kanalname:
            continue

        telemach_auto_beschreibung = f"{telemach_kanalname.title()} ᴸⁱᵛᵉ"
        telemach_kategorie_key = None

        sender_daten.append({
            "kanal": f"{telemach_land}| {telemach_kanalname}",
            "land": telemach_land,
            "sender": telemach_kanalname,
            "beschreibung": telemach_auto_beschreibung,
            "logo": telemach_logo,
            "exakter_name": True,
            "event_titel": None,
            "kategorie": telemach_kategorie_key,
            "telemach": {"country": telemach_land.lower()},
        })
        continue

    # SKY:-Präfix: opt-in für EINZELNE Sender, die echte Programmdaten
    # von der Sky-EPG-API bekommen sollen (siehe sky_epg.py), statt der
    # generischen kategoriebasierten Platzhaltertexte. Im Unterschied
    # zum TELEMACH:-Mechanismus gibt es hier BEWUSST KEIN automatisches
    # Matching gegen alle Sender mit Land "DE"/"GB" - zu viele Zeilen in
    # sender.txt, das wären zu viele API-Aufrufe pro Lauf und ein zu
    # hohes Fehltreffer-Risiko. Nur Sender mit dieser Zeile bekommen die
    # echten Daten.
    #
    # SYNTAX (3 Felder, analog zum TELEMACH:-Schema, optional ein 4.
    # Feld fuer Playlist-Namen, die NICHT dem normalen "DE|"/"UK|"-
    # Schema folgen):
    #
    #   SKY:<Territory, "DE" oder "GB", optional/Default "DE">|<Kanalname wie bei Sky>|<Logo-URL>
    #   SKY:<Territory>|<Suchbegriff wie bei Sky>|<Logo-URL>|<Kompletter Playlist-Name/ID, falls abweichend>
    #
    # Beispiele:
    #   SKY:DE|Sky Sport Bundesliga 1|https://example.com/logo.png
    #   SKY:GB|Sky Showcase|https://example.com/logo.png
    #   SKY:DE|SKY CRIME|https://example.com/logo.png|WOW| SKY CRIME ᴴᴰ ◉
    #
    # "DE" deckt technisch auch Oesterreich/Schweiz mit ab (Sky kennt
    # dafuer kein eigenes Territory - "Sky Sport Austria"-Kanaele laufen
    # ueber DE). Andere Werte als DE/GB fallen graceful auf "DE" zurück
    # (siehe sky_epg.py).
    #
    # Der Kanalname (2. Feld) wird als Suchbegriff gegen die
    # Sky-Kanalliste verwendet (sky_kanal_finden(), erst exakt
    # normalisiert, dann difflib-Fuzzy-Match) UND - falls kein 4. Feld
    # angegeben ist - 1:1 als <channel> id/display-name (wie bei
    # NAME:/TELEMACH:). Manche Playlists benennen Sky-Buendel-Sender
    # aber unter einem komplett anderen Praefix (z.B. "WOW| ..." statt
    # "DE| .../UK| ...") - fuer genau diesen Fall kann das optionale 4.
    # Feld den kompletten, echten Playlist-Namen 1:1 vorgeben, waehrend
    # das 2. Feld weiterhin nur als Sky-Suchbegriff dient. Für die
    # ersten bis zu 2 Tage werden - sofern Kanalsuche/Programmabruf
    # gelingen - echte Sendungen eingetragen; alle weiteren Tage (und
    # bei jedem Fehlschlag der Sky-Anfrage) fallen exakt auf die
    # normale, generische Generierung zurück wie bei jedem anderen
    # Sender.
    if zeile.upper().startswith("SKY:"):
        rest = zeile[len("SKY:"):]
        # maxsplit=3: das optionale 4. Feld (ID-Override) darf selbst
        # Pipe-Zeichen enthalten (z.B. "WOW| SKY CRIME ᴴᴰ ◉") - wird
        # daher NICHT weiter zerschnitten, alles ab dem 3. Pipe bleibt
        # als ein Stueck erhalten.
        teile_sky = [x.strip() for x in rest.split("|", 3)]

        while len(teile_sky) < 4:
            teile_sky.append("")

        sky_territory = teile_sky[0].upper() or "DE"
        if sky_territory == "UK":
            sky_territory = "GB"
        if sky_territory not in ("DE", "GB"):
            sky_territory = "DE"

        sky_kanalname = teile_sky[1]
        sky_logo = teile_sky[2]
        sky_id_override = teile_sky[3]

        if not sky_kanalname:
            continue

        # Anzeige-Land: Sky selbst kennt nur "GB" als Territory-Code
        # (siehe sky_territory oben, wird 1:1 an sky_epg.py durchgereicht),
        # aber in der eigenen IPTV-Playlist des Nutzers heissen britische
        # Sender durchgehend "UK|..." statt "GB|..." - fuer die
        # automatische TiviMate-Zuordnung muss die <channel> id/
        # display-name daher "UK" zeigen, nicht "GB".
        sky_anzeige_land = "UK" if sky_territory == "GB" else sky_territory

        sky_auto_beschreibung = f"{sky_kanalname.title()} ᴸⁱᵛᵉ"
        sky_kategorie_key = None

        sender_daten.append({
            "kanal": sky_id_override if sky_id_override else f"{sky_anzeige_land}| {sky_kanalname}",
            "land": sky_anzeige_land,
            "sender": sky_kanalname,
            "beschreibung": sky_auto_beschreibung,
            "logo": sky_logo,
            "exakter_name": True,
            "event_titel": None,
            "kategorie": sky_kategorie_key,
            "sky": {"territory": sky_territory},
        })
        continue

    # MAGENTA:-Präfix: opt-in für EINZELNE Sender, die echte
    # Programmdaten von Magenta TV (Deutsche Telekom) bekommen sollen
    # (siehe magenta_epg.py), statt der generischen kategoriebasierten
    # Platzhaltertexte. Genau wie bei SKY: gibt es hier BEWUSST KEIN
    # automatisches Matching gegen alle Sender mit Land "DE" - nur
    # Sender mit dieser Zeile bekommen die echten Daten.
    #
    # SYNTAX (3 Felder, analog zum SKY:-Schema):
    #
    #   MAGENTA:<Territory, nur "DE" unterstützt/Default>|<Kanalname wie bei Magenta>|<Logo-URL>
    #
    # Beispiel:
    #   MAGENTA:DE|RTL|https://example.com/logo.png
    #
    # Der Kanalname (2. Feld) wird 1:1 als <channel> id/display-name
    # verwendet (wie bei NAME:/SKY:) UND als Suchbegriff gegen die
    # Magenta-Kanalliste (magenta_kanal_finden(), erst exakt
    # normalisiert, dann difflib-Fuzzy-Match). Dabei wird zuerst die
    # neuere www.magenta.tv-API versucht, bei keinem Treffer/keinen
    # Daten als zweiter Versuch die ältere web.magentatv.de-API (analog
    # zum Telemach->mtel.ba-Fallback). Für die ersten bis zu 2 Tage
    # werden - sofern eine der beiden Quellen etwas liefert - echte
    # Sendungen eingetragen; alle weiteren Tage (und bei Fehlschlag
    # beider Quellen) fallen exakt auf die normale, generische
    # Generierung zurück wie bei jedem anderen Sender.
    if zeile.upper().startswith("MAGENTA:"):
        rest = zeile[len("MAGENTA:"):]
        teile_magenta = [x.strip() for x in rest.split("|")]

        while len(teile_magenta) < 3:
            teile_magenta.append("")

        # Territory ist aktuell fest auf "DE" - andere Werte werden
        # graceful ignoriert/auf "DE" zurückgesetzt (siehe magenta_epg.py).
        magenta_territory = teile_magenta[0].upper() or "DE"
        if magenta_territory != "DE":
            magenta_territory = "DE"

        magenta_kanalname = teile_magenta[1]
        magenta_logo = teile_magenta[2]

        if not magenta_kanalname:
            continue

        magenta_auto_beschreibung = f"{magenta_kanalname.title()} ᴸⁱᵛᵉ"
        magenta_kategorie_key = None

        sender_daten.append({
            "kanal": f"DE| {magenta_kanalname}",
            "land": "DE",
            "sender": magenta_kanalname,
            "beschreibung": magenta_auto_beschreibung,
            "logo": magenta_logo,
            "exakter_name": True,
            "event_titel": None,
            "kategorie": magenta_kategorie_key,
            "magenta": True,
        })
        continue

    # ARENA:-Präfix: opt-in für EINZELNE Sender, die echte Programmdaten
    # von den HTML-gescrapten Arena-Sport-Seiten (siehe arena_epg.py)
    # bekommen sollen, statt der generischen kategoriebasierten
    # Platzhaltertexte. Genau wie bei SKY: gibt es hier BEWUSST KEIN
    # automatisches Matching - nur Sender mit dieser Zeile bekommen die
    # echten Daten.
    #
    # SYNTAX (3 Felder, analog zum SKY:-Schema):
    #
    #   ARENA:<Land HR oder RS>|<Kanalname, z.B. "Arena Sport 1">|<Logo-URL>
    #
    # Beispiele:
    #   ARENA:HR|Arena Sport 1|https://example.com/logo.png
    #   ARENA:RS|Arena Sport 2 Serbia|https://example.com/logo.png
    #
    # Land bestimmt, welche Seite gescrapt wird (HR -> tvarenasport.hr,
    # RS -> tvarenasport.com) und welche Zeitzone gilt (HR: Europe/
    # Budapest, RS: Europe/Belgrade). Unbekannte/leere Werte fallen
    # graceful auf HR zurück. Der Kanalname (2. Feld) wird 1:1 als
    # <channel> id/display-name verwendet UND als Suchbegriff gegen die
    # Arena-Kanalliste (arena_kanal_finden(), erst exakt normalisiert,
    # dann difflib-Fuzzy-Match). Für die verfügbaren Tage (bis zu
    # ARENA_TAGE) werden - sofern Kanalsuche/Programmabruf gelingen -
    # echte Sendungen eingetragen; alle weiteren Tage (und bei jedem
    # Fehlschlag) fallen exakt auf die normale, generische Generierung
    # zurück wie bei jedem anderen Sender.
    if zeile.upper().startswith("ARENA:"):
        rest = zeile[len("ARENA:"):]
        teile_arena = [x.strip() for x in rest.split("|")]

        while len(teile_arena) < 3:
            teile_arena.append("")

        arena_land = teile_arena[0].upper() or "HR"
        if arena_land not in ("HR", "RS"):
            arena_land = "HR"

        arena_kanalname = teile_arena[1]
        arena_logo = teile_arena[2]

        if not arena_kanalname:
            continue

        arena_auto_beschreibung = f"{arena_kanalname.title()} ᴸⁱᵛᵉ"
        arena_kategorie_key = None

        sender_daten.append({
            "kanal": f"{arena_land}| {arena_kanalname}",
            "land": arena_land,
            "sender": arena_kanalname,
            "beschreibung": arena_auto_beschreibung,
            "logo": arena_logo,
            "exakter_name": True,
            "event_titel": None,
            "kategorie": arena_kategorie_key,
            "arena": {"land": arena_land},
        })
        continue

    # DAZN:-Präfix: opt-in für EINZELNE Sender, die echte Programmdaten
    # von der DAZN-Rail-API (siehe dazn_epg.py) bekommen sollen, statt der
    # generischen kategoriebasierten Platzhaltertexte. Genau wie bei SKY:/
    # ARENA: gibt es hier BEWUSST KEIN automatisches Matching - nur Sender
    # mit dieser Zeile bekommen die echten Daten.
    #
    # SYNTAX (3 Felder, analog zum SKY:/ARENA:-Schema):
    #
    #   DAZN:<Land, 2-Buchstaben-Ländercode, optional, Default DE>|<Kanalname wie bei DAZN>|<Logo-URL>
    #
    # Beispiel:
    #   DAZN:DE|DAZN 1 HD|https://example.com/logo.png
    #
    # Im Unterschied zu SKY: (nur "DE") und ARENA: (nur "HR"/"RS")
    # unterstützt DAZN beliebige 2-Buchstaben-Ländercodes (die echte DAZN-
    # API deckt viele Länder ab) - ein leerer oder ungültiger Wert fällt
    # graceful auf "DE" zurück (siehe dazn_epg.py). Der Kanalname (2. Feld)
    # wird 1:1 als <channel> id/display-name verwendet UND als Suchbegriff
    # gegen die DAZN-Kanalliste (dazn_kanal_finden(), erst exakt
    # normalisiert, dann difflib-Fuzzy-Match). DAZNs API liefert kein
    # echtes mehrtägiges Datumsraster, sondern nur ihr aktuelles Now/Next/
    # Later-Fenster (siehe dazn_epg.py-Docstring) - entsprechend dünn ist
    # die Datenabdeckung in der Praxis. Alle weiteren Tage (und bei jedem
    # Fehlschlag der DAZN-Anfrage) fallen exakt auf die normale,
    # generische Generierung zurück wie bei jedem anderen Sender.
    if zeile.upper().startswith("DAZN:"):
        rest = zeile[len("DAZN:"):]
        teile_dazn = [x.strip() for x in rest.split("|")]

        while len(teile_dazn) < 3:
            teile_dazn.append("")

        dazn_land = teile_dazn[0].lower() or "de"
        if not (len(dazn_land) == 2 and dazn_land.isalpha()):
            dazn_land = "de"

        dazn_kanalname = teile_dazn[1]
        dazn_logo = teile_dazn[2]

        if not dazn_kanalname:
            continue

        dazn_auto_beschreibung = f"{dazn_kanalname.title()} ᴸⁱᵛᵉ"
        dazn_kategorie_key = None

        sender_daten.append({
            "kanal": f"{dazn_land.upper()}| {dazn_kanalname}",
            "land": dazn_land.upper(),
            "sender": dazn_kanalname,
            "beschreibung": dazn_auto_beschreibung,
            "logo": dazn_logo,
            "exakter_name": True,
            "event_titel": None,
            "kategorie": dazn_kategorie_key,
            "dazn": {"land": dazn_land},
        })
        continue

    # FREEVIEW:-Präfix: opt-in für EINZELNE Sender, die echte
    # Programmdaten von der Freeview-UK-TV-Guide-API (siehe
    # freeview_epg.py) bekommen sollen, statt der generischen
    # kategoriebasierten Platzhaltertexte. Genau wie bei SKY:/DAZN: gibt
    # es hier BEWUSST KEIN automatisches Matching - nur Sender mit
    # dieser Zeile bekommen die echten Daten.
    #
    # SYNTAX (3 Felder, analog zum SKY:/DAZN:-Schema):
    #
    #   FREEVIEW:<Land, nur "GB" unterstützt, optional, Default GB>|<Kanalname wie bei Freeview>|<Logo-URL>
    #
    # Beispiel:
    #   FREEVIEW:GB|BBC One|https://example.com/logo.png
    #
    # Es wird nur "GB" unterstützt (jeder andere Wert fällt still auf
    # "GB" zurück). Der Kanalname (2. Feld) wird 1:1 als <channel>
    # id/display-name verwendet UND als Suchbegriff gegen die Freeview-
    # Kanalliste (freeview_kanal_finden(), erst exakt normalisiert, dann
    # difflib-Fuzzy-Match). Die Kanalliste deckt nur die eine
    # repräsentative Network-ID "Greater London" ab, also nur NATIONALE
    # Kanäle, keine regionalen Opt-out-Varianten (siehe
    # freeview_epg.py-Docstring). Jeder Fehlschlag der Freeview-Anfrage
    # fällt exakt auf die normale, generische Generierung zurück wie bei
    # jedem anderen Sender.
    if zeile.upper().startswith("FREEVIEW:"):
        rest = zeile[len("FREEVIEW:"):]
        teile_freeview = [x.strip() for x in rest.split("|")]

        while len(teile_freeview) < 3:
            teile_freeview.append("")

        freeview_land = teile_freeview[0].upper() or "GB"
        if freeview_land == "UK":
            freeview_land = "GB"
        if freeview_land != "GB":
            freeview_land = "GB"

        # Anzeige-Land "UK" statt "GB" (siehe gleicher Kommentar beim
        # SKY:-Block oben) - Freeview kennt intern ohnehin kein eigenes
        # Territory-Konzept, freeview_epg.py deckt immer nur GB ab.
        freeview_anzeige_land = "UK"

        freeview_kanalname = teile_freeview[1]
        freeview_logo = teile_freeview[2]

        if not freeview_kanalname:
            continue

        freeview_auto_beschreibung = f"{freeview_kanalname.title()} ᴸⁱᵛᵉ"
        freeview_kategorie_key = None

        sender_daten.append({
            "kanal": f"{freeview_anzeige_land}| {freeview_kanalname}",
            "land": freeview_anzeige_land,
            "sender": freeview_kanalname,
            "beschreibung": freeview_auto_beschreibung,
            "logo": freeview_logo,
            "exakter_name": True,
            "event_titel": None,
            "kategorie": freeview_kategorie_key,
            "freeview": True,
        })
        continue

    # TVGUIDE:-Präfix: opt-in für EINZELNE Sender, die echte
    # Programmdaten von der TVGuide.com-US-API (siehe tvguide_epg.py)
    # bekommen sollen, statt der generischen kategoriebasierten
    # Platzhaltertexte. Genau wie bei SKY:/DAZN:/FREEVIEW: gibt es hier
    # BEWUSST KEIN automatisches Matching - nur Sender mit dieser Zeile
    # bekommen die echten Daten.
    #
    # SYNTAX (3 Felder, analog zum SKY:/DAZN:-Schema):
    #
    #   TVGUIDE:<Land, nur "US" unterstützt, optional, Default US>|<Kanalname wie bei TVGuide>|<Logo-URL>
    #
    # Beispiel:
    #   TVGUIDE:US|CBS|https://example.com/logo.png
    #
    # Es wird nur "US" unterstützt (jeder andere Wert fällt still auf
    # "US" zurück). Der Kanalname (2. Feld) wird 1:1 als <channel>
    # id/display-name verwendet UND als Suchbegriff gegen die TVGuide-
    # Kanalliste (tvguide_kanal_finden(), erst exakt normalisiert, dann
    # difflib-Fuzzy-Match). Die Kanalliste deckt nur die eine fest
    # hinterlegte, nationale providerId ab, keine lokalen/anbieter-
    # spezifischen Sender (siehe tvguide_epg.py-Docstring). Jeder
    # Fehlschlag der TVGuide-Anfrage fällt exakt auf die normale,
    # generische Generierung zurück wie bei jedem anderen Sender.
    if zeile.upper().startswith("TVGUIDE:"):
        rest = zeile[len("TVGUIDE:"):]
        teile_tvguide = [x.strip() for x in rest.split("|")]

        while len(teile_tvguide) < 3:
            teile_tvguide.append("")

        tvguide_land = teile_tvguide[0].upper() or "US"
        if tvguide_land != "US":
            tvguide_land = "US"

        tvguide_kanalname = teile_tvguide[1]
        tvguide_logo = teile_tvguide[2]

        if not tvguide_kanalname:
            continue

        tvguide_auto_beschreibung = f"{tvguide_kanalname.title()} ᴸⁱᵛᵉ"
        tvguide_kategorie_key = None

        sender_daten.append({
            "kanal": f"{tvguide_land}| {tvguide_kanalname}",
            "land": tvguide_land,
            "sender": tvguide_kanalname,
            "beschreibung": tvguide_auto_beschreibung,
            "logo": tvguide_logo,
            "exakter_name": True,
            "event_titel": None,
            "kategorie": tvguide_kategorie_key,
            "tvguide": True,
        })
        continue

    # TVPASSPORT:-Präfix: opt-in für EINZELNE Sender, die echte
    # Programmdaten von tvpassport.com (siehe tvpassport_epg.py) bekommen
    # sollen, statt der generischen kategoriebasierten Platzhaltertexte.
    # Genau wie bei TVGUIDE:/SKY:/DAZN:/FREEVIEW: gibt es hier BEWUSST
    # KEIN automatisches Matching - nur Sender mit dieser Zeile bekommen
    # die echten Daten. Im Unterschied zu TVGUIDE: (eine feste nationale
    # Grundaufstellung) deckt tvpassport.com ~19.000 LOKALE US-Sender pro
    # Stadt/Call-Sign ab (z. B. "FOX (KFFX) Yakima, WA").
    #
    # SYNTAX (3 Felder, analog zum TVGUIDE:-Schema, optional ein 4.
    # Feld fuer Playlist-Namen, die NICHT dem "US| ..."-Schema folgen,
    # analog zum SKY:-ID-Override):
    #
    #   TVPASSPORT:<Land, nur "US" unterstützt, optional, Default US>|<Kanalname wie bei TVPassport>|<Logo-URL>
    #   TVPASSPORT:<Land>|<Suchbegriff wie bei TVPassport>|<Logo-URL>|<Kompletter Playlist-Name/ID, falls abweichend>
    #
    # Beispiele:
    #   TVPASSPORT:US|FOX (KFFX) Yakima, WA|https://example.com/logo.png
    #   TVPASSPORT:US|FOX (KTTV) Los Angeles, CA HD|https://example.com/logo.png|TUBI| FOX 11 LOS ANGELES ᴿᴬᵂ
    #
    # Es wird nur "US" unterstützt (jeder andere Wert fällt still auf
    # "US" zurück). Der Kanalname (2. Feld) wird als Suchbegriff gegen
    # die statische, im Repo mitgelieferte TVPassport-Kanalliste
    # verwendet (tvpassport_kanal_finden(), erst exakt normalisiert,
    # dann difflib-Fuzzy-Match) UND - falls kein 4. Feld angegeben ist -
    # 1:1 als <channel> id/display-name. Manche Playlists benennen
    # solche lokalen US-Sender aber unter einem komplett anderen
    # Praefix (z.B. "TUBI| ..." statt "US| ...") - fuer genau diesen
    # Fall kann das optionale 4. Feld den kompletten, echten Playlist-
    # Namen 1:1 vorgeben. Jeder Fehlschlag der TVPassport-Anfrage fällt
    # exakt auf die normale, generische Generierung zurück wie bei
    # jedem anderen Sender.
    if zeile.upper().startswith("TVPASSPORT:"):
        rest = zeile[len("TVPASSPORT:"):]
        # maxsplit=3: das optionale 4. Feld (ID-Override) darf selbst
        # Pipe-Zeichen enthalten (z.B. "TUBI| FOX 11 LOS ANGELES ᴿᴬᵂ").
        teile_tvpassport = [x.strip() for x in rest.split("|", 3)]

        while len(teile_tvpassport) < 4:
            teile_tvpassport.append("")

        tvpassport_land = teile_tvpassport[0].upper() or "US"
        if tvpassport_land != "US":
            tvpassport_land = "US"

        tvpassport_kanalname = teile_tvpassport[1]
        tvpassport_logo = teile_tvpassport[2]
        tvpassport_id_override = teile_tvpassport[3]

        if not tvpassport_kanalname:
            continue

        tvpassport_auto_beschreibung = f"{tvpassport_kanalname.title()} ᴸⁱᵛᵉ"
        tvpassport_kategorie_key = None

        sender_daten.append({
            "kanal": tvpassport_id_override if tvpassport_id_override else f"{tvpassport_land}| {tvpassport_kanalname}",
            "land": tvpassport_land,
            "sender": tvpassport_kanalname,
            "beschreibung": tvpassport_auto_beschreibung,
            "logo": tvpassport_logo,
            "exakter_name": True,
            "event_titel": None,
            "kategorie": tvpassport_kategorie_key,
            "tvpassport": True,
        })
        continue

    # Leeres Land-Feld (Zeile beginnt mit "|"): fuer Sender, deren
    # echter Playlist-Name selbst KEIN Land-Praefix hat (z.B.
    # "24/7 GHOST ADVENTURES SCREAMING ROOM") oder deren Name selbst
    # ein Pipe-Zeichen enthaelt (z.B. "US| GHOST ADVENTURES FHD" mit
    # Leerzeichen nach dem Pipe als fester Teil des Playlist-Namens).
    # Hier wird NUR an den LETZTEN ZWEI Pipes der Zeile getrennt
    # (Beschreibung, Logo) - alles davor bleibt unveraendert der
    # komplette Sendername, egal wie viele Pipes er selbst enthaelt.
    # Ohne diese Ausnahme wuerde kanal = f"{land}|{sender}" faelschlich
    # ein fuehrendes "|" einfuegen bzw. der Name wuerde am falschen
    # Pipe zerschnitten - beides wuerde das Playlist-Matching
    # verhindern.
    if zeile.startswith("|"):
        rechte_teile = [x.strip() for x in zeile[1:].rsplit("|", 2)]
        while len(rechte_teile) < 3:
            rechte_teile.append("")
        # rsplit(maxsplit=2) liefert bei WENIGER als 2 Pipes im Rest zu
        # wenige Elemente an der falschen Position (Logo wuerde in die
        # Beschreibung-Spalte rutschen) - deshalb wird bei nur 1 Pipe
        # (Sender + Logo, keine Beschreibung) die leere Beschreibung
        # eingeschoben statt hinten angehaengt.
        if "|" in zeile[1:] and zeile[1:].count("|") == 1:
            sender, logo = rechte_teile[0], rechte_teile[1]
            beschreibung = ""
        else:
            sender, beschreibung, logo = rechte_teile[0], rechte_teile[1], rechte_teile[2]
        land = ""
        kanal = sender
        leeres_land_zeile = True
    else:
        leeres_land_zeile = False
        teile = [x.strip() for x in zeile.split("|")]

        while len(teile) < 4:
            teile.append("")

        land = teile[0]
        sender = teile[1]
        beschreibung = teile[2]
        logo = teile[3]
        kanal = f"{land}| {sender}"

    auto_beschreibung, kategorie_key = standard_beschreibung(land, sender)

    # "AUTO" ist im Beschreibungsfeld reserviert (analog zum Logofeld,
    # siehe LOGO_AUTO_MARKER) - schuetzt vor dem haeufigen Tippfehler
    # "Land|Sender|AUTO" (fehlender Pipe vor dem eigentlich gemeinten
    # "Land|Sender||AUTO"), bei dem "AUTO" sonst versehentlich im
    # Beschreibungsfeld statt im Logofeld landet und woertlich als
    # Sendungstext erscheinen wuerde.
    manueller_text = beschreibung if beschreibung.strip().upper() != LOGO_AUTO_MARKER else ""

    if beschreibung == "" or beschreibung.strip().upper() == LOGO_AUTO_MARKER:
        beschreibung = auto_beschreibung

    # DAZN-Sender: im Gegensatz zu DYN PPV/Flo Racing aendert sich der
    # Kanalname bei DAZN NICHT dynamisch (kein Event-Text im Namen
    # selbst). Trotzdem soll hier nicht die generische, kategorie-
    # basierte Standardbeschreibung erscheinen, sondern schlicht der
    # eigentliche Kanalname selbst (z.B. "DAZN Bar 1 HD"), damit im
    # EPG-Raster erkennbar ist, um welchen konkreten DAZN-Sender es
    # sich handelt statt eines generischen Sport-Textes.
    direkter_text_event_titel = kanalname_normal_geschrieben(sender) if "DAZN" in sender.upper() else None

    # Manuell eingetragener Text im Beschreibungsfeld (3. Spalte) hat
    # Vorrang vor allem anderen: wird 1:1 als Sendungstitel/-beschreibung
    # uebernommen, ohne Kategorie-Text oder Variation - fuer Sender, bei
    # denen einfach immer derselbe feste Text gewuenscht ist, statt der
    # automatisch generierten, abwechslungsreichen Kategorie-Beschreibung.
    if manueller_text:
        direkter_text_event_titel = manueller_text

    eintrag = {
        "kanal": kanal,
        "land": land,
        "sender": sender,
        "beschreibung": beschreibung,
        "logo": logo,
        "exakter_name": leeres_land_zeile,
        "event_titel": direkter_text_event_titel,
        "kategorie": kategorie_key
    }

    # Automatischer Telemach-Abgleich fuer BA/ME-Sender: kein eigenes
    # TELEMACH:-Prefix noetig - jeder ganz normal eingetragene Sender
    # mit Land "BA" oder "ME" (bzw. den in sender.txt gebraeuchlichen
    # Alias-Kuerzeln "MNG"/"CG" fuer Crna Gora/Montenegro) wird beim
    # Generieren zusaetzlich per Name gegen die Telemach-Kanalliste
    # geprueft (siehe telemach_epg.py und der Verarbeitungsblock bei
    # "telemach_sender" weiter unten). Bei Treffer werden fuer die
    # ersten bis zu 3 Tage echte Sendungen eingetragen, sonst faellt
    # der Sender unveraendert auf die normale generische Beschreibung
    # zurueck - reine Zusatzanreicherung ohne Risiko fuer bestehende
    # Sender.
    TELEMACH_LAND_ALIAS = {"BA": "ba", "ME": "me", "MNG": "me", "CG": "me", "MO": "me"}
    if land.strip().upper() in TELEMACH_LAND_ALIAS:
        eintrag["telemach"] = {"country": TELEMACH_LAND_ALIAS[land.strip().upper()]}

    # Automatischer Abgleich fuer RS/HR/SI/MK-Sender: analog zum BA/ME-
    # Telemach-Autoabgleich oben - kein eigenes Praefix noetig, jeder
    # ganz normal eingetragene Sender mit Land "RS"/"HR"/"SI"/"MK" wird
    # beim Generieren zusaetzlich per Name gegen die jeweilige Kanalliste
    # geprueft (mts.rs/MojMaxTV/tv-spored.siol.net, siehe die
    # Verarbeitungsbloecke bei "mts_sender"/"mojmaxtv_sender"/
    # "siol_sender" weiter unten). Bei Treffer werden echte Sendungen
    # eingetragen, sonst faellt der Sender unveraendert auf die normale
    # generische Beschreibung zurueck - unabhaengige, sich gegenseitig
    # ausschliessende Zusatzanreicherungen ohne Risiko fuer bestehende
    # Sender. MK laeuft ueber dieselbe siol.net-Quelle wie SI (siol.net
    # fuehrt eine kleine Zahl mazedonischer Sender wie Alfa TV/Alsat
    # Macedonia/TV Sitel/MTV 1-3 zusaetzlich zu den slowenischen).
    if land.strip().upper() == "RS":
        eintrag["mts"] = True
    if land.strip().upper() == "HR":
        eintrag["mojmaxtv"] = True
    if land.strip().upper() in ("SI", "MK"):
        eintrag["siol"] = True
    # "PRIME" laeuft zusaetzlich zu Tubi (siehe unten) auch durch die
    # deutsche Kaskade (deswird.org/Pluto TV/tvmovie.de/hoerzu.de/
    # Samsung TV Plus) - der PRIME-Bereich der Playlist enthaelt neben
    # US-Sendern auch deutschsprachige Kanaele (z.B. "X-Factor: Das
    # Unfassbare", das als echter Live-Kanal bei Pluto TV DE existiert).
    # Tubi wird zuerst probiert (siehe tubi_sender-Verarbeitung), erst
    # danach die DE-Kaskade - kein Risiko fuer echte US-PRIME-Sender,
    # da die Namenssuche pro Quelle unabhaengig ist und nur bei
    # tatsaechlichem Treffer etwas eintraegt.
    # "WOW" (die eigene Playlist-Kennzeichnung fuer den WOW/Sky-
    # Streaming-Bereich, siehe z.B. den SKY:-Override "WOW| SKY CRIME
    # ᴴᴰ ◉") laeuft ebenfalls durch die deutsche Kaskade - WOW-Sender
    # sind inhaltlich deutsche Kanaele (z.B. "Cartoon Network", das
    # als echter Kanal bei deswird.org existiert), fuer Sky-exklusive
    # WOW-Sender bleibt zusaetzlich die explizite SKY:-Zeile mit
    # Display-ID-Override die bevorzugte Loesung.
    if land.strip().upper() in ("DE", "JOYN", "PRIME", "WOW"):
        eintrag["plutotv"] = True

    # Automatischer Tubi-TV-Abgleich fuer PRIME-/TUBI-/GO-Sender: analog
    # zum PlutoTV-Autoabgleich fuer DE - kein eigenes Praefix noetig,
    # jeder ganz normal eingetragene Sender mit Land "PRIME", "TUBI"
    # oder "GO" wird beim Generieren zusaetzlich per Name gegen die
    # Tubi-Kanalliste geprueft (siehe tubi_epg.py, Verarbeitungsblock
    # bei "tubi_sender" weiter unten). Bei Treffer werden echte
    # Sendungen UND ein passendes Kanal-Icon eingetragen, sonst faellt
    # der Sender unveraendert auf die normale generische Beschreibung
    # zurueck.
    if land.strip().upper() in ("PRIME", "TUBI", "GO"):
        eintrag["tubi"] = True

    sender_daten.append(eintrag)

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

# Die ID/Anzeigename der 20 fest kodierten API-Kanaele war bisher immer
# der hartcodierte String "DE| DYN PPV {i} HD" - anders als bei den
# NAME:-Sendern (ESPN+/SOCCER/DAZN PPV usw.), deren ID seit September
# 2026 direkt aus dem LIVE-Playlist-Namen des Nutzers uebernommen wird.
# Weicht der tatsaechliche Playlist-Name auch nur minimal ab (ein
# unsichtbares Zeichen, andere Leerzeichen-Stellung), matcht TiviMates
# automatische Zuordnung nicht, obwohl der Name auf den ersten Blick
# identisch aussieht - genau dieses Symptom wurde fuer die Kanaele 14-20
# beobachtet (manuelle Zuordnung funktioniert und bleibt bestehen,
# automatische nicht). Hier wird deshalb - analog zum NAME:-Mechanismus -
# einmalig die eigene Playlist nach den 20 "DE| DYN PPV N HD"-Kanaelen
# durchsucht und bei Treffer der exakte rohe Playlist-Name uebernommen;
# ohne PROVIDER-Secret oder bei jedem Fehler (Netzwerk, kein Treffer)
# bleibt der bisherige hartcodierte String als Fallback stehen - keine
# Verhaltensaenderung fuer Nutzer ohne diese spezielle Playlist-Abweichung.
dyn_ppv_api_playlist_namen = {}
_m3u_url_fuer_dyn_ppv = os.environ.get("PROVIDER")
if _m3u_url_fuer_dyn_ppv:
    try:
        _antwort = requests.get(_m3u_url_fuer_dyn_ppv, timeout=M3U_PROVIDER_TIMEOUT_SEKUNDEN, stream=True)
        _antwort.raise_for_status()
        _gepuffert = ""
        for _chunk in _antwort.iter_content(chunk_size=65536):
            _gepuffert += _chunk.decode("utf-8", errors="ignore")
            if len(_gepuffert) > M3U_PROVIDER_MAX_ZEICHEN:
                break
        _antwort.close()

        for _zeile in _gepuffert.splitlines():
            _zeile = _zeile.strip()
            if not _zeile.startswith("#EXTINF") or "," not in _zeile:
                continue
            # Gleiche Trennlogik wie in m3u_playlist_abgleichen() (siehe
            # dortiger Kommentar): erstes Komma NACH dem letzten
            # Anfuehrungszeichen, nicht das letzte Komma der Zeile.
            _letztes_anfuehrungszeichen = _zeile.rfind('"')
            _such_start = _letztes_anfuehrungszeichen if _letztes_anfuehrungszeichen != -1 else 0
            _komma_pos = _zeile.find(",", _such_start)
            _voller_name = (_zeile[_komma_pos + 1:] if _komma_pos != -1 else _zeile.rsplit(",", 1)[-1]).strip()
            _dyn_ppv_match = re.match(r"^DE\|\s*DYN\s*PPV\s*0*(\d{1,2})\s*HD$", _voller_name, re.IGNORECASE)
            if _dyn_ppv_match:
                _nummer = int(_dyn_ppv_match.group(1))
                if 1 <= _nummer <= DYN_PPV_ANZAHL:
                    dyn_ppv_api_playlist_namen[_nummer] = _voller_name

        if dyn_ppv_api_playlist_namen:
            print(
                f"DYN-PPV-API-Kanalnamen: {len(dyn_ppv_api_playlist_namen)} von "
                f"{DYN_PPV_ANZAHL} Kanaelen mit exaktem Playlist-Namen abgeglichen"
            )
    except Exception as e:
        print("DYN-PPV-API-Kanalnamen-Abgleich Fehler:", e)

for i in range(1, DYN_PPV_ANZAHL + 1):
    kanal = dyn_ppv_api_playlist_namen.get(i, f"DE| DYN PPV {i} HD")
    logo_fuer_kanal = dyn_ppv_logo_overrides.get(
        i,
        f"https://raw.githubusercontent.com/babo20094-rgb/Epg/main/logos/dyn_ppv/dyn_ppv_{i}.png",
    )
    # display-name zeigt jetzt "DE| " wie die echte ID und wie der
    # tatsaechliche Name in der Playlist des Nutzers (bestaetigt per
    # Playlist-Check: tvg-name="DE| DYN PPV 4 HD") - vorher fehlte das
    # Laenderkuerzel im display-name, obwohl ID und Playlist-Name es
    # beide hatten. Falls TiviMate beim automatischen Zuordnen den
    # display-name statt der ID heranzieht, verhinderte genau diese
    # Abweichung die Zuordnung trotz technisch passender ID (Bug
    # September 2026 behoben).
    for kanal_id in kanal_id_varianten(kanal):
        xml_teile.append(
            f' <channel id="{escape(kanal_id)}"> <display-name>{escape(kanal)}</display-name> <icon src="{escape(logo_fuer_kanal)}"/> </channel> '
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
# (1-20) - wird unten bei den DYN LEERZEITEN gebraucht, um den
# ueberlappenden Teil der stuendlichen Platzhalter auszuschneiden.
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

                kanal = dyn_ppv_api_playlist_namen.get(kanal_nummer, f"DE| DYN PPV {kanal_nummer} HD")

                for kanal_id in kanal_id_varianten(kanal):
                    xml_teile.append(
                        f' <programme start="{startzeit}" stop="{endzeit}" channel="{escape(kanal_id)}">'
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
# DYN PPV: ZUSAETZLICH BASKETBALL (Competitions-API)
# ==========================================================
# Der /live-productions-Endpunkt oben deckt nur Handball und
# Tischtennis ab - Basketball fehlt dort komplett, obwohl die Spiele
# laut /public/competitions/{id}/matches durchaus existieren (nur ohne
# "liveProduction"-Verknuepfung, z.B. bei Sonderwettbewerben). Auf
# ausdruecklichen Nutzerwunsch wird HIER zusaetzlich NUR Basketball
# nachgeladen - kein Volleyball/Hockey/weitere Handball-/Tischtennis-
# Wettbewerbe. Jeder Wettbewerb wird einzeln abgefragt; ein Fehler bei
# einem einzelnen Wettbewerb ueberspringt nur diesen, kein Abbruch der
# gesamten DYN-Verarbeitung.
DYN_BASKETBALL_COMPETITION_IDS = {
    "Qoi9d4XUraPLu9v9HzL8fk": "NCAA College Basketball",
    "JnahjYBEhsfer9zCQbqicd": "easyCredit BBL",
    "UuDL3pJ5GAHqnLmfu6kQov": "Netto BBL Pokal",
}
# Diese API liefert keine Endzeit, nur den Anstoss - eine
# durchschnittliche Basketball-Spieldauer (inkl. Pausen/Verlaengerung)
# wird stattdessen fest angenommen.
DYN_BASKETBALL_SPIELDAUER = timedelta(hours=2)
# Nur nahe Zukunft uebernehmen (die Competitions-API liefert teils
# Spielplaene fuer Monate im Voraus) - konsistent mit dem sonstigen
# Vorschau-Horizont dieses Skripts, statt hunderter kaum relevanter
# Eintraege weit in der Zukunft.
DYN_BASKETBALL_VORSCHAU_TAGE = 14

basketball_kanal_nummer = 1
jetzt_utc = datetime.now(timezone.utc)

for competition_id, competition_name in DYN_BASKETBALL_COMPETITION_IDS.items():
    try:
        resp = requests.get(
            f"https://streaming.contentdesk.sport/api/public/competitions/{competition_id}/matches",
            timeout=DYN_API_TIMEOUT_SEKUNDEN,
        )
        resp.raise_for_status()
        matches = resp.json().get("items", [])
    except Exception as e:
        print(f"DYN Basketball ({competition_name}) Fehler:", e)
        continue

    for match in matches:
        start = match.get("scheduledAt")
        if not start:
            continue

        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        if not (jetzt_utc <= start_dt <= jetzt_utc + timedelta(days=DYN_BASKETBALL_VORSCHAU_TAGE)):
            continue
        ende_dt = start_dt + DYN_BASKETBALL_SPIELDAUER

        heim = (match.get("homeClub") or {}).get("name", "").strip()
        gast = (match.get("awayClub") or {}).get("name", "").strip()
        titel = f"{heim} - {gast}".strip(" -") if (heim or gast) else competition_name

        startzeit = start_dt.strftime("%Y%m%d%H%M%S +0000")
        endzeit = ende_dt.strftime("%Y%m%d%H%M%S +0000")
        kanal = dyn_ppv_api_playlist_namen.get(basketball_kanal_nummer, f"DE| DYN PPV {basketball_kanal_nummer} HD")

        for kanal_id in kanal_id_varianten(kanal):
            xml_teile.append(
                f' <programme start="{startzeit}" stop="{endzeit}" channel="{escape(kanal_id)}">'
                f' <title>{escape(titel)}</title> <desc>{escape(titel)}</desc> </programme> '
            )

        dyn_synth_api_fenster.setdefault(basketball_kanal_nummer, []).append(
            (start_dt, ende_dt)
        )

        basketball_kanal_nummer += 1
        if basketball_kanal_nummer > DYN_PPV_ANZAHL:
            basketball_kanal_nummer = 1

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

def _kern_und_event_aus_rohname(voller_name):
    """Versucht Kern-hinten- (DYN PPV, Flo Racing, ...), dann Kern-vorne-
    Konvention (Clubber, ...) und gibt (normalisierter_kern, real_daten,
    kurzname, event_teil) zurueck, oder (None, None, None, None) bei
    keinem Treffer in name_pipe_kanal_index."""
    kurzname, event_teil = kern_und_event_extrahieren(voller_name)
    normalisierter_kern = re.sub(r"\s+", " ", kurzname).strip().upper()
    real_daten = name_pipe_kanal_index.get(normalisierter_kern)
    if real_daten is None:
        kurzname, event_teil = kern_vorne_und_event_extrahieren(voller_name)
        if kurzname is None:
            return None, None, None, None
        normalisierter_kern = re.sub(r"\s+", " ", kurzname).strip().upper()
        real_daten = name_pipe_kanal_index.get(normalisierter_kern)
        if real_daten is None:
            return None, None, None, None
    return normalisierter_kern, real_daten, kurzname, event_teil


def _live_event_uebernehmen(kurzname, event_teil, real_daten):
    """Prueft, ob event_teil ein echtes Event ist (kein Leerlauf-Marker)
    und traegt es bei Treffer in real_daten ein. Gibt True bei
    Uebernahme zurueck. Bei Leerlauf (z.B. DYN-PPV-Platzhaltertext
    "- NO EVENT STREAMING - | 8K EXCLUSIVE") bleibt real_daten
    unveraendert - der beim Einlesen gesetzte Fallback ("Dyn Sport (N)
    ᴺᵒ ᴸⁱᵛᵉ" bei DYN PPV, generischer Kategorietext sonst) bleibt
    stehen, statt des rohen Platzhaltertexts."""
    if event_teil and not any(marker in event_teil.lower() for marker in LEERLAUF_MARKER):
        roh_segmente = [s.strip() for s in event_teil.split("|")]
        roh_marker = roh_segmente[0].lower() if roh_segmente else ""

        dyn_ppv_next_match = re.match(r"^DYN\s*PPV\s*0*(\d+)$", kurzname, re.IGNORECASE)
        if dyn_ppv_next_match and roh_marker in EVENT_MARKER_ENDE:
            # Kein fixer Abmoderationstext bei DYN PPV - stattdessen werden
            # die Teamnamen wie bei NEXT/LIVE extrahiert, nur mit "ᴮᵉᵉⁿᵈᵉᵗ"
            # als Suffix. Gelingt die Extraktion nicht, bleibt der beim
            # Einlesen bereits gesetzte Fallback ("Dyn Sport (N) ᴺᵒ ᴸⁱᵛᵉ")
            # unveraendert stehen - real_daten["event_titel"] wird dann
            # NICHT auf None ueberschrieben (sonst faellt die Sendung auf
            # den generischen kategoriebasierten Zufallstext zurueck, Bug
            # August 2026 behoben).
            team_namen = dyn_next_team_namen(event_teil, status_suffix="ᴮᵉᵉⁿᵈᵉᵗ")
            if team_namen:
                real_daten["event_titel"] = team_namen
            return True

        event_titel = formatiere_event_text(event_teil)

        if dyn_ppv_next_match:
            if roh_marker in EVENT_MARKER_NEXT:
                team_namen = dyn_next_team_namen(event_teil, status_suffix="ᴺᵉˣᵗ")
                event_titel = team_namen or f"Dyn Sport ({dyn_ppv_next_match.group(1)}) ᴺᵉˣᵗ"
            elif roh_marker in EVENT_MARKER_LIVE:
                team_namen = dyn_next_team_namen(event_teil, status_suffix="ᴸⁱᵛᵉ")
                event_titel = team_namen or f"Dyn Sport ({dyn_ppv_next_match.group(1)}) ᴸⁱᵛᵉ"

        real_daten["event_titel"] = event_titel
        return True
    return False


# ==========================================================
# LIVE-KANALNAMEN AUS DER EIGENEN IPTV-PLAYLIST
#
# Manche IPTV-Anbieter pflegen die aktuellen Live-Event-Namen direkt
# im Anzeigenamen der eigenen M3U-Playlist (z.B. Clubber: "(IE)
# (Clubber 01) | Kerry GAA: Milltown/Castlemaine vs An Ghaeltacht
# (2026-08-07 16:00:00)"). Das ist die einzige Quelle fuer Live-
# Kanalnamen (Secret PROVIDER, optional) - ohne gesetztes
# Secret bleibt es bei den generischen Kategorie-Platzhaltertexten.
# ==========================================================

M3U_PROVIDER_TIMEOUT_SEKUNDEN = 120
# Die Playlist enthaelt (anders als die myepg.top-Datei) ausschliesslich
# Kanaldefinitionen, keine Programmdaten - daher reicht ein grosszuegiges,
# aber festes Limit als Sicherheitsnetz gegen eine unerwartet riesige Datei.
M3U_PROVIDER_MAX_ZEICHEN = 80_000_000


def m3u_playlist_abgleichen(url, quelle_name):
    """Laedt die M3U-Playlist des IPTV-Anbieters und uebertraegt fuer
    jeden per Kernname matchenden NAME:-Sender (siehe
    name_pipe_kanal_index) den aktuellen Anzeigenamen aus der
    #EXTINF-Zeile als Sendungstitel. Gibt die Menge der normalisierten
    Kern-Keys zurueck, die dabei ein echtes Event geliefert haben."""
    response = requests.get(url, timeout=M3U_PROVIDER_TIMEOUT_SEKUNDEN, stream=True)
    response.raise_for_status()

    gepuffert = ""
    for chunk in response.iter_content(chunk_size=65536):
        gepuffert += chunk.decode("utf-8", errors="ignore")
        if len(gepuffert) > M3U_PROVIDER_MAX_ZEICHEN:
            break
    response.close()

    erledigte_keys = set()
    aktualisierte_sender = []
    for zeile in gepuffert.splitlines():
        zeile = zeile.strip()
        if not zeile.startswith("#EXTINF") or "," not in zeile:
            continue

        # Trennung von Attributen und Anzeigename NICHT am letzten Komma
        # der Zeile (rsplit) vornehmen - manche Anbieter haben selbst ein
        # Komma im rohen Live-Event-Namen eingebettet (z.B. "NEXT | WED,
        # 9/2 - THE RICH EISEN SHOW | ... | US: ESPN+ PPV 4"), wodurch
        # rsplit(",", 1) faelschlich den Namen ab dem eingebetteten Komma
        # abschnitt statt ab dem echten Attribute/Name-Trenner. Alle
        # #EXTINF-Attribute (tvg-id="...", group-title="...", ...) enden
        # in einem schliessenden Anfuehrungszeichen - das erste Komma NACH
        # dem letzten Anfuehrungszeichen ist daher der zuverlaessige
        # Trenner, unabhaengig davon, ob der Name selbst Kommas enthaelt.
        letztes_anfuehrungszeichen = zeile.rfind('"')
        such_start = letztes_anfuehrungszeichen if letztes_anfuehrungszeichen != -1 else 0
        komma_pos = zeile.find(",", such_start)
        voller_name = (zeile[komma_pos + 1:] if komma_pos != -1 else zeile.rsplit(",", 1)[-1]).strip()
        normalisierter_kern, real_daten, kurzname, event_teil = _kern_und_event_aus_rohname(voller_name)
        if real_daten is None:
            continue

        # Die <channel id>/den Anzeigenamen direkt auf den kompletten
        # aktuellen Rohnamen aus der Playlist setzen (egal ob gerade
        # ein Event laeuft oder Leerlauf ist) - GENAU wie es der
        # frueher genutzte externe EPG-Anbieter (myepg.top) gemacht
        # hat, der fuer diese Kanaele nachweislich zuverlaessig
        # automatisch zugeordnet wurde. Der stabile Kern bleibt nur
        # als Fallback stehen, falls die eigene Playlist gerade nicht
        # erreichbar ist oder der Sender darin fehlt (dann behaelt
        # "kanal" seinen urspruenglichen sender.txt-Wert). Bewusster
        # Trade-off (September 2026 auf Nutzerwunsch so entschieden):
        # eine einmal in TiviMate manuell gesetzte Zuordnung ueberlebt
        # dadurch nicht zwingend jeden Lauf, dafuer funktioniert die
        # AUTOMATISCHE Zuordnung zuverlaessiger, was hier Prioritaet hat.
        real_daten["kanal"] = voller_name

        if _live_event_uebernehmen(kurzname, event_teil, real_daten):
            erledigte_keys.add(normalisierter_kern)
            aktualisierte_sender.append(real_daten["sender"])

    if aktualisierte_sender:
        print(f"Live-Kanalabgleich ({quelle_name}) Treffer:", ", ".join(aktualisierte_sender))

    return erledigte_keys


if name_pipe_kanal_index:
    m3u_url = os.environ.get("PROVIDER")
    if m3u_url:
        try:
            treffer = m3u_playlist_abgleichen(m3u_url, "Live-Kanalabgleich")
            print(
                f"Live-Kanalabgleich: {len(treffer)} von "
                f"{len(name_pipe_kanal_index)} NAME:-Kanaelen mit "
                f"Live-Kanalnamen aktualisiert"
            )
        except Exception as e:
            print("Live-Kanalabgleich Fehler:", e)

# ==========================================================
# <channel>-Blöcke schreiben (sender.txt, mit ggf.
# überschriebenem Logo aus logo_only.txt)
#
# Bewusst ERST HIER (nach dem Live-Kanalabgleich oben), damit fuer
# NAME:-Sender bereits die per Live-Playlist-Abgleich ggf.
# ueberschriebene "kanal" (siehe m3u_playlist_abgleichen()) verwendet
# wird - nicht mehr der urspruengliche statische Kern.
# ==========================================================

for daten in sender_daten:

    # So wie er in der Playlist als tvg-name steht (z.B. "DE| RTL"),
    # unverändert übernommen - das ist entscheidend für die
    # automatische Sender-Zuordnung in TiviMate.
    # Ausnahme: Einträge mit "exakter_name" (aus NAME:-Zeilen in
    # sender.txt) haben ihren kompletten, echten Playlist-Namen
    # bereits direkt in "kanal" stehen (bei erfolgreichem Live-
    # Abgleich sogar den AKTUELLEN Live-Namen, siehe oben) - hier
    # NICHT aus Land+Sender neu zusammenbauen, sonst geht der Name
    # kaputt.
    if daten.get("exakter_name"):
        playlist_name = daten["kanal"]
    else:
        playlist_name = f"{daten['land']}| {daten['sender']}"

    # Fuer jede Kanal-ID-Variante (mit/ohne Leerzeichen nach dem Pipe-
    # Zeichen, siehe kanal_id_varianten()) einen eigenen <channel>-
    # Block schreiben, damit TiviMate unabhaengig von der in der
    # jeweiligen Playlist-Gruppe genutzten Schreibweise automatisch
    # zuordnen kann.
    for kanal_id in kanal_id_varianten(daten["kanal"]):
        xml_teile.append(
            f' <channel id="{escape(kanal_id)}"> <display-name>{escape(playlist_name)}</display-name>'
        )

        # Icon wird NUR erzeugt, wenn ein Logo angegeben ist
        # (aus sender.txt oder als Override aus logo_only.txt)
        if daten["logo"]:
            xml_teile.append(f' <icon src="{escape(daten["logo"])}"/>\n')

        xml_teile.append(" </channel>\n")

# Hinweis Clubber-PPV (Irland, GAA-Club-Spiele): laeuft ueber denselben
# generischen Playlist-Namensabgleich wie DYN PPV - der Anbieter fuehrt
# die 50 echten Clubber-Kanaele mit demselben Kern ("(IE) (Clubber 01)"
# usw.) nur in Kern-vorne- statt Kern-hinten-Konvention (siehe
# kern_vorne_und_event_extrahieren()).

# ==========================================================
# TELEMACH: echte Programmdaten fuer TELEMACH:-Sender (siehe
# telemach_epg.py und der Parsing-Kommentar oben bei "TELEMACH:").
# Login und Kanalliste werden dank Caching in telemach_epg.py nur
# einmal pro Land geholt, egal wie viele TELEMACH:-Sender es gibt.
# Ohne jegliche TELEMACH:-Zeile in sender.txt passiert hier gar
# nichts - keine zusaetzlichen Netzwerk-Aufrufe.
# ==========================================================

TELEMACH_TAGE = 3
MTEL_TAGE = 2
MYMEDIA_TAGE = 3
KLIX_TAGE = 3
SKY_TAGE = 2
MAGENTA_TAGE = 2
ARENA_TAGE = 2
DAZN_TAGE = 3
FREEVIEW_TAGE = 2
TVGUIDE_TAGE = 2
TVPASSPORT_TAGE = 2
MTS_TAGE = 2
MOJMAXTV_TAGE = 2
SIOL_TAGE = 2
DESWIRD_TAGE = 3
PLUTOTV_TAGE = 2
TVMOVIE_TAGE = 1
SAMSUNGTV_TAGE = 1
TUBI_TAGE = 2
telemach_sender = [d for d in sender_daten if d.get("telemach")]
sky_sender = [d for d in sender_daten if d.get("sky")]
magenta_sender = [d for d in sender_daten if d.get("magenta")]
arena_sender = [d for d in sender_daten if d.get("arena")]
dazn_sender = [d for d in sender_daten if d.get("dazn")]
freeview_sender = [d for d in sender_daten if d.get("freeview")]
tvguide_sender = [d for d in sender_daten if d.get("tvguide")]
tvpassport_sender = [d for d in sender_daten if d.get("tvpassport")]
mts_sender = [d for d in sender_daten if d.get("mts")]
mojmaxtv_sender = [d for d in sender_daten if d.get("mojmaxtv")]
siol_sender = [d for d in sender_daten if d.get("siol")]
plutotv_sender = [d for d in sender_daten if d.get("plutotv")]
tubi_sender = [d for d in sender_daten if d.get("tubi")]


BESCHREIBUNG_MAX_LAENGE = 150
BESCHREIBUNG_SATZ_WORT_MINDEST = 6
BESCHREIBUNG_SATZENDE_MUSTER = re.compile(r"(?<!\d)[.!?](?:\s+(?=[A-ZÀ-ÖØ-Þ])|$)")


def _wirkt_wie_ausformulierter_satz(segment):
    """True, wenn ein an ": " abgetrenntes Textsegment wie ein
    ausformulierter Erklaersatz aussieht (grossgeschrieben, endet mit
    Satzzeichen, mehrere Woerter) statt wie ein kompaktes Namens-/Datums-
    Fragment (z.B. "Ried - Grazer" oder "15.8.")."""
    segment = segment.strip()
    if not segment:
        return False
    if not segment[0].isupper():
        return False
    if not segment.rstrip().endswith((".", "!", "?", "…")):
        return False
    return len(segment.split()) >= BESCHREIBUNG_SATZ_WORT_MINDEST


def kuerze_beschreibung(text, max_laenge=BESCHREIBUNG_MAX_LAENGE):
    """Kuerzt lange Sendungstitel/-beschreibungen echter Quellen (z.B.
    Telemachs "shortDescription", das bei Sport-/Magazin-Events oft
    einen generischen Liga-/Ankuendigungstext nach den eigentlichen
    Kerndaten anhaengt, etwa "Fudbal - Austrijska liga: Ried - Grazer:
    Salzburg je austrijski fudbal podigao..." oder "Vijesti: Najnovije
    informacije iz...") auf die reinen Kerndaten statt des kompletten
    Fliesstexts - manche Player (z.B. TiviMate) zeigen sonst den ganzen
    Text direkt im kompakten EPG-Raster an. Der Text wird an ": "
    aufgeteilt; jedes abschliessende Segment, das wie ein ausformulierter
    Satz aussieht (siehe _wirkt_wie_ausformulierter_satz()), wird
    entfernt - so bleiben nur die kompakten Kern-Segmente (Kategorie/
    Liga/Teams/Datum) uebrig, unabhaengig vom genauen Format der
    jeweiligen Quelle. Ohne erkennbares Satz-Segment wird bei sehr
    langen Texten hart bei einer Wortgrenze abgeschnitten und "…"
    angehaengt. Kurze Texte bleiben unveraendert."""
    if not text:
        return text
    text = text.strip()
    segmente = text.split(": ")
    while len(segmente) > 1 and _wirkt_wie_ausformulierter_satz(segmente[-1]):
        segmente.pop()
    gekuerzter_text = ": ".join(segmente).strip().rstrip(" :;,")
    if gekuerzter_text != text:
        return gekuerzter_text
    # Kein Doppelpunkt-Segment erkannt (z.B. reiner Fliesstext ohne
    # "Kategorie: Teams:"-Struktur, nur durchgehende Saetze): auf den
    # ersten vollstaendigen Satz kuerzen, falls der noch deutlich
    # kompakter als der Gesamttext ist.
    satzende = BESCHREIBUNG_SATZENDE_MUSTER.search(text)
    if satzende and satzende.end() < len(text) and satzende.end() <= max_laenge:
        return text[: satzende.end()].strip()
    if len(text) <= max_laenge:
        return text
    gekuerzt = text[:max_laenge].rsplit(" ", 1)[0]
    return gekuerzt.rstrip(".,;: ") + "…"


def _schreibe_echte_programme(daten, programme):
    """Haengt die uebergebenen echten Programmdaten (Telemach ODER
    mtel.ba, gleiches dict-Format) als <programme>-Eintraege an
    xml_teile an."""
    kanal_ids = kanal_id_varianten(daten["kanal"])
    for p in programme:
        start_str = p["start"].strftime("%Y%m%d%H%M%S +0000")
        stop_str = p["stop"].strftime("%Y%m%d%H%M%S +0000")
        titel_escaped = escape(kuerze_beschreibung(p["title"]))
        beschr_text = kuerze_beschreibung(p["beschreibung"] or p["title"])
        beschr_escaped = escape(beschr_text)
        # Bewusst KEIN <sub-title> mehr: manche Player (z.B. TiviMate)
        # haengen den Untertitel im kompakten Wochenraster direkt hinter
        # den Titel an, wodurch trotz gekuerztem Titel wieder ein langer
        # Text in der Zeile stand. Nur der Titel soll dort sichtbar
        # sein - die volle Beschreibung bleibt im <desc>-Feld erhalten
        # und ist ueber die Detailansicht weiterhin abrufbar.
        icon_tag = f' <icon src="{escape(p["bild"])}"/>' if p.get("bild") else ""
        for kanal_id in kanal_ids:
            xml_teile.append(
                f' <programme start="{start_str}" stop="{stop_str}" channel="{escape(kanal_id)}">'
                f' <title lang="de">{titel_escaped}</title>'
                f' <desc lang="de">{beschr_escaped}</desc>{icon_tag} </programme> '
            )


for daten in telemach_sender:
    programme = []
    try:
        site_id = telemach_kanal_finden(daten["sender"], daten["telemach"]["country"])
        if site_id is not None:
            programme = telemach_hole_programme(
                site_id, daten["telemach"]["country"], TELEMACH_TAGE
            )
        else:
            pass  # log unterdrueckt: keine echten Programmdaten
    except Exception as e:
        # Darf den Lauf niemals abbrechen - jeder Fehler faellt auf die
        # generische Generierung fuer diesen Sender zurueck.
        pass  # log unterdrueckt: keine echten Programmdaten
        programme = []

    daten["telemach_intervalle"] = [(p["start"], p["stop"]) for p in programme]
    echte_daten_gefunden = bool(programme)

    if programme:
        print(f"Telemach-EPG: {len(programme)} echte Sendungen fuer '{daten['sender']}' geladen.")
        _schreibe_echte_programme(daten, programme)
    else:
        pass  # log unterdrueckt: keine echten Programmdaten

        # mtel.ba als zweiter Versuch: nur fuer BA-Sender (mtel.ba kennt
        # kein Montenegro), und nur weil Telemach fuer diesen Sender
        # nichts gefunden hat. Kein Merge beider Quellen - entweder
        # Telemach ODER mtel.ba ODER generisch.
        if daten["telemach"]["country"] == "ba":
            mtel_programme = []
            try:
                mtel_site_id = mtel_kanal_finden(daten["sender"])
                if mtel_site_id is not None:
                    mtel_programme = mtel_hole_programme(mtel_site_id, MTEL_TAGE)
                else:
                    pass  # log unterdrueckt: keine echten Programmdaten
            except Exception as e:
                pass  # log unterdrueckt: keine echten Programmdaten
                mtel_programme = []

            daten["mtel_intervalle"] = [(p["start"], p["stop"]) for p in mtel_programme]

            if mtel_programme:
                print(f"Mtel-EPG: {len(mtel_programme)} echte Sendungen fuer '{daten['sender']}' geladen (Telemach-Fallback).")
                _schreibe_echte_programme(daten, mtel_programme)
                echte_daten_gefunden = True
            else:
                pass  # log unterdrueckt: keine echten Programmdaten

                # mymedia.ba als dritter Versuch: deckt technisch nur
                # EINEN festen Kanal ab ("MY TV", siehe mymedia_epg.py),
                # daher hier per Namensvergleich statt Kanalsuche - nur
                # wenn Telemach UND mtel.ba nichts gefunden haben.
                if normalisiere_sendername(daten["sender"]) == normalisiere_sendername("MY TV"):
                    mymedia_programme = []
                    try:
                        mymedia_programme = mymedia_hole_programme(MYMEDIA_TAGE)
                    except Exception as e:
                        pass  # log unterdrueckt: keine echten Programmdaten
                        mymedia_programme = []

                    daten["mymedia_intervalle"] = [(p["start"], p["stop"]) for p in mymedia_programme]

                    if mymedia_programme:
                        print(f"MyMedia-EPG: {len(mymedia_programme)} echte Sendungen fuer '{daten['sender']}' geladen (Telemach/Mtel-Fallback).")
                        _schreibe_echte_programme(daten, mymedia_programme)
                        echte_daten_gefunden = True
                    else:
                        pass  # log unterdrueckt: keine echten Programmdaten

                # klix.ba als vierter Versuch fuer BA-Sender (siehe
                # klix_epg.py), nur wenn Telemach UND mtel.ba (UND ggf.
                # mymedia.ba) nichts gefunden haben.
                if not echte_daten_gefunden:
                    klix_programme = []
                    try:
                        klix_site_id = klix_kanal_finden(daten["sender"])
                        if klix_site_id is not None:
                            klix_programme = klix_hole_programme(klix_site_id, KLIX_TAGE)
                        else:
                            pass  # log unterdrueckt: keine echten Programmdaten
                    except Exception as e:
                        pass  # log unterdrueckt: keine echten Programmdaten
                        klix_programme = []

                    daten["klix_intervalle"] = [(p["start"], p["stop"]) for p in klix_programme]

                    if klix_programme:
                        print(f"Klix-EPG: {len(klix_programme)} echte Sendungen fuer '{daten['sender']}' geladen (Telemach/Mtel-Fallback).")
                        _schreibe_echte_programme(daten, klix_programme)
                        echte_daten_gefunden = True
                    else:
                        pass  # log unterdrueckt: keine echten Programmdaten

# ==========================================================
# SKY: echte Programmdaten fuer SKY:-Sender (siehe sky_epg.py und der
# Parsing-Kommentar oben bei "SKY:"). Rein opt-in, unabhaengig von
# Telemach/mtel.ba (die sind BA/ME-only, Sky ist DE-only - beide
# Mechanismen schliessen sich gegenseitig aus). Ohne jegliche
# SKY:-Zeile in sender.txt passiert hier gar nichts - keine
# zusaetzlichen Netzwerk-Aufrufe.
# ==========================================================

for daten in sky_sender:
    programme = []
    try:
        site_id = sky_kanal_finden(daten["sender"], daten["sky"]["territory"])
        if site_id is not None:
            programme = sky_hole_programme(site_id, daten["sky"]["territory"], SKY_TAGE)
        else:
            pass  # log unterdrueckt: keine echten Programmdaten
    except Exception as e:
        # Darf den Lauf niemals abbrechen - jeder Fehler faellt auf die
        # generische Generierung fuer diesen Sender zurueck.
        pass  # log unterdrueckt: keine echten Programmdaten
        programme = []

    daten["sky_intervalle"] = [(p["start"], p["stop"]) for p in programme]

    if programme:
        print(f"Sky-EPG: {len(programme)} echte Sendungen fuer '{daten['sender']}' geladen.")
        _schreibe_echte_programme(daten, programme)
    else:
        pass  # log unterdrueckt: keine echten Programmdaten

# ==========================================================
# MAGENTA: echte Programmdaten fuer MAGENTA:-Sender (siehe magenta_epg.py
# und der Parsing-Kommentar oben bei "MAGENTA:"). Rein opt-in,
# unabhaengig von den anderen Quellen. Ohne jegliche MAGENTA:-Zeile in
# sender.txt passiert hier gar nichts - keine zusaetzlichen
# Netzwerk-Aufrufe.
# ==========================================================

for daten in magenta_sender:
    programme = []
    try:
        kanal_ref = magenta_kanal_finden(daten["sender"])
        if kanal_ref is not None:
            programme = magenta_hole_programme(kanal_ref, MAGENTA_TAGE)
        else:
            pass  # log unterdrueckt: keine echten Programmdaten
    except Exception as e:
        # Darf den Lauf niemals abbrechen - jeder Fehler faellt auf die
        # generische Generierung fuer diesen Sender zurueck.
        pass  # log unterdrueckt: keine echten Programmdaten
        programme = []

    daten["magenta_intervalle"] = [(p["start"], p["stop"]) for p in programme]

    if programme:
        print(f"Magenta-EPG: {len(programme)} echte Sendungen fuer '{daten['sender']}' geladen.")
        _schreibe_echte_programme(daten, programme)
    else:
        pass  # log unterdrueckt: keine echten Programmdaten

# ==========================================================
# ARENA: echte Programmdaten fuer ARENA:-Sender (siehe arena_epg.py und
# der Parsing-Kommentar oben bei "ARENA:"). Rein opt-in, unabhaengig von
# den anderen Quellen. Ohne jegliche ARENA:-Zeile in sender.txt passiert
# hier gar nichts - keine zusaetzlichen Netzwerk-Aufrufe.
# ==========================================================

for daten in arena_sender:
    programme = []
    try:
        site_id = arena_kanal_finden(daten["sender"], daten["arena"]["land"])
        if site_id is not None:
            programme = arena_hole_programme(site_id, daten["arena"]["land"], ARENA_TAGE)
        else:
            pass  # log unterdrueckt: keine echten Programmdaten
    except Exception as e:
        # Darf den Lauf niemals abbrechen - jeder Fehler faellt auf die
        # generische Generierung fuer diesen Sender zurueck.
        pass  # log unterdrueckt: keine echten Programmdaten
        programme = []

    daten["arena_intervalle"] = [(p["start"], p["stop"]) for p in programme]

    if programme:
        print(f"Arena-EPG: {len(programme)} echte Sendungen fuer '{daten['sender']}' geladen.")
        _schreibe_echte_programme(daten, programme)
    else:
        pass  # log unterdrueckt: keine echten Programmdaten

# ==========================================================
# DAZN: echte Programmdaten fuer DAZN:-Sender (siehe dazn_epg.py und der
# Parsing-Kommentar oben bei "DAZN:"). Rein opt-in, unabhaengig von den
# anderen Quellen. Ohne jegliche DAZN:-Zeile in sender.txt passiert hier
# gar nichts - keine zusaetzlichen Netzwerk-Aufrufe.
# ==========================================================

for daten in dazn_sender:
    programme = []
    try:
        site_id = dazn_kanal_finden(daten["sender"], daten["dazn"]["land"])
        if site_id is not None:
            programme = dazn_hole_programme(site_id, daten["dazn"]["land"], DAZN_TAGE)
        else:
            pass  # log unterdrueckt: keine echten Programmdaten
    except Exception as e:
        # Darf den Lauf niemals abbrechen - jeder Fehler faellt auf die
        # generische Generierung fuer diesen Sender zurueck.
        pass  # log unterdrueckt: keine echten Programmdaten
        programme = []

    daten["dazn_intervalle"] = [(p["start"], p["stop"]) for p in programme]

    if programme:
        print(f"DAZN-EPG: {len(programme)} echte Sendungen fuer '{daten['sender']}' geladen.")
        _schreibe_echte_programme(daten, programme)
    else:
        pass  # log unterdrueckt: keine echten Programmdaten

# ==========================================================
# FREEVIEW: echte Programmdaten fuer FREEVIEW:-Sender (siehe
# freeview_epg.py und der Parsing-Kommentar oben bei "FREEVIEW:"). Rein
# opt-in, unabhaengig von den anderen Quellen. Ohne jegliche
# FREEVIEW:-Zeile in sender.txt passiert hier gar nichts - keine
# zusaetzlichen Netzwerk-Aufrufe.
# ==========================================================

for daten in freeview_sender:
    programme = []
    try:
        site_id = freeview_kanal_finden(daten["sender"])
        if site_id is not None:
            programme = freeview_hole_programme(site_id, FREEVIEW_TAGE)
        else:
            pass  # log unterdrueckt: keine echten Programmdaten
    except Exception as e:
        # Darf den Lauf niemals abbrechen - jeder Fehler faellt auf die
        # generische Generierung fuer diesen Sender zurueck.
        pass  # log unterdrueckt: keine echten Programmdaten
        programme = []

    daten["freeview_intervalle"] = [(p["start"], p["stop"]) for p in programme]

    if programme:
        print(f"Freeview-EPG: {len(programme)} echte Sendungen fuer '{daten['sender']}' geladen.")
        _schreibe_echte_programme(daten, programme)
    else:
        pass  # log unterdrueckt: keine echten Programmdaten

# ==========================================================
# TVGUIDE: echte Programmdaten fuer TVGUIDE:-Sender (siehe
# tvguide_epg.py und der Parsing-Kommentar oben bei "TVGUIDE:"). Rein
# opt-in, unabhaengig von den anderen Quellen. Ohne jegliche
# TVGUIDE:-Zeile in sender.txt passiert hier gar nichts - keine
# zusaetzlichen Netzwerk-Aufrufe.
# ==========================================================

for daten in tvguide_sender:
    programme = []
    try:
        site_id = tvguide_kanal_finden(daten["sender"])
        if site_id is not None:
            programme = tvguide_hole_programme(site_id, TVGUIDE_TAGE)
        else:
            pass  # log unterdrueckt: keine echten Programmdaten
    except Exception as e:
        # Darf den Lauf niemals abbrechen - jeder Fehler faellt auf die
        # generische Generierung fuer diesen Sender zurueck.
        pass  # log unterdrueckt: keine echten Programmdaten
        programme = []

    daten["tvguide_intervalle"] = [(p["start"], p["stop"]) for p in programme]

    if programme:
        print(f"TVGuide-EPG: {len(programme)} echte Sendungen fuer '{daten['sender']}' geladen.")
        _schreibe_echte_programme(daten, programme)
    else:
        pass  # log unterdrueckt: keine echten Programmdaten

# ==========================================================
# TVPASSPORT: echte Programmdaten fuer TVPASSPORT:-Sender (siehe
# tvpassport_epg.py und der Parsing-Kommentar oben bei "TVPASSPORT:").
# Rein opt-in, unabhaengig von den anderen Quellen. Ohne jegliche
# TVPASSPORT:-Zeile in sender.txt passiert hier gar nichts - keine
# zusaetzlichen Netzwerk-Aufrufe.
# ==========================================================

for daten in tvpassport_sender:
    programme = []
    try:
        site_id = tvpassport_kanal_finden(daten["sender"])
        if site_id is not None:
            programme = tvpassport_hole_programme(site_id, TVPASSPORT_TAGE)
        else:
            pass  # log unterdrueckt: keine echten Programmdaten
    except Exception as e:
        # Darf den Lauf niemals abbrechen - jeder Fehler faellt auf die
        # generische Generierung fuer diesen Sender zurueck.
        pass  # log unterdrueckt: keine echten Programmdaten
        programme = []

    daten["tvpassport_intervalle"] = [(p["start"], p["stop"]) for p in programme]

    if programme:
        print(f"TVPassport-EPG: {len(programme)} echte Sendungen fuer '{daten['sender']}' geladen.")
        _schreibe_echte_programme(daten, programme)
    else:
        pass  # log unterdrueckt: keine echten Programmdaten

# ==========================================================
# MTS: automatischer Abgleich fuer alle RS-Sender (siehe mts_epg.py und
# der Parsing-Kommentar oben bei "Automatischer Abgleich fuer RS/HR/
# SI-Sender"). Kein eigenes Praefix noetig. Ohne jegliche RS-Zeile in
# sender.txt passiert hier gar nichts - keine zusaetzlichen Netzwerk-
# Aufrufe.
# ==========================================================

for daten in mts_sender:
    programme = []
    try:
        site_id = mts_kanal_finden(daten["sender"])
        if site_id is not None:
            programme = mts_hole_programme(site_id, MTS_TAGE)
        else:
            pass  # log unterdrueckt: keine echten Programmdaten
    except Exception as e:
        pass  # log unterdrueckt: keine echten Programmdaten
        programme = []

    daten["mts_intervalle"] = [(p["start"], p["stop"]) for p in programme]

    if programme:
        print(f"Mts-EPG: {len(programme)} echte Sendungen fuer '{daten['sender']}' geladen.")
        _schreibe_echte_programme(daten, programme)
    else:
        pass  # log unterdrueckt: keine echten Programmdaten

# ==========================================================
# MOJMAXTV: automatischer Abgleich fuer alle HR-Sender (siehe
# mojmaxtv_epg.py). Kein eigenes Praefix noetig. Ohne jegliche
# HR-Zeile in sender.txt passiert hier gar nichts - keine
# zusaetzlichen Netzwerk-Aufrufe.
# ==========================================================

for daten in mojmaxtv_sender:
    programme = []
    try:
        site_id = mojmaxtv_kanal_finden(daten["sender"])
        if site_id is not None:
            programme = mojmaxtv_hole_programme(site_id, MOJMAXTV_TAGE)
        else:
            pass  # log unterdrueckt: keine echten Programmdaten
    except Exception as e:
        pass  # log unterdrueckt: keine echten Programmdaten
        programme = []

    daten["mojmaxtv_intervalle"] = [(p["start"], p["stop"]) for p in programme]

    if programme:
        print(f"MojMaxTV-EPG: {len(programme)} echte Sendungen fuer '{daten['sender']}' geladen.")
        _schreibe_echte_programme(daten, programme)
    else:
        pass  # log unterdrueckt: keine echten Programmdaten

# ==========================================================
# SPORTKLUB: zweiter Versuch fuer alle HR-Sender, bei denen MojMaxTV
# nichts gefunden hat (siehe sportklub_epg.py - MojMaxTV fuehrt seit
# September 2026 keine "Sport Klub"-Kanaele mehr, betrifft "HR|SK N").
# Kein eigenes Praefix noetig, laeuft automatisch als Fallback nach
# MojMaxTV innerhalb derselben mojmaxtv_sender-Liste.
# ==========================================================

for daten in mojmaxtv_sender:
    if daten.get("mojmaxtv_intervalle"):
        continue  # MojMaxTV hat fuer diesen Sender bereits echte Daten geliefert

    programme = []
    try:
        site_id = sportklub_kanal_finden(daten["sender"])
        if site_id is not None:
            programme = sportklub_hole_programme(site_id, MOJMAXTV_TAGE)
        else:
            pass  # log unterdrueckt: keine echten Programmdaten
    except Exception as e:
        pass  # log unterdrueckt: keine echten Programmdaten
        programme = []

    daten["sportklub_intervalle"] = [(p["start"], p["stop"]) for p in programme]

    if programme:
        print(f"SportKlub-EPG: {len(programme)} echte Sendungen fuer '{daten['sender']}' geladen.")
        _schreibe_echte_programme(daten, programme)
    else:
        pass  # log unterdrueckt: keine echten Programmdaten

# ==========================================================
# SIOL: automatischer Abgleich fuer alle SI- UND MK-Sender (siehe
# siol_epg.py - HTML-Scraping, fragiler als die anderen Quellen). Kein
# eigenes Praefix noetig. Ohne jegliche SI-/MK-Zeile in sender.txt
# passiert hier gar nichts - keine zusaetzlichen Netzwerk-Aufrufe.
# ==========================================================

for daten in siol_sender:
    programme = []
    try:
        site_id = siol_kanal_finden(daten["sender"])
        if site_id is not None:
            programme = siol_hole_programme(site_id, SIOL_TAGE)
        else:
            pass  # log unterdrueckt: keine echten Programmdaten
    except Exception as e:
        pass  # log unterdrueckt: keine echten Programmdaten
        programme = []

    daten["siol_intervalle"] = [(p["start"], p["stop"]) for p in programme]

    if programme:
        print(f"Siol-EPG: {len(programme)} echte Sendungen fuer '{daten['sender']}' geladen.")
        _schreibe_echte_programme(daten, programme)
    else:
        pass  # log unterdrueckt: keine echten Programmdaten

# ==========================================================
# DESWIRD / PLUTOTV / TVMOVIE / HOERZU / SAMSUNGTV: automatischer
# Abgleich fuer alle DE-Sender (siehe deswird_epg.py, plutotv_epg.py,
# tvmovie_epg.py, hoerzu_epg.py, samsungtv_epg.py). Kein eigenes
# Praefix noetig, einzige automatischen Quellen fuer DE - deswird.org
# als primaere Quelle (beste Abdeckung/Qualitaet, mehrere Tage im
# Voraus), Pluto TV als zweiter Versuch, tvmovie.de als dritter
# Versuch, hoerzu.de als vierter Versuch, Samsung TV Plus als fuenfter
# Versuch, jeweils nur wenn die vorherige(n) Quelle(n) nichts gefunden
# haben. Ohne jegliche DE-Zeile in sender.txt passiert hier gar nichts.
# ==========================================================

for daten in plutotv_sender:
    # "MAGENTA SPORT PPV N"-Sender ueberspringen deswird.org/PlutoTV/
    # tvmovie.de/hoerzu.de/Samsung TV Plus komplett und gehen direkt zu
    # myTeamTV (siehe magenta_myteam_epg.py) - deswird.org matcht diese
    # Sender sonst per unscharfem Abgleich faelschlich auf den voellig
    # anderen, echten Basis-Kanal "MagentaSport" und liefert dessen
    # generischen "MagentaSport Programmübersicht"-Platzhaltertext, der
    # als "echter Treffer" durchgeht und myTeamTV nie zum Zug kommen
    # laesst (Bug September 2026 behoben).
    if re.match(r"^MAGENTA\s*SPORT\s*PPV\s*\d+", daten["sender"], re.IGNORECASE):
        programme = []
        try:
            myteam_site_id = magenta_myteam_kanal_finden(daten["sender"])
            if myteam_site_id is not None:
                programme = magenta_myteam_hole_programme(myteam_site_id, PLUTOTV_TAGE)
        except Exception as e:
            programme = []

        daten["magenta_myteam_intervalle"] = [(p["start"], p["stop"]) for p in programme]

        if programme:
            print(f"Magenta-myTeamTV-EPG: {len(programme)} echte Sendungen fuer '{daten['sender']}' geladen.")
            _schreibe_echte_programme(daten, programme)
        continue

    programme = []
    try:
        site_id = deswird_kanal_finden(daten["sender"])
        if site_id is not None:
            programme = deswird_hole_programme(site_id, DESWIRD_TAGE)
        else:
            pass  # log unterdrueckt: keine echten Programmdaten
    except Exception as e:
        pass  # log unterdrueckt: keine echten Programmdaten
        programme = []

    daten["deswird_intervalle"] = [(p["start"], p["stop"]) for p in programme]

    if programme:
        print(f"Deswird-EPG: {len(programme)} echte Sendungen fuer '{daten['sender']}' geladen.")
        _schreibe_echte_programme(daten, programme)
        continue

    # Pluto TV als zweiter Versuch fuer DE-Sender (siehe
    # plutotv_epg.py), nur wenn deswird.org nichts gefunden hat.
    programme = []
    try:
        site_id = plutotv_kanal_finden(daten["sender"])
        if site_id is not None:
            programme = plutotv_hole_programme(site_id, PLUTOTV_TAGE)
        else:
            pass  # log unterdrueckt: keine echten Programmdaten
    except Exception as e:
        pass  # log unterdrueckt: keine echten Programmdaten
        programme = []

    daten["plutotv_intervalle"] = [(p["start"], p["stop"]) for p in programme]

    if programme:
        print(f"PlutoTV-EPG: {len(programme)} echte Sendungen fuer '{daten['sender']}' geladen.")
        _schreibe_echte_programme(daten, programme)
    else:
        pass  # log unterdrueckt: keine echten Programmdaten

        # tvmovie.de als dritter Versuch fuer DE-Sender (siehe
        # tvmovie_epg.py), nur wenn weder deswird.org noch Pluto TV
        # etwas gefunden haben.
        tvmovie_programme = []
        try:
            tvmovie_site_id = tvmovie_kanal_finden(daten["sender"])
            if tvmovie_site_id is not None:
                tvmovie_programme = tvmovie_hole_programme(tvmovie_site_id, TVMOVIE_TAGE)
            else:
                pass  # log unterdrueckt: keine echten Programmdaten
        except Exception as e:
            pass  # log unterdrueckt: keine echten Programmdaten
            tvmovie_programme = []

        daten["tvmovie_intervalle"] = [(p["start"], p["stop"]) for p in tvmovie_programme]

        if tvmovie_programme:
            print(f"TvMovie-EPG: {len(tvmovie_programme)} echte Sendungen fuer '{daten['sender']}' geladen (Deswird/PlutoTV-Fallback).")
            _schreibe_echte_programme(daten, tvmovie_programme)
        else:
            # hoerzu.de als vierter Versuch fuer DE-Sender (siehe
            # hoerzu_epg.py), nur wenn weder deswird.org noch Pluto TV
            # noch tvmovie.de etwas gefunden haben.
            hoerzu_programme = []
            try:
                hoerzu_slug = hoerzu_kanal_finden(daten["sender"])
                if hoerzu_slug is not None:
                    hoerzu_programme = hoerzu_hole_programme(hoerzu_slug)
                else:
                    pass  # log unterdrueckt: keine echten Programmdaten
            except Exception as e:
                pass  # log unterdrueckt: keine echten Programmdaten
                hoerzu_programme = []

            daten["hoerzu_intervalle"] = [(p["start"], p["stop"]) for p in hoerzu_programme]

            if hoerzu_programme:
                print(f"Hoerzu-EPG: {len(hoerzu_programme)} echte Sendungen fuer '{daten['sender']}' geladen (Deswird/PlutoTV/TvMovie-Fallback).")
                _schreibe_echte_programme(daten, hoerzu_programme)
            else:
                # Samsung TV Plus als fuenfter Versuch fuer DE-Sender
                # (siehe samsungtv_epg.py), nur wenn weder deswird.org
                # noch Pluto TV noch tvmovie.de noch hoerzu.de etwas
                # gefunden haben.
                samsungtv_programme = []
                try:
                    samsungtv_site_id = samsungtv_kanal_finden(daten["sender"])
                    if samsungtv_site_id is not None:
                        samsungtv_programme = samsungtv_hole_programme(samsungtv_site_id, SAMSUNGTV_TAGE)
                    else:
                        pass  # log unterdrueckt: keine echten Programmdaten
                except Exception as e:
                    pass  # log unterdrueckt: keine echten Programmdaten
                    samsungtv_programme = []

                daten["samsungtv_intervalle"] = [(p["start"], p["stop"]) for p in samsungtv_programme]

                if samsungtv_programme:
                    print(f"SamsungTV-EPG: {len(samsungtv_programme)} echte Sendungen fuer '{daten['sender']}' geladen (Deswird/PlutoTV/TvMovie/Hoerzu-Fallback).")
                    _schreibe_echte_programme(daten, samsungtv_programme)

# ==========================================================
# TUBI: automatischer Abgleich fuer alle PRIME-Sender (siehe
# tubi_epg.py - community-gepflegte, loginfreie XMLTV-Datei mit echten
# Tubi-TV-Sendungen und Kanal-Icons). Kein eigenes Praefix noetig.
# Ohne jegliche PRIME-Zeile in sender.txt passiert hier gar nichts.
# ==========================================================

for daten in tubi_sender:
    # PRIME-Sender laufen zusaetzlich durch die DE-Kaskade (siehe oben,
    # deswird.org/Pluto TV/tvmovie.de/hoerzu.de/Samsung TV Plus) - hat
    # die bereits echte Daten gefunden UND geschrieben, wird Tubi hier
    # uebersprungen, damit dieselben Sendungen nicht doppelt ins XML
    # geschrieben werden.
    if any(daten.get(feld) for feld in (
        "deswird_intervalle", "plutotv_intervalle", "tvmovie_intervalle",
        "hoerzu_intervalle", "samsungtv_intervalle",
    )):
        continue

    programme = []
    try:
        site_id = tubi_kanal_finden(daten["sender"])
        if site_id is not None:
            programme = tubi_hole_programme(site_id, TUBI_TAGE)
            # Kanal-Icon von Tubi uebernehmen, aber nur wenn noch kein
            # manuelles Logo in sender.txt gesetzt wurde (leeres Feld
            # oder der "AUTO"-Marker fuer die spaetere automatische
            # Logo-Suche).
            if daten["logo"].strip().upper() in ("", LOGO_AUTO_MARKER):
                tubi_icon = tubi_kanal_icon(site_id)
                if tubi_icon:
                    daten["logo"] = tubi_icon
        else:
            pass  # log unterdrueckt: keine echten Programmdaten
    except Exception as e:
        pass  # log unterdrueckt: keine echten Programmdaten
        programme = []

    daten["tubi_intervalle"] = [(p["start"], p["stop"]) for p in programme]

    if programme:
        print(f"Tubi-EPG: {len(programme)} echte Sendungen fuer '{daten['sender']}' geladen.")
        _schreibe_echte_programme(daten, programme)
    else:
        pass  # log unterdrueckt: keine echten Programmdaten

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

# Sender-Hash haengt nur vom (unveraenderlichen) Sendernamen ab - einmal
# pro Sender berechnen statt bei jedem Tag/Block-Durchlauf erneut.
for daten in sender_daten:
    daten["_hash"] = sender_hash(daten["sender"])

for tag_index in range(ANZAHL_TAGE):

    tag_start = starttag + timedelta(days=tag_index)
    stunden_cursor = 0

    for block_index, (dauer, tageszeit) in enumerate(TAGESRASTER):

        start = tag_start + timedelta(hours=stunden_cursor)
        ende = start + timedelta(hours=dauer)
        stunden_cursor += dauer

        for daten in sender_daten:
            kategorie_key = daten.get("kategorie")
            hash_wert = daten["_hash"]

            # DYN PPV 1-50, Flo Racing, Clubber & andere NAME:-Sender: hat
            # sich der Kanalname wegen eines laufenden/angekuendigten
            # Events geaendert (siehe Erkennung weiter oben beim
            # Einlesen bzw. beim EPG-Anbieter-Abgleich), wird dieser
            # Event-Name hier 1:1 als Sendungstitel/-beschreibung
            # uebernommen - unabhaengig von einer im Text erkennbaren
            # Uhrzeit. Steht das Event im Kanalnamen, steht es auch im
            # EPG-Raster; verschwindet es dort wieder, verschwindet es
            # auch hier wieder (naechster Skriptlauf). Ohne Event bleibt
            # es beim bisherigen kategoriebasierten Text.
            event_titel = daten.get("event_titel")

            if event_titel:
                titel_text = escape(event_titel)
                beschr_text = event_titel
                lang_code = "de"
                schreibe_programme_segmente(
                    xml_teile, [(start, ende)], daten["kanal"],
                    titel_text, beschr_text, lang_code,
                    kategorie_key, daten["land"], True,
                )
                continue

            # Echte EPG-Quellen (Telemach/mtel.ba/mymedia.ba/klix.ba, Sky,
            # Magenta, Arena, DAZN, Freeview, TVGuide, TVPassport, Pluto TV/
            # tvmovie.de/hoerzu.de, MTS, MojMaxTV, Siol, Tubi - siehe
            # _ECHTE_QUELLEN_INTERVALLE): fuer den von einer echten Quelle
            # bereits ABGEDECKTEN Teil dieses Blocks wird hier nichts
            # generisch nachgeneriert - sonst gaebe es doppelte/
            # ueberlappende <programme>-Eintraege fuer denselben Zeitraum.
            # Frueher wurde bei einer nur TEILWEISEN Ueberlappung (z.B.
            # weil eine Quelle wie tvmovie.de nur ca. 05:00-20:00 Uhr statt
            # des vollen Tages abdeckt, oder weil die letzte echte Sendung
            # mitten in diesem Block endet) der KOMPLETTE Block
            # uebersprungen - der unbedeckte Rest bekam dadurch GAR KEINEN
            # <programme>-Eintrag, was im Player als "Keine Information"-
            # Luecke zwischen letzter echter Sendung und dem naechsten
            # generischen Block auffiel. Jetzt wird ueber
            # segmente_ohne_ueberlappung() praezise nur der tatsaechlich
            # unbedeckte Rest ermittelt und mit "<Sendername> ᴸⁱᵛᵉ" gefuellt
            # statt des generischen, abwechslungsreichen Kategorietexts -
            # weniger verwirrend als ein zufaellig wirkender Platzhaltertext
            # neben echten Sendungen am selben Tag.
            if hat_aktive_echte_quelle(daten):
                rest_segmente = segmente_ohne_ueberlappung(
                    start, ende, alle_echten_intervalle(daten)
                )
                if rest_segmente:
                    luecken_titel = f"{kanalname_normal_geschrieben(daten['sender'])} ᴸⁱᵛᵉ"
                    schreibe_programme_segmente(
                        xml_teile, rest_segmente, daten["kanal"],
                        escape(luecken_titel), luecken_titel, "de",
                        kategorie_key, daten["land"], True,
                    )
                continue

            # Kein echtes Programm bekannt: statt eines abwechslungsreichen,
            # kategoriebasierten Zufallstitels wird hier einheitlich nur
            # "<Sendername> ᴸⁱᵛᵉ" fuer den gesamten Block angezeigt - gleiche
            # Konvention wie bei den Luecken echter Quellen weiter oben.
            luecken_titel = f"{kanalname_normal_geschrieben(daten['sender'])} ᴸⁱᵛᵉ"
            schreibe_programme_segmente(
                xml_teile, [(start, ende)], daten["kanal"],
                escape(luecken_titel), luecken_titel, "de",
                kategorie_key, daten["land"], True,
            )

# ==========================================================
# DYN LEERZEITEN
# ==========================================================

jetzt = datetime.now(timezone.utc).replace(
    hour=0, minute=0, second=0, microsecond=0
)

for i in range(1, DYN_PPV_ANZAHL + 1):
    kanal = dyn_ppv_api_playlist_namen.get(i, f"DE| DYN PPV {i} HD")
    kanal_ids = kanal_id_varianten(kanal)
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

            # Gleiche Leerlauf-Konvention wie bei den Playlist-basierten
            # DYN PPV 1-50-Sendern ("Dyn Sport (N) ᴺᵒ ᴸⁱᵛᵉ") statt eines
            # eigenen, abweichenden Textes - auf Nutzerwunsch vereinheitlicht.
            leerlauf_text = f"Dyn Sport ({i}) ᴺᵒ ᴸⁱᵛᵉ"
            for kanal_id in kanal_ids:
                xml_teile.append(
                    f' <programme start="{start_str}" stop="{ende_str}" channel="{escape(kanal_id)}">'
                    f' <title>{escape(leerlauf_text)}</title>'
                    f' <desc>{escape(leerlauf_text)}</desc> </programme> '
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

# Zusaetzlich gzip-komprimiert schreiben (Epg_365_Tage.xml.gz) - seit dem
# Playlist-Vollimport (August/September 2026, ~19.000 statt ~2.200 Sender)
# ueberschreitet die unkomprimierte XML-Datei GitHubs 100-MB-Dateilimit
# (ca. 200+ MB), wodurch der automatische Commit im Workflow fehlschlagen
# wuerde. XML komprimiert sehr gut (repetitive Tags/Whitespace), die
# gezippte Datei bleibt deutlich unter dem Limit. Git LFS wurde bewusst
# NICHT gewaehlt, da GitHubs kostenloses LFS-Bandbreiten-Kontingent
# (1 GB/Monat) bei einer alle 3 Stunden neu gepushten ~100+ MB-Datei
# sofort aufgebraucht waere. Fast jeder IPTV-Player (u.a. TiviMate)
# unterstuetzt gezippte XMLTV-Quellen direkt per URL.
with gzip.open("Epg_365_Tage.xml.gz", "wb") as f:
    f.write(xml_inhalt.encode("utf-8"))

print(f"EPG erfolgreich erstellt ({len(sender_daten)} Sender).")
