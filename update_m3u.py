#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_m3u.py

Lädt automatisch die IPTV-Playlist über das GitHub-Secret
IPTV_M3U_URL herunter und ergänzt fehlende tvg-id-Einträge
anhand der sender.txt.

Ausgabe:
    playlist_mit_tvgid.m3u

Die Original-Playlist wird nicht veröffentlicht.
"""

from pathlib import Path
import os
import sys
import re
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
        "FEHLER: GitHub-Secret 'IPTV_M3U_URL' wurde nicht gefunden."
    )

print("=" * 60)
print("IPTV PLAYLIST DOWNLOAD")
print("=" * 60)
print("URL wurde erfolgreich aus GitHub Secrets geladen.")
print("=" * 60)
# ==========================================================
# PLAYLIST HERUNTERLADEN
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

except requests.exceptions.Timeout:
    sys.exit("FEHLER: Zeitüberschreitung beim Download der IPTV-Playlist.")

except requests.exceptions.ConnectionError:
    sys.exit("FEHLER: Verbindung zum IPTV-Server fehlgeschlagen.")

except requests.exceptions.RequestException as e:
    sys.exit(f"FEHLER beim Download: {e}")

if response.status_code != 200:
    sys.exit(
        f"FEHLER: Server antwortete mit HTTP {response.status_code}."
    )

playlist = response.text

if not playlist.strip():
    sys.exit("FEHLER: Die heruntergeladene Playlist ist leer.")

if "#EXTM3U" not in playlist:
    sys.exit("FEHLER: Keine gültige M3U-Playlist erhalten.")

ORIGINAL_M3U.write_text(
    playlist,
    encoding="utf-8",
    newline="\n"
)

print("✓ Playlist erfolgreich heruntergeladen.")
print(f"✓ Gespeichert als: {ORIGINAL_M3U}")

anzahl_sender = playlist.count("#EXTINF")

print(f"✓ Gefundene Sender: {anzahl_sender}")

if anzahl_sender == 0:
    sys.exit("FEHLER: Keine Sender in der Playlist gefunden.")

print("=" * 60)
