"""Einmaliges Diagnose-Skript: vergleicht die aktuelle IPTV-Playlist
(Umgebungsvariable PROVIDER) mit den Kanal-IDs, die generate_epg.py aus
sender.txt erzeugen wuerde, und listet Playlist-Kanaele auf, fuer die
KEINE passende Kanal-ID existiert (= im EPG-Player nicht automatisch
zuordenbar).

Fuehrt dazu generate_epg.py NUR bis zu dem Punkt aus, an dem alle
<channel>-Bloecke feststehen (inkl. Live-Playlist-Abgleich fuer NAME:-
Sender) - die anschliessenden, deutlich aufwendigeren Programmdaten-
Abrufe pro Quelle werden nicht ausgefuehrt, da sie fuer diesen Vergleich
irrelevant sind.

Nur fuer manuelle Diagnose per workflow_dispatch gedacht, kein Teil des
regulaeren EPG-Erzeugungslaufs.
"""
import os
import sys

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)

with open(os.path.join(REPO_ROOT, "generate_epg.py"), "r", encoding="utf-8") as f:
    quelltext = f.read()

marker = "# DYN LEERZEITEN"
idx = quelltext.index(marker)
teilquelltext = quelltext[:idx]

namensraum = {"__name__": "__main__", "__file__": os.path.join(REPO_ROOT, "generate_epg.py")}
exec(compile(teilquelltext, "generate_epg.py (gekuerzt)", "exec"), namensraum)

sender_daten = namensraum["sender_daten"]
kanal_id_varianten = namensraum["kanal_id_varianten"]

kanal_ids = set()
for daten in sender_daten:
    for kanal_id in kanal_id_varianten(daten["kanal"]):
        kanal_ids.add(kanal_id)

print(f"Generierte Kanal-IDs: {len(kanal_ids)}")

m3u_url = os.environ.get("PROVIDER")
if not m3u_url:
    raise SystemExit("Fehler: Umgebungsvariable PROVIDER ist nicht gesetzt.")

antwort = requests.get(m3u_url, timeout=60)
antwort.raise_for_status()
playlist_text = antwort.text

namen = []
for zeile in playlist_text.splitlines():
    zeile = zeile.strip()
    if not zeile.startswith("#EXTINF") or "," not in zeile:
        continue
    letztes_anfuehrungszeichen = zeile.rfind('"')
    such_start = letztes_anfuehrungszeichen if letztes_anfuehrungszeichen != -1 else 0
    komma_pos = zeile.find(",", such_start)
    name = (zeile[komma_pos + 1:] if komma_pos != -1 else zeile.rsplit(",", 1)[-1]).strip()
    namen.append(name)

print(f"Playlist-Kanaele: {len(namen)}")

fehlend = [n for n in namen if n not in kanal_ids]
print(f"Nicht zugeordnet: {len(fehlend)}")
for name in fehlend:
    print(repr(name))
