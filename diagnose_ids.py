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
    with urllib.request.urlopen(quelle, timeout=180) as r:
        return r.read().decode("utf-8", errors="ignore")


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
