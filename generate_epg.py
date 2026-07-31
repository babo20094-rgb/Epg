from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape
import re
import requests
import xml.etree.ElementTree as ET

from epg_lib import (
    KATEGORIEN, KATEGORIE_PRIORITAET,
    DE_STANDARD, EXYU_STANDARD, EN_STANDARD,
    EXYU_LAENDER, UK_LAENDER, US_LAENDER, EN_LAENDER,
    ALTERSFREIGABE, DEFAULT_ALTERSFREIGABE,
    TAGESRASTER, FALLBACK_LABEL, SENDETITEL_VORLAGEN, WOCHENTAGE,
    sprache_fuer_land, sendetitel, beschreibung_fuer_sender,
    sender_anzeigename, standard_beschreibung, kategorie_label,
    parse_event_zeit, datumspraefix, vorbericht_text,
)

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
        # Kern des Namens (z.B. "DYN PPV 1" oder "FLO RACING 3")
        # herausgelöst, falls vorhanden - das unterscheidet sich klar
        # vom Kanalnamen. Erfasst sowohl DYN-PPV- als auch
        # FLO-RACING-Sender (gleiches Prinzip, gleiche Behandlung).
        kurzname_match = re.search(r"(DYN\s*PPV|FLO\s*RACING)\s*\d+", voller_name, re.IGNORECASE)
        kurzname = kurzname_match.group(0) if kurzname_match else voller_name

        beschreibung, kategorie_key = standard_beschreibung("DE", kurzname)

        # DYN PPV 1-50 UND FLO RACING (diese NAME:-Einträge in
        # sender.txt - NICHT zu verwechseln mit den fest verdrahteten
        # API-Kanälen "DYN PPV 1-20" weiter unten, die unverändert
        # bleiben):
        #
        # Zwei unterschiedliche Formate, je nach Anbieter:
        #
        # a) DYN (Pipe-Format): der Name besteht aus mehreren mit "|"
        #    getrennten Teilen, z.B.
        #    "- NO EVENT STREAMING - | 8K EXCLUSIVE | DE: DYN PPV 1"
        #    Der vordere Teil (vor dem ersten "|") ist im Leerlauf ein
        #    Platzhalter ("- NO EVENT STREAMING -"), läuft ein Event
        #    steht dort stattdessen der Event-Name (z.B.
        #    "FC Bayern - Real Madrid").
        #
        # b) FLO RACING (Doppelpunkt-Format, kein "|" im Namen): im
        #    Leerlauf steht NUR der Kanalname selbst, z.B.
        #    "Flo Racing 03". Läuft ein Event, wird davor Datum/Uhrzeit
        #    eingefügt, getrennt durch ":", z.B.
        #    "Sa 14:00 : Flo Racing 05".
        #
        # In beiden Fällen gilt: steht vor dem Kurznamen zusätzlicher,
        # nicht-generischer Text -> Event läuft, dieser Text wird als
        # Sendungstitel/-beschreibung übernommen. Steht nichts oder nur
        # der bekannte "NO EVENT"-Platzhalter davor -> Leerlauf, es
        # bleibt beim generischen Standardtext (beschreibung s.o.).
        if kurzname_match and kurzname_match.start() > 0:
            # DYN- UND FLO-RACING-Format: alles vor dem gefundenen
            # Kurznamen (z.B. "DYN PPV 1"/"FLO RACING 3") ist der
            # Event-Teil - unabhaengig davon, wie viele Pipes darin
            # vorkommen (z.B. "ENDED | DEUTSCHLAND - GUINEA | IHF U18
            # WOMEN'S... | DE: DYN PPV 1"). Fruehere Version schnitt
            # hier faelschlich nur am ERSTEN Pipe, wodurch bei
            # mehrteiligen Event-Titeln fast der gesamte Titel verloren
            # ging und nur ein Fragment wie "ENDED" uebrig blieb.
            event_teil = voller_name[:kurzname_match.start()]
            # Sprach-/Land-Praefix direkt vor dem Kurznamen entfernen
            # (z.B. "... | DE: DYN PPV 1" -> das "DE:" gehoert zum
            # Kanal-Bezeichner, nicht zum Event-Titel).
            event_teil = re.sub(r"[|\s]*[A-Za-z]{2}\s*:\s*$", "", event_teil)
            event_teil = event_teil.strip(" |:").strip()
        elif "|" in voller_name:
            # Kein Kurzname im Namen gefunden, aber trotzdem Pipes
            # vorhanden - Fallback: erster Pipe-Abschnitt.
            event_teil = voller_name.split("|", 1)[0].strip()
        else:
            # Name besteht nur aus dem Kurznamen selbst -> kein Event
            event_teil = ""

        event_titel = None

        if event_teil and "no event" not in event_teil.lower():
            event_titel = event_teil

        sender_daten.append({
            "kanal": voller_name,
            "land": "DE",
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

    sender_daten.append({
        "kanal": kanal,
        "land": land,
        "sender": sender,
        "beschreibung": beschreibung,
        "logo": logo,
        "exakter_name": False,
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

        start_str = start.strftime("%Y%m%d%H%M%S +0000")
        ende_str = ende.strftime("%Y%m%d%H%M%S +0000")

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
                        datum=tag_start.date(), tag_index=tag_index
                    )
                )
                beschr_text, lang_code = beschreibung_fuer_sender(
                    kategorie_key, daten["land"], daten["sender"], hash_wert,
                    tag_index=tag_index
                )

            # Programmzeitraum: normalerweise der komplette Tagesraster-
            # Block, bei praezise erkanntem DYN/Flo-Racing-Event aber das
            # engere, tatsaechliche Event-Zeitfenster.
            if event_start_dt is not None:
                prog_start_str = event_start_dt.strftime("%Y%m%d%H%M%S +0000")
                prog_ende_str = event_ende_dt.strftime("%Y%m%d%H%M%S +0000")
            else:
                prog_start_str = start_str
                prog_ende_str = ende_str

            # Genre-Tags: die normale Kategorie, UND zusaetzlich ein
            # "Live"-Tag, sobald es sich um ein praezise erkanntes
            # DYN/Flo-Racing-Event handelt (XMLTV erlaubt mehrere
            # <category>-Tags pro Sendung, z.B. "Sport" + "Live").
            # Sprache richtet sich nach dem Land des Senders, damit
            # z.B. ein EXYU-Sender "Sport" auch in seiner Sprache
            # bekommt statt eines fix deutschen Labels.
            label = kategorie_label(kategorie_key, daten["land"])
            category_tags = ""
            if label:
                category_tags += f' <category lang="{lang_code}">{escape(label)}</category>'
            if event_start_dt is not None:
                live_label = {"de": "Live", "hr": "Uživo", "sl": "V živo", "mk": "Vo živo"}.get(lang_code, "Live")
                category_tags += f' <category lang="{lang_code}">{escape(live_label)}</category>'

            # Altersfreigabe passend zur Kategorie (Standard: 6)
            altersfreigabe = ALTERSFREIGABE.get(kategorie_key, DEFAULT_ALTERSFREIGABE)
            rating_tag = (
                f' <rating system="FSK"><value>{altersfreigabe}</value></rating>'
            )

            # Beschreibung nur in der zum Sender-Land passenden Sprache
            # (DE/EXYU/EN) - jeweils identisch fuer sub-title und desc.
            beschr_escaped = escape(beschr_text)
            desc_tag = f' <desc lang="{lang_code}">{beschr_escaped}</desc>'
            sub_title_tag = f' <sub-title lang="{lang_code}">{beschr_escaped}</sub-title>'

            xml_teile.append(
                f' <programme start="{prog_start_str}" stop="{prog_ende_str}" channel="{escape(daten["kanal"])}">'
                f' <title lang="{lang_code}">{titel_text}</title>'
                f'{sub_title_tag}'
                f'{desc_tag}{category_tags}{rating_tag} </programme> '
            )

# ==========================================================
# DYN LIVE EVENTS
# ==========================================================

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

            for event in daten:
                titel = event.get("title", "Dyn Sport")
                beschreibung = event.get("description", titel)

                start = event.get("scheduledAt")
                ende = event.get("scheduledEnd")

                if not start or not ende:
                    continue

                startzeit = datetime.fromisoformat(
                    start.replace("Z", "+00:00")
                ).strftime("%Y%m%d%H%M%S +0000")

                endzeit = datetime.fromisoformat(
                    ende.replace("Z", "+00:00")
                ).strftime("%Y%m%d%H%M%S +0000")

                kanal = f"DE| DYN PPV {kanal_nummer} HD"

                xml_teile.append(
                    f' <programme start="{startzeit}" stop="{endzeit}" channel="{escape(kanal)}">'
                    f' <title>{escape(titel)}</title> <desc>{escape(beschreibung)}</desc> </programme> '
                )

                kanal_nummer += 1
                if kanal_nummer > DYN_PPV_ANZAHL:
                    kanal_nummer = 1

except Exception as e:
    print("DYN Fehler:", e)

# ==========================================================
# DYN LEERZEITEN
# ==========================================================

jetzt = datetime.now(timezone.utc).replace(
    hour=0, minute=0, second=0, microsecond=0
)

for i in range(1, DYN_PPV_ANZAHL + 1):
    kanal = f"DE| DYN PPV {i} HD"

    for stunde in range(24 * DYN_LEERZEIT_TAGE):
        start = jetzt + timedelta(hours=stunde)
        ende = start + timedelta(hours=1)

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
