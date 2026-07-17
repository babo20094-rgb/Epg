#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_m3u.py

Ergänzt automatisch fehlende tvg-id in einer M3U-Playlist
anhand der Einträge aus sender.txt.

- Vorhandene tvg-id bleiben erhalten.
- Original-M3U bleibt unverändert.
- Es wird eine neue playlist_mit_tvgid.m3u erzeugt.
"""

from pathlib import Path
import re
import shutil
import sys

# ==========================================================
# DATEIEN
# ==========================================================

SENDER_DATEI = Path("sender.txt")
AUSGABE_DATEI = Path("playlist_mit_tvgid.m3u")

# ==========================================================
# M3U automatisch finden
# ==========================================================

m3u_dateien = list(Path(".").glob("*.m3u"))

if len(m3u_dateien) == 0:
    print("FEHLER: Keine .m3u-Datei gefunden.")
    sys.exit(1)

if len(m3u_dateien) > 1:
    print("FEHLER: Mehr als eine .m3u-Datei gefunden.")
    print("Bitte nur eine Playlist im Repository belassen.")
    sys.exit(1)

M3U_DATEI = m3u_dateien[0]
BACKUP_DATEI = Path(str(M3U_DATEI) + ".bak")

print("=" * 60)
print("update_m3u.py")
print("=" * 60)
print(f"M3U-Datei : {M3U_DATEI.name}")
print(f"Backup    : {BACKUP_DATEI.name}")
print(f"Ausgabe   : {AUSGABE_DATEI.name}")
print("=" * 60)

# Backup erstellen
shutil.copy2(M3U_DATEI, BACKUP_DATEI)
# ==========================================================
# HILFSFUNKTIONEN
# ==========================================================

def normalize(text: str) -> str:
    """
    Vereinheitlicht Sendernamen für Vergleiche.
    """

    text = text.upper()

    entfernen = [
        " UHD",
        " FHD",
        " HD",
        " SD",
        " 4K",
        " 8K",
        " HEVC"
    ]

    for wort in entfernen:
        text = text.replace(wort, "")

    text = text.replace("-", " ")
    text = text.replace("_", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def get_attribute(extinf: str, name: str) -> str:
    """
    Liest ein Attribut aus einer EXTINF-Zeile.
    """

    match = re.search(
        rf'{re.escape(name)}="([^"]*)"',
        extinf,
        flags=re.IGNORECASE
    )

    if match:
        return match.group(1)

    return ""


def set_attribute(extinf: str, name: str, value: str) -> str:
    """
    Erstellt oder ersetzt ein Attribut.
    """

    pattern = rf'{re.escape(name)}="[^"]*"'

    if re.search(pattern, extinf, flags=re.IGNORECASE):

        return re.sub(
            pattern,
            f'{name}="{value}"',
            extinf,
            count=1,
            flags=re.IGNORECASE
        )

    return extinf.replace(
        "#EXTINF:-1",
        f'#EXTINF:-1 {name}="{value}"',
        1
    )


def print_trenner():
    print("-" * 60)
  # ==========================================================
# sender.txt einlesen
# ==========================================================

def lade_sender():
    """
    Liest sender.txt und erstellt ein Wörterbuch mit
    verschiedenen Suchschlüsseln.
    """

    sender = {}

    if not SENDER_DATEI.exists():
        print(f"FEHLER: {SENDER_DATEI} wurde nicht gefunden.")
        sys.exit(1)

    print("Lese sender.txt ...")

    with open(SENDER_DATEI, "r", encoding="utf-8") as f:

        for zeile in f:

            zeile = zeile.strip()

            if not zeile:
                continue

            if zeile.startswith("#"):
                continue

            teile = [x.strip() for x in zeile.split("|")]

            if len(teile) < 2:
                continue

            land = teile[0]
            kanal = teile[1]

            tvgid = f"{land}|{kanal}"

            keys = set()

            # Original
            keys.add(normalize(kanal))

            # Varianten ohne Qualitätszusätze
            name = normalize(kanal)

            for suffix in (
                " HD",
                " FHD",
                " UHD",
                " SD",
                " HEVC",
                " 4K",
                " 8K",
            ):
                keys.add(normalize(name.replace(suffix, "")))

            # Varianten mit Land entfernen
            if "|" in tvgid:
                keys.add(normalize(tvgid.split("|", 1)[1]))

            # Alles speichern
            for key in keys:
                if key:
                    sender[key] = tvgid

    print(f"{len(sender)} Suchschlüssel geladen.")

    return sender


SENDER = lade_sender()

print_trenner()
# ==========================================================
# M3U einlesen
# ==========================================================

print("Lese M3U-Datei ...")

with open(M3U_DATEI, "r", encoding="utf-8", errors="ignore") as f:
    zeilen = f.readlines()

print(f"{len(zeilen)} Zeilen gelesen.")

print_trenner()

# ==========================================================
# Statistik
# ==========================================================

geaendert = 0
bereits_ok = 0
nicht_gefunden = 0

neue_zeilen = []

# ==========================================================
# Playlist verarbeiten
# ==========================================================

for zeile in zeilen:

    if not zeile.startswith("#EXTINF"):
        neue_zeilen.append(zeile)
        continue

    original = zeile

    tvgid = get_attribute(zeile, "tvg-id")
    tvgname = get_attribute(zeile, "tvg-name")

    # Sendername hinter dem Komma
    if "," in zeile:
        sendername = zeile.split(",", 1)[1].strip()
    else:
        sendername = ""

    kandidaten = []

    if tvgname:
        kandidaten.append(tvgname)

    if sendername:
        kandidaten.append(sendername)

    gefunden = False

    for kandidat in kandidaten:

        key = normalize(kandidat)

        if key in SENDER:

            gefunden = True

            if tvgid.strip() == "":

                neue_id = SENDER[key]

                zeile = set_attribute(
                    zeile,
                    "tvg-id",
                    neue_id
                )

                geaendert += 1

            else:

                bereits_ok += 1

            break

    if not gefunden:
        nicht_gefunden += 1

    neue_zeilen.append(zeile)

print("Analyse abgeschlossen.")
print_trenner()
# ==========================================================
# Neue M3U schreiben
# ==========================================================

print("Speichere neue Playlist...")

with open(
    AUSGABE_DATEI,
    "w",
    encoding="utf-8",
    newline=""
) as f:

    f.writelines(neue_zeilen)

print("Fertig.")
print_trenner()

# ==========================================================
# Statistik
# ==========================================================

gesamt = geaendert + bereits_ok + nicht_gefunden

print("")
print("=" * 60)
print("update_m3u.py abgeschlossen")
print("=" * 60)

print(f"Original-M3U : {M3U_DATEI.name}")
print(f"Backup       : {BACKUP_DATEI.name}")
print(f"Neue M3U     : {AUSGABE_DATEI.name}")

print("")

print(f"Sender geprüft          : {gesamt}")
print(f"Neue tvg-id ergänzt     : {geaendert}")
print(f"Bereits vorhanden       : {bereits_ok}")
print(f"Nicht zugeordnet        : {nicht_gefunden}")

print("")
print("Die Original-M3U wurde NICHT verändert.")
print("Die neue Playlist enthält die ergänzten tvg-id.")
print("=" * 60)
