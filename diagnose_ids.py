"""Reines Diagnose-Werkzeug (aendert nichts, schreibt keine EPG-Datei).

Vergleicht die Kanal-IDs der aktuell veroeffentlichten Epg_365_Tage.xml.gz
mit den Kanalnamen der eigenen IPTV-Playlist (Secret PROVIDER) und gibt
nur Zahlen/Beispielnamen aus - NIE die Playlist-URL.

Aufruf: python diagnose_ids.py [EPG.xml.gz] [Playlist-Datei-statt-URL]
"""
import gzip
import os
import re
import sys
import urllib.request
from html import unescape


def playlist_laden(quelle):
    if os.path.isfile(quelle):
        with open(quelle, encoding="utf-8", errors="ignore") as f:
            return f.read()
    # Der Anbieter weist den ersten Abruf sofort mit einem Fehler (403/461)
    # ab, bereitet die Playlist aber offenbar im Hintergrund vor: im
    # Browser startet der Download erst nach einiger Wartezeit. Deshalb
    # wenige Abrufe mit LANGEN Pausen (Abstaende 3/5/7 Minuten, zusammen
    # ca. 15 Minuten) statt vieler kurzer - schont zugleich den Anbieter.
    import time
    import requests
    pausen = [0, 180, 300, 420]
    letzter = "unbekannt"
    for versuch, pause in enumerate(pausen, start=1):
        time.sleep(pause)
        try:
            antwort = requests.get(quelle, timeout=300)
            text = antwort.content.decode("utf-8", errors="ignore")
            if antwort.ok and text.lstrip().startswith("#EXTM3U"):
                print(f"Playlist geladen bei Versuch {versuch} ({len(text)} Zeichen)")
                return text
            # Nur Statuscode und Anfang der Antwort melden, nie die URL.
            letzter = f"HTTP {antwort.status_code}, Antwortanfang: {text[:80]!r}"
        except requests.RequestException as fehler:
            letzter = f"{type(fehler).__name__}"
        print(f"Versuch {versuch}/{len(pausen)} fehlgeschlagen: {letzter}", flush=True)
    sys.exit(f"Playlist nicht ladbar nach {len(pausen)} Versuchen: {letzter}")


def playlist_namen(text):
    """Gibt (tvg_namen, anzeigenamen) als Listen zurueck - je Kanal einer."""
    tvg, anzeige = [], []
    for zeile in text.splitlines():
        if not zeile.startswith("#EXTINF"):
            continue
        m = re.search(r'tvg-name="(.*?)"(?=\s+[\w-]+=|,)', zeile)
        if m:
            tvg.append(m.group(1))
        if "," in zeile:
            anzeige.append(zeile.split('",', 1)[-1] if '",' in zeile else zeile.rsplit(",", 1)[-1])
    return tvg, anzeige


def epg_ids(pfad):
    with gzip.open(pfad, "rt", encoding="utf-8") as f:
        xml = f.read()
    return [unescape(i) for i in re.findall(r'<channel id="([^"]*)"', xml)]


def bericht(ids, namen, titel, ausgabe):
    ids_set, namen_set = set(ids), set(namen)
    treffer = ids_set & namen_set
    ohne_id = namen_set - ids_set
    ueberfluessig = ids_set - namen_set
    ausgabe.append(f"### Abgleich mit {titel}")
    ausgabe.append(f"- Kanaele in der Playlist (verschieden): {len(namen_set)}")
    ausgabe.append(f"- IDs in der EPG-Datei (verschieden): {len(ids_set)}")
    ausgabe.append(f"- Playlist-Kanaele MIT exakt passender ID: {len(treffer)}")
    ausgabe.append(f"- Playlist-Kanaele OHNE passende ID (Luecken): {len(ohne_id)}")
    ausgabe.append(f"- IDs OHNE Gegenstueck in der Playlist (entbehrlich?): {len(ueberfluessig)}")
    for name, menge in (("Luecken", ohne_id), ("Entbehrliche IDs", ueberfluessig)):
        ausgabe.append(f"\nBeispiele {name} (max. 25):")
        for n in sorted(menge)[:25]:
            ausgabe.append("  " + repr(n))
    ausgabe.append("")


def main():
    epg = sys.argv[1] if len(sys.argv) > 1 else "Epg_365_Tage.xml.gz"
    quelle = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("PROVIDER")
    if not quelle:
        sys.exit("Kein PROVIDER-Secret und keine Playlist-Datei angegeben.")
    ids = epg_ids(epg)
    tvg, anzeige = playlist_namen(playlist_laden(quelle))
    ausgabe = ["## Diagnose Kanal-IDs", ""]
    ausgabe.append(f"EPG-IDs gesamt: {len(ids)} (verschieden: {len(set(ids))})")
    ausgabe.append(f"Playlist-Eintraege: tvg-name={len(tvg)}, Anzeigename={len(anzeige)}\n")
    bericht(ids, tvg, "tvg-name", ausgabe)
    bericht(ids, anzeige, "Anzeigename", ausgabe)
    text = "\n".join(ausgabe)
    print(text)
    ziel = os.environ.get("GITHUB_STEP_SUMMARY")
    if ziel:
        with open(ziel, "a", encoding="utf-8") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
