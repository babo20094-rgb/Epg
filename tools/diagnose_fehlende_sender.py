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
GROUP_TITLE_MUSTER = re.compile(r'group-title="([^"]*)"')

namen = []
for zeile in playlist_text.splitlines():
    zeile = zeile.strip()
    if not zeile.startswith("#EXTINF") or "," not in zeile:
        continue

    gruppe_treffer = GROUP_TITLE_MUSTER.search(zeile)
    gruppe = gruppe_treffer.group(1).strip() if gruppe_treffer else ""

    tvg_name_treffer = TVG_NAME_MUSTER.search(zeile)
    if tvg_name_treffer and tvg_name_treffer.group(1).strip():
        namen.append((tvg_name_treffer.group(1).strip(), gruppe))
        continue

    letztes_anfuehrungszeichen = zeile.rfind('"')
    such_start = letztes_anfuehrungszeichen if letztes_anfuehrungszeichen != -1 else 0
    komma_pos = zeile.find(",", such_start)
    name = (zeile[komma_pos + 1:] if komma_pos != -1 else zeile.rsplit(",", 1)[-1]).strip()
    namen.append((name, gruppe))

print(f"Playlist-Kanaele: {len(namen)}")

fehlend = [(n, g) for n, g in namen if n not in kanal_ids]
print(f"Nicht zugeordnet: {len(fehlend)}")

# VOD-/Serien-Gruppen (Filme, Serien, Kids, 24/7-Binge-Kanaele) machen
# den Grossteil der 1,3+ Mio. Playlist-Zeilen aus und sind fuer die
# EPG-Zuordnung irrelevant (VOD hat kein XMLTV-EPG). Nach Gruppe
# aggregieren, damit echte LIVE-TV-Gruppen mit fehlender Zuordnung
# sofort auffallen, statt in der VOD-Masse unterzugehen.
gruppen_zaehler = {}
for _, g in fehlend:
    gruppen_zaehler[g] = gruppen_zaehler.get(g, 0) + 1

print(f"\n--- Fehlende Zuordnungen nach group-title (Top 80 nach Anzahl) ---")
for gruppe, anzahl in sorted(gruppen_zaehler.items(), key=lambda x: -x[1])[:80]:
    print(f"{anzahl:6d}  {gruppe!r}")

# Live-TV-Gruppen: direkt vom Nutzer aus TiviMates "Gruppen verwalten"-
# Bildschirm uebernommen (nur die dort AKTIVIERTEN/blauen Gruppen -
# die deaktivierten/weissen sind VOD/Serien/24-7-Binge und zaehlen
# NICHT zu den ~18.957 echten Live-Sendern). Prefix-Abgleich (nicht
# exakt), da TiviMate an manche Gruppennamen zusaetzliche Qualitaets-
# Badges (HD/4K/PPV/...) anhaengt, die hier nicht 1:1 nachgebaut werden
# koennen - ein Praefix-Treffer reicht, um die Gruppe zu identifizieren.
LIVE_GRUPPEN_PREFIXE = [p.upper() for p in (
    "DE| ALLGEMEIN", "DE| GERMANY", "DE| MAGENTA SPORT", "DE| MAGENTA",
    "DE| MYTEAM SPORT", "DE| DYN SPORT", "DE| SKY GO WOW",
    "DE| SKY BUNDESLIGA", "DE| WOW SKY SPORT", "DE| JOYN",
    "DE| KINDER SENDER", "DE| SKY GO DOKU", "DE| PRIME TV",
    "DE| VODAFONE GO", "DE| DAZN/SKY SPORT", "DE| DAZN", "DE| LEAGUES FOOTBALL",
    "DE| SPORT DEUTSCHLAND", "DE| DISCOVERY+", "DE| SKY GO FILME",
    "DE| SKY MAX", "DE| SKY SELECT", "DE| PREMIUM PLAY", "DE| PLEX TV",
    "DE| MAGENTA FILME", "DE| MYSPORT", "DE| RTL+", "DE| BUNDESLIGA REPLAY",
    "DE| SKY GO SPORT", "DE| SKY GO", "DE| SOCCER", "DE| DISNEY+",
    "US| ENTERTAINMENT", "US| NEWS NETWORK", "US| SPECTRUM NETWORK",
    "US| KIDS NETWORK", "US| SPORTS NETWORK", "US| MAX ESPN",
    "US| MOVIES NETWORK", "US| PRIME", "US| DIREC TV", "US| TUBI",
    "US| FIFA+", "US| PARAMOUNT+ PPV VIP", "US| PARAMOUNT+ 10",
    "US| PEACOCK PPV", "US| B1G+", "US| BTN+", "US| NBA NETWORK",
    "US| NBA PACKAGE", "US| NFL NETWORK HULU", "US| NFL PACKAGE",
    "US| MLB PACKAGE", "US| WNBA PACKAGE", "US| MILB TV",
    "US| NCAAF PACKAGE", "US| FLO COLLEGE", "US| NHL PACKAGE",
    "US| FLO RACING", "US| VIAPLAY NHL", "US| VICTORY+", "US| FITE TV",
    "US| STAN", "US| DIRTVISION", "US| MLS NETWORK", "US| MLS PPV VIP",
    "US| NFHS", "US| MLS PPV 50", "US| NETFLIX PPV 12", "US| MAX PPV 40",
    "US| B/R MAX SPORTS", "US| FLO NETWORK", "US| ABC NETWORK",
    "US| CBS NETWORK", "US| FOX NETWORK", "US| NBC NETWORK",
    "US| PBS NETWORK", "US| CW/MY NETWORK", "US| TELEMUNDO NETWORK",
    "US| CINEMANIA HOLLYWOOD", "US| CINEMANIA TV SHOWS",
    "US| TENNIS CHANNEL PLUS", "US| PEACOCK NETWORK", "US| TENNIS PPV",
    "US| HBO MAX NETWORK", "US| HULU NETWORK", "US| DISNEY+ NETWORK",
    "US| ESPN PLUS", "US| ESPN+ PPV VIP", "US| ESPN PLAY",
    "US| VIX+ DEPORTES", "US| SOCCER", "US| DAZN", "US| NETFLIX ON AIR",
    "US| PLUTO TV",
    "NA| PPV & LIVE EVENTS", "NA| HOCKEY LEAGUE",
    "UK| GENERAL", "UK| ENTERTAINMENT", "UK| NEWS", "UK| KIDS",
    "UK| DOCUMENTARY", "UK| MUSIC", "UK| MC VIDEO", "UK| MOVIES 4K",
    "UK| SPORTS", "UK| SKY SPORT+ VIP", "UK| SOCCER REPLAY",
    "UK| NATIONAL LEAGUE", "UK| UEFA REPLAY", "UK| WORLD SPORTS",
    "UK| DAZN", "UK| AMAZON PRIME",
    "CA| OHL",
    "RS| SERBIA", "BH| BOSNIA", "HR| CROATIA", "MK| MACEDONIA",
    "SL| SLOVENIA", "CG| MONTENEGRO",
    "EXYU| SPORTSKI KANALI", "EXYU| PINK MEDIA", "EXYU| FILMSKI KANALI",
    "EXYU| MUZICKI KANALI", "EXYU| DOKUMENTARNI", "EXYU| DJECIJI KANALI",
    "EXYU| NON STOP", "EXYU| BALKAN SKY", "EXYU| SKY KIDS",
    "24/7 DRAMA VIP",
    # Zusaetzlich alle Kategorien, die im Screenshot NICHT aktiviert
    # waren - auf Nutzerwunsch trotzdem mitgeprueft, da nicht sicher
    # ist, ob der Aktivierungsstatus wirklich "gehoert nicht zu den
    # 18.957 Live-Sendern" bedeutet (Beispiel: "UK| NOW TV" war
    # deaktiviert, zeigt laut Nutzer aber 149 Sender mit "Keine
    # Information" im EPG-Raster - gehoert also sehr wohl dazu).
    "4K UHD 3840P", "US| BIBLICAL/RELIGIOUS", "WM 2026 REPLAY",
    "US| APPLE TV F1 PPV", "DE| WORLD CUP 2026 REPLAY",
    "DE| DAZN EXCLUSIVE", "US| PARAMOUNT+ PPV RAW", "US| NCAAB PACKAGE",
    "24/7 DISNEY+", "24/7 PRIME VIDEO", "24/7 MOVIES & SERIES",
    "24/7 ONEPLAY", "24/7 SHOWS VIP", "24/7 CLASSIC SHOWS VIP",
    "24/7 REALITY VIP", "24/7 CARTOON VIP", "24/7 COMEDY VIP",
    "24/7 KIDS/FAMILY VIP", "24/7 CRIME VIP",
    "24/7 ACTION & ADVENTURE VIP", "24/7 MOVIES/ACTORS VIP",
    "UK| MOVIES HEVC", "UK| ITV X VIP", "UK| APPLE TV+ SERIES",
    "UK| NETFLIX ORIGINAL", "UK| PRIME VIDEO SERIES", "UK| BBCI",
    "UK| BBCIPLAYER SERIES", "UK| BBC STREAM PPV", "UK| NOW TV",
    "UK| MONOMAX PPV", "UK| MXGP PPV", "UK| VOLLEY BALL WORLD PPV",
    "UK| LIGUE 1 PPV", "UK| RALLY TV PPV", "UK| GAA GO PPV",
    "IR| IRELAND", "IR| CLUBBER PPV", "IR| SETANTA PPV", "IR| LOI PPV",
    "IR| NIFL PPV",
)]

live_gruppen = [
    g for g in gruppen_zaehler
    if g and any(g.upper().startswith(p) for p in LIVE_GRUPPEN_PREFIXE)
]
print(f"\n--- Einzelne fehlende Kanaele in mutmasslichen LIVE-TV-Gruppen ({len(live_gruppen)} Gruppen) ---")
ausgegeben = 0
LIMIT = 3000
for name, gruppe in sorted(fehlend):
    if gruppe in live_gruppen:
        print(f"{gruppe!r} -> {name!r}")
        ausgegeben += 1
        if ausgegeben >= LIMIT:
            print(f"... Abbruch nach {LIMIT} Zeilen (weitere vorhanden) ...")
            break
