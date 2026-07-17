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
# ==========================================================
# sender.txt EINLESEN
# ==========================================================

print("Lese sender.txt...")

if not SENDER_DATEI.exists():
    sys.exit(f"FEHLER: {SENDER_DATEI} wurde nicht gefunden.")

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

        teile = [t.strip() for t in zeile.split("|")]

        # Mindestens Land + Sendername erforderlich
        if len(teile) < 2:
            continue

        land = teile[0]
        sender = teile[1]

        if not land or not sender:
            continue

        # tvg-id erzeugen
        tvg_id = f"{land}|{sender}"

        #
        # ==========================================================
# M3U EINLESEN
# ==========================================================

print("Analysiere IPTV-Playlist...")

try:
    with ORIGINAL_M3U.open("r", encoding="utf-8", errors="ignore") as f:
        m3u_zeilen = f.readlines()

except Exception as e:
    sys.exit(f"FEHLER beim Lesen der Playlist: {e}")

print(f"✓ {len(m3u_zeilen)} Zeilen gelesen.")

# ==========================================================
# REGEX
# ==========================================================

regex_tvg_id = re.compile(r'tvg-id="([^"]*)"')
regex_tvg_name = re.compile(r'tvg-name="([^"]*)"')

# ==========================================================
# AUSGABE
# ==========================================================

neue_playlist = []

geaendert = 0
unveraendert = 0
nicht_gefunden = 0

print("=" * 60)
print("Prüfe tvg-id Einträge...")
print("=" * 60)

i = 0

while i < len(m3u_zeilen):

    zeile = m3u_zeilen[i]

    if not zeile.startswith("#EXTINF"):
        neue_playlist.append(zeile)
        i += 1
        continue

    extinf = zeile.rstrip("\n")

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

        neue_tvgid = sender_mapping.get(
            sendername.casefold()
        )

    # Bereits vorhandene tvg-id -> nichts ändern
    if vorhandene_tvgid:

        neue_playlist.append(extinf + "\n")
        neue_playlist.append(stream_url)

        unveraendert += 1
        i += 2
        continue

    # Sender gefunden
    if neue_tvgid:

        # tvg-id existiert aber ist leer
        if 'tvg-id=""' in extinf:

            extinf = extinf.replace(
                'tvg-id=""',
                f'tvg-id="{neue_tvgid}"'
            )

        # tvg-id fehlt komplett
        elif 'tvg-id=' not in extinf:

            if "#EXTINF:-1 " in extinf:

                extinf = extinf.replace(
                    "#EXTINF:-1 ",
                    f'#EXTINF:-1 tvg-id="{neue_tvgid}" ',
                    1
                )

            else:

                extinf = extinf.replace(
                    "#EXTINF:-1",
                    f'#EXTINF:-1 tvg-id="{neue_tvgid}"',
                    1
                )

        neue_playlist.append(extinf + "\n")
        neue_playlist.append(stream_url)

        geaendert += 1

    # Sender nicht gefunden
    else:

        neue_playlist.append(extinf + "\n")
        neue_playlist.append(stream_url)

        nicht_gefunden += 1

        print(f"[NICHT GEFUNDEN] {sendername}")

    i += 2
        continue

    
    # ==========================================================
# NEUE PLAYLIST SPEICHERN
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
    sys.exit(f"FEHLER beim Schreiben der Playlist: {e}")

print(f"✓ Neue Playlist gespeichert: {AUSGABE_M3U}")

print("=" * 60)
print("STATISTIK")
print("=" * 60)

print(f"Sender aus sender.txt : {anzahl_eintraege}")
print(f"Sender in Playlist    : {anzahl_sender}")
print(f"tvg-id ergänzt        : {geaendert}")
print(f"Bereits vorhanden     : {unveraendert}")
print(f"Nicht gefunden        : {nicht_gefunden}")

print("=" * 60)
print("update_m3u.py erfolgreich beendet.")
