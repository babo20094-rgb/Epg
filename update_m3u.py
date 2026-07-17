#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_m3u.py

Lädt automatisch die IPTV-M3U über das GitHub-Secret
IPTV_M3U_URL herunter und ergänzt fehlende tvg-id
anhand der sender.txt.

Erstellt:
    playlist_mit_tvgid.m3u

Die Original-M3U wird nur temporär gespeichert.
"""

from pathlib import Path
import os
import re
import sys
import requests

# ==========================================================
# DATEIEN
# ==========================================================

SENDER_DATEI = Path("sender.txt")
ORIGINAL_M3U = Path("original_playlist.m3u")
AUSGABE_M3U = Path("playlist_mit_tvgid.m3u")

# ==========================================================
# GITHUB SECRET
# ==========================================================

M3U_URL = os.getenv("IPTV_M3U_URL")

if not M3U_URL:
    sys.exit(
        "FEHLER: GitHub Secret 'IPTV_M3U_URL' fehlt."
    )

print("=" * 60)
print("UPDATE M3U")
print("=" * 60)
print("GitHub Secret gefunden.")
print("=" * 60)

# ==========================================================
# DOWNLOAD
# ==========================================================

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

except requests.exceptions.RequestException as e:
    sys.exit(f"FEHLER beim Download:\n{e}")

playlist = response.text

if "#EXTM3U" not in playlist:
    sys.exit("FEHLER: Ungültige M3U erhalten.")

ORIGINAL_M3U.write_text(
    playlist,
    encoding="utf-8",
    newline="\n"
)

print("✓ Download erfolgreich")
# ==========================================================
# sender.txt EINLESEN
# ==========================================================

print("Lese sender.txt...")

if not SENDER_DATEI.exists():
    sys.exit(f"FEHLER: Datei '{SENDER_DATEI}' wurde nicht gefunden.")

sender_mapping = {}
anzahl_eintraege = 0

with SENDER_DATEI.open("r", encoding="utf-8") as f:

    for zeile_nr, zeile in enumerate(f, start=1):

        zeile = zeile.strip()

        # Leere Zeilen überspringen
        if not zeile:
            continue

        # Kommentare überspringen
        if zeile.startswith("#"):
            continue

        teile = [teil.strip() for teil in zeile.split("|")]

        # Mindestens Land + Sendername erforderlich
        if len(teile) < 2:
            continue

        land = teile[0]
        sender = teile[1]

        if not land or not sender:
            continue

        tvg_id = f"{land}|{sender}"

        # Doppelte Einträge vermeiden
        key = sender.casefold()

        if key not in sender_mapping:
            sender_mapping[key] = tvg_id
            anzahl_eintraege += 1

print(f"✓ {anzahl_eintraege} Sender aus sender.txt geladen.")
print("=" * 60)
# ==========================================================
# M3U EINLESEN
# ==========================================================

print("Lese heruntergeladene Playlist...")

try:
    with ORIGINAL_M3U.open("r", encoding="utf-8", errors="ignore") as f:
        m3u_zeilen = f.readlines()

except Exception as e:
    sys.exit(f"FEHLER beim Lesen der Playlist:\n{e}")

print(f"✓ {len(m3u_zeilen)} Zeilen gelesen.")

# ==========================================================
# REGEX
# ==========================================================

regex_tvg_id = re.compile(r'tvg-id="([^"]*)"')
regex_tvg_name = re.compile(r'tvg-name="([^"]*)"')

# ==========================================================
# AUSGABE VORBEREITEN
# ==========================================================

neue_playlist = []

geaendert = 0
unveraendert = 0
nicht_gefunden = 0

print("=" * 60)
print("Verarbeite Playlist...")
print("=" * 60)

i = 0

while i < len(m3u_zeilen):

    zeile = m3u_zeilen[i]

    # Keine EXTINF-Zeile -> unverändert übernehmen
    if not zeile.startswith("#EXTINF"):
        neue_playlist.append(zeile)
        i += 1
        continue

    extinf = zeile.rstrip("\n")

    # Stream-URL übernehmen
    stream_url = ""
    if i + 1 < len(m3u_zeilen):
        stream_url = m3u_zeilen[i + 1]

    # Anzeigename hinter dem Komma
    sendername = ""
    if "," in extinf:
        sendername = extinf.rsplit(",", 1)[1].strip()

    # tvg-id lesen
    vorhandene_tvgid = ""
    match = regex_tvg_id.search(extinf)
    if match:
        vorhandene_tvgid = match.group(1).strip()

    # tvg-name lesen
    tvg_name = ""
    match = regex_tvg_name.search(extinf)
    if match:
        tvg_name = match.group(1).strip()

    # Suchname bestimmen
    if tvg_name:
        suchname = tvg_name.casefold()
    else:
        suchname = sendername.casefold()
            # ==========================================================
    # tvg-id ERMITTELN
    # ==========================================================

    neue_tvgid = sender_mapping.get(suchname)

    # Fallback: Anzeigename verwenden
    if not neue_tvgid and sendername:
        neue_tvgid = sender_mapping.get(sendername.casefold())

    # Bereits vorhandene tvg-id -> unverändert übernehmen
    if vorhandene_tvgid:

        neue_playlist.append(extinf + "\n")
        neue_playlist.append(stream_url)

        unveraendert += 1
        i += 2
        continue

    # Sender gefunden -> tvg-id ergänzen
    if neue_tvgid:

        if 'tvg-id=""' in extinf:

            extinf = extinf.replace(
                'tvg-id=""',
                f'tvg-id="{neue_tvgid}"'
            )

        elif 'tvg-id=' not in extinf:

            extinf = extinf.replace(
                "#EXTINF:-1",
                f'#EXTINF:-1 tvg-id="{neue_tvgid}"',
                1
            )

        neue_playlist.append(extinf + "\n")
        neue_playlist.append(stream_url)

        geaendert += 1

    else:

        neue_playlist.append(extinf + "\n")
        neue_playlist.append(stream_url)

        nicht_gefunden += 1

        print(f"[NICHT GEFUNDEN] {sendername}")

    i += 2
    # ==========================================================
# PLAYLIST SPEICHERN
# ==========================================================

print("=" * 60)
print("Speichere neue Playlist...")

try:
    with AUSGABE_M3U.open(
        "w",
        encoding="utf-8",
        newline="\n"
    ) as f:

        f.writelines(neue_playlist)

except Exception as e:
    sys.exit(f"FEHLER beim Schreiben der Playlist:\n{e}")

print(f"✓ Playlist gespeichert: {AUSGABE_M3U}")

# ==========================================================
# STATISTIK
# ==========================================================

print("=" * 60)
print("FERTIG")
print("=" * 60)

print(f"Sender aus sender.txt : {anzahl_eintraege}")
print(f"Playlist-Einträge     : {anzahl_sender}")
print(f"tvg-id ergänzt        : {geaendert}")
print(f"Bereits vorhanden     : {unveraendert}")
print(f"Nicht gefunden        : {nicht_gefunden}")

print("=" * 60)

if nicht_gefunden > 0:
    print("Hinweis: Einige Sender wurden in sender.txt nicht gefunden.")

print("update_m3u.py erfolgreich abgeschlossen.")
