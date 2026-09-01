"""Einmaliges Nachlade-Skript fuer Logos, deren URL auf den vom
Entwickler-Sandbox aus blockierten Picon-Host (103.176.90.95 /
51.158.145.100) zeigt.

Laeuft NICHT als Teil von generate_epg.py, sondern nur ueber den
separaten, manuell ausgeloesten Workflow logos_nachladen.yml auf einem
GitHub-Actions-Runner mit vollem Internetzugriff (die Entwickler-
Sandbox selbst kann diesen Host nicht erreichen, siehe CLAUDE.md).

Laedt jede betroffene URL genau einmal herunter, optimiert sie wie die
anderen logos/-Sets (max. 300px Kantenlaenge, 256-Farben-Palette) und
speichert sie selbst gehostet unter logos/blockiert_nachgeladen/
<sha1-hash>.png. sender.txt wird anschliessend so umgeschrieben, dass
dort statt der externen URL die raw.githubusercontent.com-URL der
selbst gehosteten Datei steht.

Zero-Risk: schlaegt der Download fuer eine einzelne URL fehl (Timeout,
HTTP-Fehler, kaputtes Bild), bleibt die betroffene Zeile in sender.txt
unveraendert (alte externe URL bleibt stehen) - kein Absturz des
gesamten Laufs.
"""

import hashlib
import io
import re
import sys

import requests
from PIL import Image

SENDER_DATEI = "sender.txt"
ZIEL_ORDNER = "logos/blockiert_nachgeladen"
RAW_BASIS = "https://raw.githubusercontent.com/babo20094-rgb/Epg/main"

BLOCKIERTE_HOSTS = ("103.176.90.95", "51.158.145.100")

MAX_KANTENLAENGE = 300
REQUEST_TIMEOUT_SEKUNDEN = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def _url_blockiert(url):
    return any(host in url for host in BLOCKIERTE_HOSTS)


def _optimiere_und_speichere(rohbytes, ziel_pfad):
    bild = Image.open(io.BytesIO(rohbytes))
    bild.load()

    if bild.width > MAX_KANTENLAENGE or bild.height > MAX_KANTENLAENGE:
        bild.thumbnail((MAX_KANTENLAENGE, MAX_KANTENLAENGE), Image.LANCZOS)

    if bild.mode in ("RGBA", "LA") or (bild.mode == "P" and "transparency" in bild.info):
        bild = bild.convert("RGBA")
        bild = bild.quantize(colors=256, method=Image.FASTOCTREE).convert("RGBA")
    else:
        bild = bild.convert("RGB")
        bild = bild.quantize(colors=256, method=Image.MEDIANCUT).convert("RGB")

    bild.save(ziel_pfad, "PNG", optimize=True)


def main():
    import os

    with open(SENDER_DATEI, encoding="utf-8") as f:
        zeilen = f.readlines()

    # Alle betroffenen, eindeutigen URLs sammeln
    urls = set()
    for zeile in zeilen:
        roh = zeile.rstrip("\n")
        if not roh or roh.startswith("#"):
            continue
        teile = roh.split("|")
        logo = teile[-1].strip()
        if logo and _url_blockiert(logo):
            urls.add(logo)

    print(f"Gefundene eindeutige blockierte Logo-URLs: {len(urls)}")

    os.makedirs(ZIEL_ORDNER, exist_ok=True)

    url_zu_raw = {}
    fehler = 0
    for i, url in enumerate(sorted(urls), 1):
        hash_name = hashlib.sha1(url.encode("utf-8")).hexdigest()
        ziel_pfad = os.path.join(ZIEL_ORDNER, f"{hash_name}.png")
        raw_url = f"{RAW_BASIS}/{ziel_pfad}"

        if os.path.exists(ziel_pfad):
            url_zu_raw[url] = raw_url
            continue

        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEKUNDEN)
            resp.raise_for_status()
            _optimiere_und_speichere(resp.content, ziel_pfad)
            url_zu_raw[url] = raw_url
        except Exception as e:
            fehler += 1
            print(f"  [{i}/{len(urls)}] FEHLER bei {url}: {e}")
            continue

        if i % 100 == 0:
            print(f"  [{i}/{len(urls)}] verarbeitet...")

    print(f"Erfolgreich heruntergeladen/optimiert: {len(url_zu_raw)}, Fehler: {fehler}")

    # sender.txt umschreiben
    geaenderte_zeilen = 0
    neue_zeilen = []
    for zeile in zeilen:
        roh = zeile.rstrip("\n")
        if not roh or roh.startswith("#"):
            neue_zeilen.append(zeile)
            continue
        teile = roh.split("|")
        logo = teile[-1].strip()
        if logo in url_zu_raw:
            teile[-1] = url_zu_raw[logo]
            neue_zeilen.append("|".join(teile) + "\n")
            geaenderte_zeilen += 1
        else:
            neue_zeilen.append(zeile)

    with open(SENDER_DATEI, "w", encoding="utf-8") as f:
        f.writelines(neue_zeilen)

    print(f"sender.txt aktualisiert: {geaenderte_zeilen} Zeilen auf selbst gehostete Logos umgestellt.")

    if fehler > 0 and len(url_zu_raw) == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
