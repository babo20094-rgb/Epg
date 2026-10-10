"""Einmal-Werkzeug (Diagnose-Workflow "Logos holen"): laedt alle noch
EXTERNEN Logo-URLs aus sender.txt herunter, optimiert sie (max. 300 px,
256 Farben) nach logos/externe_logos_import/<sha1(url)>.png und stellt
sender.txt auf die selbst gehostete raw.githubusercontent.com-URL um.
Nicht ladbare Links bleiben unveraendert; am Ende steht ein Bericht pro
Host/Fehlerart (Diagnose). Aufruf: python tools/logos_holen.py [--dry]"""
import concurrent.futures as cf
import hashlib
import io
import os
import re
import sys
from collections import Counter, defaultdict
from urllib.parse import urlparse

import requests
from PIL import Image

BASIS = "https://raw.githubusercontent.com/babo20094-rgb/Epg/main/logos/"
ZIEL = "logos/externe_logos_import"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}
URL_RE = re.compile(r"https?://[^|\s]+")


def umwandeln(daten, url, ct):
    if "svg" in ct or url.lower().split("?")[0].endswith(".svg"):
        import cairosvg
        daten = cairosvg.svg2png(bytestring=daten, output_width=300)
    im = Image.open(io.BytesIO(daten))
    im.load()
    im.thumbnail((300, 300), Image.LANCZOS)
    if im.mode == "P":
        im = im.convert("RGBA")
    if im.mode in ("RGBA", "LA"):
        return im.convert("RGBA").quantize(colors=256, method=Image.FASTOCTREE)
    return im.convert("RGB").quantize(colors=256, method=Image.MEDIANCUT)


def holen(url):
    h = hashlib.sha1(url.encode()).hexdigest()
    pfad = f"{ZIEL}/{h}.png"
    if os.path.exists(pfad):
        return url, h, "OK (schon vorhanden)"
    letzter = ""
    for versuch in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            if r.status_code == 429:
                import time
                time.sleep(8 * (versuch + 1))
                letzter = "HTTP 429"
                continue
            if r.status_code != 200:
                return url, h, f"HTTP {r.status_code}"
            umwandeln(r.content, url, r.headers.get("content-type", "")).save(pfad, optimize=True)
            return url, h, "OK"
        except Exception as e:
            letzter = f"{type(e).__name__}: {str(e)[:70]}"
    return url, h, letzter or "Fehler"


def main():
    dry = "--dry" in sys.argv
    os.makedirs(ZIEL, exist_ok=True)
    text = open("sender.txt", encoding="utf-8").read()
    urls = sorted({u for u in URL_RE.findall(text) if "raw.githubusercontent.com/babo20094-rgb/Epg" not in u})
    print(f"{len(urls)} externe URLs gefunden.")
    if dry:
        return
    # Je Host wenige parallele Abrufe (Wikimedia/Server nicht ueberlasten).
    ergebnisse = []
    nach_host = defaultdict(list)
    for u in urls:
        nach_host[urlparse(u).netloc].append(u)
    with cf.ThreadPoolExecutor(12) as ex:
        futs = [ex.submit(lambda us=us: [holen(u) for u in us]) for us in nach_host.values()]
        for f in futs:
            ergebnisse.extend(f.result())
    ok = {u: h for u, h, s in ergebnisse if s.startswith("OK")}
    for u, h in ok.items():
        text = text.replace(u, f"{BASIS}externe_logos_import/{h}.png")
    open("sender.txt", "w", encoding="utf-8").write(text)
    print("\n=== Diagnose je Host ===")
    z = defaultdict(Counter)
    for u, h, s in ergebnisse:
        z[urlparse(u).netloc][s.split(":")[0] if s.startswith("OK") is False else "OK"] += 1
    for host, c in sorted(z.items()):
        print(host, dict(c))
    print("\n=== Nicht ladbar ===")
    for u, h, s in ergebnisse:
        if not s.startswith("OK"):
            print(s, "|", u)
    print(f"\n{len(ok)} von {len(urls)} URLs umgestellt.")


if __name__ == "__main__":
    main()
