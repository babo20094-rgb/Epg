#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import os
import sys
import re
import requests

# ==========================================================
# DATEIEN
# ==========================================================

SENDER_DATEI = Path("sender.txt")
AUSGABE_M3U = Path("playlist_mit_tvgid.m3u")

# ==========================================================
# GITHUB SECRET
# ==========================================================

M3U_URL = os.getenv("IPTV_M3U_URL")

if not M3U_URL:
    sys.exit("FEHLER: GitHub Secret 'IPTV_M3U_URL' fehlt.")

print("=" * 60)
print("UPDATE M3U")
print("=" * 60)
print("Lade IPTV-Playlist herunter...")

try:
    response = requests.get(
        M3U_URL,
        timeout=60,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

except requests.RequestException as e:
    sys.exit(f"Download fehlgeschlagen:\n{e}")

playlist = response.text

if "#EXTM3U" not in playlist:
    sys.exit("Ungültige M3U-Datei.")

m3u_zeilen = playlist.splitlines(keepends=True)

print(f"✓ Playlist geladen ({playlist.count('#EXTINF')} Sender)")
print("=" * 60)
# ==========================================================
# sender.txt einlesen
# ==========================================================

print("Lese sender.txt...")

if not SENDER_DATEI.exists():
    sys.exit(f"Datei '{SENDER_DATEI}' nicht gefunden.")

sender_mapping = {}
anzahl_sender = 0

with SENDER_DATEI.open("r", encoding="utf-8") as f:

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
        sender = teile[1]

        if not land or not sender:
            continue

        tvg_id = f"{land}|{sender}"

        sender_mapping[sender.casefold()] = tvg_id

        anzahl_sender += 1

print(f"✓ {anzahl_sender} Sender geladen")
print("=" * 60)

# ==========================================================
# REGEX vorbereiten
# ==========================================================

regex_tvgid = re.compile(r'tvg-id="([^"]*)"')
regex_tvgname = re.compile(r'tvg-name="([^"]*)"')

neue_playlist = []

geaendert = 0
vorhanden = 0
nicht_gefunden = 0
# ==========================================================
# Playlist verarbeiten
# ==========================================================

print("Verarbeite Playlist...")

i = 0

while i < len(m3u_zeilen):

    zeile = m3u_zeilen[i]

    if not zeile.startswith("#EXTINF"):
        neue_playlist.append(zeile)
        i += 1
        continue

    extinf = zeile.rstrip("\n")

    stream = ""

    if i + 1 < len(m3u_zeilen):
        stream = m3u_zeilen[i + 1]

    sendername = ""

    if "," in extinf:
        sendername = extinf.rsplit(",", 1)[1].strip()

    tvg_name = ""

    match = regex_tvgname.search(extinf)

    if match:
        tvg_name = match.group(1).strip()

    vorhandene_tvgid = ""

    match = regex_tvgid.search(extinf)

    if match:
        vorhandene_tvgid = match.group(1).strip()

    suchname = tvg_name if tvg_name else sendername

    neue_tvgid = sender_mapping.get(suchname.casefold())

    if vorhandene_tvgid:

        neue_playlist.append(extinf + "\n")
        neue_playlist.append(stream)

        vorhanden += 1
        i += 2
        continue

    if neue_tvgid:

        if 'tvg-id=""' in extinf:

            extinf = extinf.replace(
                'tvg-id=""',
                f'tvg-id="{neue_tvgid}"'
            )

        elif "tvg-id=" not in extinf:

            extinf = extinf.replace(
                "#EXTINF:-1",
                f'#EXTINF:-1 tvg-id="{neue_tvgid}"',
                1
            )

        geaendert += 1

    else:

        nicht_gefunden += 1

    neue_playlist.append(extinf + "\n")
    neue_playlist.append(stream)

    i += 2
    # ==========================================================
# Playlist speichern
# ==========================================================

print("=" * 60)
print("Speichere Playlist...")

try:

    with AUSGABE_M3U.open(
        "w",
        encoding="utf-8",
        newline="\n"
    ) as f:

        f.writelines(neue_playlist)

except Exception as e:
    sys.exit(f"Fehler beim Schreiben:\n{e}")

print(f"✓ {AUSGABE_M3U} gespeichert")

# ==========================================================
# Statistik
# ==========================================================

print("=" * 60)
print("FERTIG")
print("=" * 60)

print(f"Sender aus sender.txt : {anzahl_sender}")
print(f"Playlist-Einträge     : {playlist.count('#EXTINF')}")
print(f"tvg-id ergänzt        : {geaendert}")
print(f"Bereits vorhanden     : {vorhanden}")
print(f"Nicht gefunden        : {nicht_gefunden}")

print("=" * 60)

if nicht_gefunden:
    print("Hinweis: Einige Sender wurden in sender.txt nicht gefunden.")

print("update_m3u.py erfolgreich abgeschlossen.")
