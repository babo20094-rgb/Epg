"""Einmaliges Diagnose-Skript: gleicht die LIVE-Playlist des Nutzers
(per Xtream-Codes-API, Zugangsdaten ueber Umgebungsvariablen) gegen
sender.txt ab und listet Kanaele, die auch nach kern_und_event_extrahieren()/
kern_vorne_und_event_extrahieren()-Abgleich (exakt dieselbe Logik wie
generate_epg.py) keine Zuordnung finden.

Nur fuer den manuellen Diagnose-Workflow gedacht (.github/workflows/
diagnose_playlist.yml) - liest PLAYLIST_USER/PLAYLIST_PASS/PLAYLIST_HOST
aus der Umgebung, gibt NIE Zugangsdaten aus.
"""

import json
import os
import re
import sys
from collections import Counter

import requests

HOST = os.environ["PLAYLIST_HOST"]
USER = os.environ["PLAYLIST_USER"]
PASS = os.environ["PLAYLIST_PASS"]

BASE = f"http://{HOST}/player_api.php"


def api(action, **params):
    r = requests.get(BASE, params={"username": USER, "password": PASS, "action": action, **params}, timeout=60)
    r.raise_for_status()
    return r.json()


def normalisiere(s):
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def kern_key(s):
    return re.sub(r"\s+", " ", (s or "").strip()).upper()


def kanal_id_varianten(kanal):
    match = re.match(r"^([A-Za-z]{2,5})\|(\s*)(.+)$", kanal)
    if match:
        land, _leerzeichen, rest = match.groups()
        ohne = f"{land}|{rest}"
        mit = f"{land}| {rest}"
        mit_zwei = f"{land}|  {rest}"
        varianten = [kanal] if ohne == mit else [ohne, mit, mit_zwei]
    else:
        varianten = [kanal]
    if kanal.upper().startswith("UK|"):
        rest_uk = kanal[3:]
        alias = [f"UK-{s}|{sp}{rest_uk}" for s in ("NOWTV", "BBCI") for sp in ("", " ", "  ")]
        varianten = list(dict.fromkeys(varianten + alias))
    return varianten


def extrahiere_funktionen(pfad):
    lines = open(pfad, encoding="utf-8").readlines()

    def slice_lines(a, b):
        return "".join(lines[a - 1:b - 1])

    def finde_zeile(muster, ab=1):
        for i in range(ab - 1, len(lines)):
            if re.match(muster, lines[i]):
                return i + 1
        raise RuntimeError(f"Muster nicht gefunden: {muster}")

    start_kue = finde_zeile(r"^def kern_und_event_extrahieren\(")
    start_kve = finde_zeile(r"^def kern_vorne_und_event_extrahieren\(")
    start_leer = finde_zeile(r"^LEERLAUF_MARKER")
    start_norm = finde_zeile(r"^def normalisiere_grossschreibung\(")
    start_wmr = finde_zeile(r"^def _wirkt_wie_rohtext_muell\(")
    start_eqz = finde_zeile(r"^def _echte_quelle_zaehlen\(")

    code = "import re\n\n"
    code += slice_lines(start_kue, start_kve)
    code += "\n\n"
    code += slice_lines(start_kve, start_leer)
    code += "\n\n"
    # LEERLAUF_MARKER/EVENT_MARKER_NEXT/EVENT_MARKER_LIVE/EVENT_MARKER_ENDE
    # (werden von _wirkt_wie_rohtext_muell() benoetigt).
    code += slice_lines(start_leer, start_norm)
    code += "\n\n"
    code += slice_lines(start_wmr, start_eqz)
    return code


NAMESPACE = {}
exec(extrahiere_funktionen("generate_epg.py"), NAMESPACE)
kern_und_event_extrahieren = NAMESPACE["kern_und_event_extrahieren"]
kern_vorne_und_event_extrahieren = NAMESPACE["kern_vorne_und_event_extrahieren"]
_wirkt_wie_rohtext_muell = NAMESPACE["_wirkt_wie_rohtext_muell"]


def main():
    print("Hole aktuelle Live-Kanalliste vom Anbieter ...")
    streams = api("get_live_streams")
    print(f"Playlist-Kanaele (live): {len(streams)}")

    namen = [e.get("name", "") for e in streams if e.get("name")]
    anzahl = Counter(namen)
    duplikate = {n: c for n, c in anzahl.items() if c > 1}
    print(f"Eindeutige Namen: {len(anzahl)}, Namen mit Duplikaten: {len(duplikate)}")

    standard_kanal_ids = set()
    name_kern_index = set()
    opt_in_praefixe = ("TELEMACH:", "SKY:", "MAGENTA:", "ARENA:", "DAZN:", "FREEVIEW:", "TVGUIDE:", "TVPASSPORT:")

    with open("sender.txt", encoding="utf-8") as f:
        zeilen = f.readlines()

    for rohzeile in zeilen:
        zeile = rohzeile.rstrip("\n").strip()
        if not zeile or zeile.startswith("#"):
            continue
        obenzeile = zeile.upper()

        if obenzeile.startswith("NAME:"):
            rest = zeile[len("NAME:"):]
            teile = rest.rsplit("|", 1)
            if len(teile) != 2:
                continue
            voller_name = teile[0].strip()
            if not voller_name:
                continue
            kurzname, event_teil = kern_und_event_extrahieren(voller_name)
            hinten_zurueckgerollt = False
            if kurzname != voller_name and event_teil and not _wirkt_wie_rohtext_muell(event_teil):
                kurzname, event_teil = voller_name, ""
                hinten_zurueckgerollt = True
            if kurzname == voller_name and not hinten_zurueckgerollt:
                kern_vorne, event_vorne = kern_vorne_und_event_extrahieren(voller_name)
                if kern_vorne and (not event_vorne or _wirkt_wie_rohtext_muell(event_vorne)):
                    kurzname, event_teil = kern_vorne, event_vorne
            kanal_id_fuer_eintrag = kurzname if kurzname != voller_name else voller_name
            name_kern_index.add(kern_key(kanal_id_fuer_eintrag))
            standard_kanal_ids.add(voller_name)
            continue

        ist_opt_in = False
        for praefix in opt_in_praefixe:
            if obenzeile.startswith(praefix):
                ist_opt_in = True
                rest = zeile[len(praefix):]
                teile = [x.strip() for x in rest.split("|", 3)]
                while len(teile) < 4:
                    teile.append("")
                land_feld = teile[0].upper()
                kanalname = teile[1]
                anzeigename_override = teile[3]
                if not kanalname:
                    break
                if anzeigename_override:
                    standard_kanal_ids.add(anzeigename_override)
                else:
                    if praefix == "SKY:":
                        territory = land_feld or "DE"
                        if territory == "UK":
                            territory = "GB"
                        if territory not in ("DE", "GB"):
                            territory = "DE"
                        anzeige_land = "UK" if territory == "GB" else territory
                    elif praefix == "FREEVIEW:":
                        anzeige_land = "UK"
                    elif praefix == "TVPASSPORT:":
                        anzeige_land = "US"
                    else:
                        anzeige_land = land_feld or "BA"
                    standard_kanal_ids.add(f"{anzeige_land}| {kanalname}")
                break
        if ist_opt_in:
            continue

        if zeile.startswith("|"):
            rechte_teile = [x.strip() for x in zeile[1:].rsplit("|", 2)]
            while len(rechte_teile) < 3:
                rechte_teile.append("")
            sender = rechte_teile[0]
            if sender:
                standard_kanal_ids.add(sender)
            continue

        teile = [x.strip() for x in zeile.split("|")]
        while len(teile) < 4:
            teile.append("")
        land = teile[0]
        sender = teile[1]
        if land and sender:
            standard_kanal_ids.add(f"{land}| {sender}")

    # Fest im Code verankerte DYN-PPV-1-20-Kanaele (nicht in sender.txt).
    for i in range(1, 21):
        standard_kanal_ids.add(f"DE| DYN PPV {i} HD")

    print(f"Standard-Kanal-IDs: {len(standard_kanal_ids)}")
    print(f"NAME:-Kern-Index: {len(name_kern_index)}")

    normalisierte_standard = set()
    for kid in standard_kanal_ids:
        for v in kanal_id_varianten(kid):
            normalisierte_standard.add(normalisiere(v))
        normalisierte_standard.add(normalisiere(kid))
        if "|" in kid:
            normalisierte_standard.add(normalisiere(kid.split("|", 1)[1].strip()))

    fehlend = []
    for eintrag in streams:
        name = eintrag.get("name", "")
        if not name:
            continue
        if normalisiere(name) in normalisierte_standard:
            continue
        kurzname, event_teil = kern_und_event_extrahieren(name)
        if kurzname != name and event_teil and not _wirkt_wie_rohtext_muell(event_teil):
            kurzname, event_teil = name, ""
        treffer = kern_key(kurzname) in name_kern_index
        if not treffer:
            kern_vorne, event_vorne = kern_vorne_und_event_extrahieren(name)
            if kern_vorne:
                treffer = kern_key(kern_vorne) in name_kern_index
        if not treffer:
            fehlend.append(eintrag)

    print(f"\n=== ERGEBNIS: {len(fehlend)} wirklich nicht zugeordnete Kanaele ===\n")
    for e in fehlend:
        print(json.dumps(e, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
