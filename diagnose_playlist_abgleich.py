"""TEMPORAERES Diagnose-Skript (siehe docs/HISTORIE.md, Abschnitt
"22.09.2026: Live-Playlist-Abgleich per Xtream-API + zwei echte Bugs
gefunden/behoben, ein dritter noch offen", Bug 3).

Fuehrt gezielt nur den sender.txt-Parsing-Teil und den Live-
Kanalabgleich (m3u_playlist_abgleichen()) von generate_epg.py aus
(per exec() markerbasiert aus generate_epg.py extrahiert, damit keine
Logik dupliziert wird und Code-Drift ausgeschlossen ist), baut daraus
die Menge aller generierten <channel>-IDs und vergleicht sie gegen die
tatsaechlichen Playlist-Kanalnamen (aus derselben ueber PROVIDER
geladenen M3U-Datei). Ziel: herausfinden, warum ca. 19 "24/7 X"-NAME:-
Sender trotz korrektem sender.txt-Eintrag nicht im finalen XML
auftauchen.

Nach Abschluss der Diagnose wird dieses Skript (und der zugehoerige
Workflow .github/workflows/diagnose_playlist.yml) wieder aus dem Repo
entfernt - rein temporaeres Hilfsmittel, kein Teil des normalen
EPG-Generierungslaufs.
"""

import os
import re
import sys

with open("generate_epg.py", encoding="utf-8") as f:
    quelltext = f.readlines()


def zeilen_index(such_text, ab=0):
    for i in range(ab, len(quelltext)):
        if such_text in quelltext[i]:
            return i
    raise RuntimeError(f"Marker nicht gefunden: {such_text!r}")


ende_parsing = zeilen_index('kanal_index = {d["kanal"]: d for d in sender_daten}')
start_channel_schreiben = zeilen_index("Blöcke schreiben (sender.txt, mit ggf")
ende_channel_schreiben = zeilen_index("# DYN LEERZEITEN")

print(f"Block 1 (Parsing): Zeile 1 bis {ende_parsing}")
print(f"Block 2+3 (Live-Abgleich + Channel-Schreiben): Zeile {ende_parsing} bis {ende_channel_schreiben}")

namespace = {"__name__": "__diagnose__"}

block1 = "".join(quelltext[:ende_parsing])
exec(compile(block1, "generate_epg.py::block1", "exec"), namespace)
print("Block 1 fertig. sender_daten:", len(namespace["sender_daten"]))

block23 = "".join(quelltext[ende_parsing:ende_channel_schreiben])
exec(compile(block23, "generate_epg.py::block23", "exec"), namespace)
print("Block 2+3 fertig. xml_teile Eintraege:", len(namespace["xml_teile"]))

# Alle geschriebenen <channel id="..."> aus xml_teile extrahieren.
xml_text = "".join(namespace["xml_teile"])
geschriebene_ids = set(re.findall(r'<channel id="((?:[^"\\]|\\.)*)"', xml_text))
print("Anzahl eindeutiger <channel id> aus Block 2+3:", len(geschriebene_ids))

# Kontroll-Check fuer die bekannten Problem-Sender.
verdaechtige = [
    "24/7 AL PACINO", "24/7 LAW AND ORDER", "24/7 KING OF THE HILL",
    "24/7 BONANZA", "24/7 BACK TO THE FUTURE", "24/7 ROCKY",
]
print("\n--- Kontrolle bekannter Problem-Sender ---")
for v in verdaechtige:
    treffer = [
        d for d in namespace["sender_daten"]
        if d.get("live_playlist_kern") and d.get("sender", "").strip().upper() == v
    ]
    if not treffer:
        print(f"{v}: KEIN live_playlist_kern-Eintrag gefunden (unerwartet)")
        continue
    for daten in treffer:
        print(f"{v}: kanal='{daten['kanal']}' | in geschriebenen IDs: {daten['kanal'] in geschriebene_ids}")

# Playlist direkt ueber dieselbe M3U-Quelle (PROVIDER) laden und
# Kanalnamen extrahieren, um die Diagnose auch fuer ALLE Sender (nicht
# nur die Verdaechtigen) auszuwerten.
provider_url = os.environ.get("PROVIDER")
if provider_url:
    try:
        gepuffert = namespace["_m3u_playlist_roh_text_laden"](provider_url)
        playlist_namen = set()
        for zeile in gepuffert.splitlines():
            zeile = zeile.strip()
            if not zeile.startswith("#EXTINF") or "," not in zeile:
                continue
            letztes_anfuehrungszeichen = zeile.rfind('"')
            such_start = letztes_anfuehrungszeichen if letztes_anfuehrungszeichen != -1 else 0
            komma_pos = zeile.find(",", such_start)
            voller_name = (zeile[komma_pos + 1:] if komma_pos != -1 else zeile.rsplit(",", 1)[-1]).strip()
            if voller_name:
                playlist_namen.add(voller_name)

        print(f"\nPlaylist-Kanaele (M3U, roh): {len(playlist_namen)}")
        fehlend = sorted(playlist_namen - geschriebene_ids)
        print(f"In Playlist, aber NICHT als <channel id> gefunden: {len(fehlend)}")
        for n in fehlend[:100]:
            print("  -", n)
        if len(fehlend) > 100:
            print(f"  ... und {len(fehlend) - 100} weitere (siehe vollstaendige Liste oben abgeschnitten)")
    except Exception as e:
        print(f"\nM3U-Playlist-Abgleich fehlgeschlagen: {type(e).__name__}: {e}")
else:
    print("\nKein PROVIDER-Secret gesetzt - Playlist-Vollabgleich uebersprungen.")

print("\nDiagnose abgeschlossen.")
