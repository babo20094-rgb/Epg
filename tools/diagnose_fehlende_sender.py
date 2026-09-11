"""Einmaliges Diagnose-Skript: vergleicht die aktuelle IPTV-Playlist
(Umgebungsvariable PROVIDER) mit den Kanal-IDs, die generate_epg.py aus
sender.txt erzeugen wuerde, und listet Playlist-Kanaele auf, fuer die
KEINE passende Kanal-ID existiert (= im EPG-Player nicht automatisch
zuordenbar).

Vergleicht gezielt gegen das tvg-name="..."-Attribut der #EXTINF-Zeile
(nicht den Anzeigenamen nach dem Komma) - genau das ist es, worauf
generate_epg.py die eigene <channel id> abstimmt (siehe Kommentar dort:
"So wie er in der Playlist als tvg-name steht"). Anzeigename und
tvg-name koennen sich in Gross-/Kleinschreibung unterscheiden, ein
Abgleich gegen den Anzeigenamen wuerde daher viele falsch-positive
Treffer liefern. Fehlt tvg-name in der Zeile, wird ersatzweise der
Anzeigename verwendet.

Fuehrt dazu generate_epg.py NUR bis zu dem Punkt aus, an dem alle
<channel>-Bloecke feststehen (inkl. Live-Playlist-Abgleich fuer NAME:-
Sender, den 20 fest kodierten DYN-PPV-Kanaelen und reinen Logo-
Eintraegen) - die anschliessenden, deutlich aufwendigeren Programmdaten-
Abrufe pro Quelle werden nicht ausgefuehrt, da sie fuer diesen Vergleich
irrelevant sind.

Nur fuer manuelle Diagnose per workflow_dispatch gedacht, kein Teil des
regulaeren EPG-Erzeugungslaufs.
"""
import os
import re
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
logo_only_channels = namensraum["logo_only_channels"]
dyn_ppv_kanal_ids = namensraum["dyn_ppv_kanal_ids"]
DYN_PPV_ANZAHL = namensraum["DYN_PPV_ANZAHL"]

kanal_ids = set()

for daten in sender_daten:
    for kanal_id in kanal_id_varianten(daten["kanal"]):
        kanal_ids.add(kanal_id)

for daten in logo_only_channels:
    kanal_ids.add(daten["kanal"])
    if "voller_name" in daten:
        for alias in (daten.get("aliase") or [daten["voller_name"]]):
            kanal_ids.add(alias)

for i in range(1, DYN_PPV_ANZAHL + 1):
    for kanal_id in dyn_ppv_kanal_ids(i):
        kanal_ids.add(kanal_id)

print(f"Generierte Kanal-IDs: {len(kanal_ids)}")

m3u_url = os.environ.get("PROVIDER")
if not m3u_url:
    raise SystemExit("Fehler: Umgebungsvariable PROVIDER ist nicht gesetzt.")

antwort = requests.get(m3u_url, timeout=120)
antwort.raise_for_status()
playlist_text = antwort.text

TVG_NAME_MUSTER = re.compile(r'tvg-name="([^"]*)"')

namen = []
for zeile in playlist_text.splitlines():
    zeile = zeile.strip()
    if not zeile.startswith("#EXTINF") or "," not in zeile:
        continue

    tvg_name_treffer = TVG_NAME_MUSTER.search(zeile)
    if tvg_name_treffer and tvg_name_treffer.group(1).strip():
        namen.append(tvg_name_treffer.group(1).strip())
        continue

    letztes_anfuehrungszeichen = zeile.rfind('"')
    such_start = letztes_anfuehrungszeichen if letztes_anfuehrungszeichen != -1 else 0
    komma_pos = zeile.find(",", such_start)
    name = (zeile[komma_pos + 1:] if komma_pos != -1 else zeile.rsplit(",", 1)[-1]).strip()
    namen.append(name)

print(f"Playlist-Kanaele: {len(namen)}")

fehlend = [n for n in namen if n not in kanal_ids]
print(f"Nicht zugeordnet: {len(fehlend)}")
for name in sorted(set(fehlend)):
    print(repr(name))
