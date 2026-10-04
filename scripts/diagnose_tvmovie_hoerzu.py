"""Diagnose: Koennen tvmovie.de/hoerzu.de durch epgshare01 ersetzt werden?
(nur Messung, schreibt NICHTS ins EPG).

Pro DE-Sender aus sender.txt wird die abgedeckte Sendezeit verglichen:
- aktuell:  deswird + Pluto + tvmovie + hoerzu + iptv-epg.org
- neu:      deswird + Pluto + epgshare01 (DE1/AT1/CH1) + iptv-epg.org
  (Joyn-VOD/Search.ch/Rakuten bleiben in beiden Faellen aussen vor.)
Zwei Messfenster: "24h" (heute, UTC - tvmovie/hoerzu liefern nur den
aktuellen Tag) und "2 Tage".

Ausgabe: Zusammenfassung im Job-Log + $GITHUB_STEP_SUMMARY und
diagnose_tvmovie_hoerzu.csv (Artefakt). Umgebungsvariable DIAG_LIMIT=N
begrenzt die Senderzahl (Schnelltest).
"""

import csv
import gzip
import os
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)

from quellen import _http  # noqa: E402
from quellen.deswird_epg import deswird_kanal_finden, deswird_hole_programme  # noqa: E402
from quellen.plutotv_epg import plutotv_kanal_finden, plutotv_hole_programme  # noqa: E402
from quellen.tvmovie_epg import tvmovie_kanal_finden, tvmovie_hole_programme  # noqa: E402
from quellen.hoerzu_epg import hoerzu_kanal_finden, hoerzu_hole_programme  # noqa: E402
from quellen.iptvepg_de_epg import iptvepg_de_kanal_finden, iptvepg_de_hole_programme  # noqa: E402

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
EPGSHARE_FEEDS = ["DE1", "AT1", "CH1"]
EPGSHARE_URL = "https://epgshare01.online/epgshare01/epg_ripper_{}.xml.gz"
# Namensabweichungen Playlist <-> epgshare01 (nach norm())
ALIAS = {"ard": "daserste", "kabel1": "kabeleins", "rtl2": "rtlzwei", "rtlii": "rtlzwei"}

HEUTE = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
FENSTER = {"24h": (HEUTE, HEUTE + timedelta(days=1)), "2d": (HEUTE, HEUTE + timedelta(days=2))}
SCHWELLE_MIN = 30  # Minuten Unterschied, ab denen ein Sender als Verlierer/Gewinner zaehlt

zeilen_ausgabe = []


def ausgabe(text=""):
    print(text, flush=True)
    zeilen_ausgabe.append(text)


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(hd|fhd|uhd|sd|tv|hevc|de|at|ch)\b", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return ALIAS.get(s, s)


def kern(name):
    name = re.sub(r"[ⱽᴵᴾᴿᴬᵂᴴᴰ⁴ᴷ]+", "", name)
    name = re.sub(r"\b(VIP|RAW|HD|FHD|UHD|SD|4K|HEVC)\b", "", name, flags=re.I)
    return re.sub(r"\s+", " ", name).strip()


def minuten(intervalle, fenster):
    """Vereinigte Sendeminuten im Messfenster."""
    von, bis = fenster
    clip = sorted((max(s, von), min(e, bis)) for s, e in intervalle if e > von and s < bis)
    summe, ende = 0.0, None
    for s, e in clip:
        if ende is None or s > ende:
            summe += (e - s).total_seconds()
            ende = e
        elif e > ende:
            summe += (e - ende).total_seconds()
            ende = e
    return summe / 60.0


def intervalle(programme):
    return [(p["start"], p["stop"]) for p in programme]


def de_sendernamen():
    namen = {}
    with open(os.path.join(WURZEL, "sender.txt"), encoding="utf-8") as f:
        for zeile in f:
            teile = zeile.rstrip("\n").split("|")
            if len(teile) >= 4 and teile[0].strip().upper() in ("DE", "JOYN", "WOW"):
                name = teile[1].strip()
                namen.setdefault(kern(name).upper(), name)
    return sorted(namen.values())


def epgshare_laden():
    """{norm-Name: (feed, kanal_id)}, {(feed, kanal_id): [(start, stop)]}"""
    namen, pro_kanal = {}, {}
    for feed in EPGSHARE_FEEDS:
        try:
            r = _http.mit_retry(requests.get, EPGSHARE_URL.format(feed), headers=HEADERS, timeout=120)
            r.raise_for_status()
            xml = ET.fromstring(gzip.decompress(r.content))
        except Exception as e:
            ausgabe(f"- epgshare01 {feed}: FEHLER ({e})")
            continue
        n = 0
        for kanal in xml.findall("channel"):
            kid = kanal.get("id")
            for dn in [d.text for d in kanal.findall("display-name") if d.text] + [re.sub(r"\.(de|at|ch)$", "", kid)]:
                namen.setdefault(norm(dn), (feed, kid))
            n += 1
        for p in xml.findall("programme"):
            try:
                s = datetime.strptime(p.get("start"), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
                e = datetime.strptime(p.get("stop"), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
            except (TypeError, ValueError):
                continue
            pro_kanal.setdefault((feed, p.get("channel")), []).append((s, e))
        ausgabe(f"- epgshare01 {feed}: {n} Kanaele geladen")
    return namen, pro_kanal


def main():
    ausgabe("## epgshare01-Feeds")
    eg_namen, eg_intervalle = epgshare_laden()
    ausgabe("")

    namen = de_sendernamen()
    limit = int(os.environ.get("DIAG_LIMIT", "0") or 0)
    if limit:
        namen = namen[:limit]
    ausgabe(f"{len(namen)} DE-Kernsender (Fenster 24h ab {HEUTE:%Y-%m-%d} 00:00 UTC bzw. 2 Tage)\n")

    zeilen = []
    for n in namen:
        z = {"sender": n}
        for key, f in (("dw", deswird_kanal_finden), ("pl", plutotv_kanal_finden),
                       ("tm", tvmovie_kanal_finden), ("hz", hoerzu_kanal_finden),
                       ("ip", iptvepg_de_kanal_finden)):
            try:
                z[key] = f(n)
            except Exception:
                z[key] = None
        z["eg"] = eg_namen.get(norm(n))
        zeilen.append(z)

    # Nur Sender mit tvmovie/hoerzu-Treffer sind fuer die Frage relevant.
    zeilen = [z for z in zeilen if z["tm"] or z["hz"]]
    ausgabe(f"{len(zeilen)} Sender haben einen tvmovie/hoerzu-Treffer\n")

    t0 = time.time()
    tm_slugs = {z["tm"] for z in zeilen if z["tm"]}
    hz_slugs = {z["hz"] for z in zeilen if z["hz"]}

    def hol(args):
        art, slug = args
        try:
            return (art, slug), (tvmovie_hole_programme(slug, 1) if art == "tm" else hoerzu_hole_programme(slug))
        except Exception:
            return (art, slug), []

    with ThreadPoolExecutor(max_workers=4) as pool:
        cache = dict(pool.map(hol, [("tm", s) for s in tm_slugs] + [("hz", s) for s in hz_slugs]))
    ausgabe(f"tvmovie: {len(tm_slugs)} Kanaele, hoerzu: {len(hz_slugs)} Kanaele abgerufen in {time.time()-t0:.0f}s\n")

    for z in zeilen:
        q = {
            "dw": intervalle(deswird_hole_programme(z["dw"], 3)) if z["dw"] else [],
            "pl": intervalle(plutotv_hole_programme(z["pl"], 2)) if z["pl"] else [],
            "tm": intervalle(cache.get(("tm", z["tm"]), [])) if z["tm"] else [],
            "hz": intervalle(cache.get(("hz", z["hz"]), [])) if z["hz"] else [],
            "ip": intervalle(iptvepg_de_hole_programme(z["ip"], 2)) if z["ip"] else [],
            "eg": eg_intervalle.get(z["eg"], []) if z["eg"] else [],
        }
        basis = q["dw"] + q["pl"] + q["ip"]
        z["res"] = {}
        for fn, fenster in FENSTER.items():
            z["res"][fn] = {
                "tm": minuten(q["tm"], fenster), "hz": minuten(q["hz"], fenster),
                "eg": minuten(q["eg"], fenster), "basis": minuten(basis, fenster),
                "aktuell": minuten(basis + q["tm"] + q["hz"], fenster),
                "neu": minuten(basis + q["eg"], fenster),
            }

    pfad = os.path.join(WURZEL, "diagnose_tvmovie_hoerzu.csv")
    with open(pfad, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sender", "tvmovie_slug", "hoerzu_slug", "epgshare_kanal"] +
                   [f"{fn}_{k}" for fn in FENSTER for k in ("basis", "tvmovie", "hoerzu", "epgshare", "aktuell", "neu")])
        for z in zeilen:
            row = [z["sender"], z["tm"] or "", z["hz"] or "", z["eg"][1] if z["eg"] else ""]
            for fn in FENSTER:
                r = z["res"][fn]
                row += [round(r[k]) for k in ("basis", "tm", "hz", "eg", "aktuell", "neu")]
            w.writerow(row)

    for fn, titel in (("24h", "24 Stunden (heute, UTC)"), ("2d", "2 Tage")):
        ausgabe(f"## Auswertung {titel}: aktuell (mit tvmovie/hoerzu) vs. neu (epgshare01 statt tvmovie/hoerzu)")
        verlust = [(z["sender"], z["res"][fn]["aktuell"] - z["res"][fn]["neu"]) for z in zeilen
                   if z["res"][fn]["aktuell"] - z["res"][fn]["neu"] > SCHWELLE_MIN]
        gewinn = [(z["sender"], z["res"][fn]["neu"] - z["res"][fn]["aktuell"]) for z in zeilen
                  if z["res"][fn]["neu"] - z["res"][fn]["aktuell"] > SCHWELLE_MIN]
        nur = [z["sender"] for z in zeilen if z["res"][fn]["neu"] < 1 and z["res"][fn]["aktuell"] >= 1]
        gleich = len(zeilen) - len(verlust) - len(gewinn)
        ausgabe(f"- Sender ohne wesentlichen Unterschied (<= {SCHWELLE_MIN} Min): {gleich}")
        ausgabe(f"- Verlierer (> {SCHWELLE_MIN} Min weniger mit epgshare01): {len(verlust)}")
        for n, v in sorted(verlust, key=lambda x: -x[1])[:30]:
            ausgabe(f"  - {n}: -{v:.0f} Min")
        ausgabe(f"- Gewinner (> {SCHWELLE_MIN} Min mehr mit epgshare01): {len(gewinn)}")
        for n, g in sorted(gewinn, key=lambda x: -x[1])[:15]:
            ausgabe(f"  - {n}: +{g:.0f} Min")
        ausgabe(f"- Sender, die NUR ueber tvmovie/hoerzu Daten haetten: {len(nur)} {nur[:30]}")
        ausgabe(f"- Gesamt Sendeminuten aktuell: {sum(z['res'][fn]['aktuell'] for z in zeilen):.0f}, "
                f"neu: {sum(z['res'][fn]['neu'] for z in zeilen):.0f}")
        ausgabe("")

    ausgabe("Rate-Limit-Uebersicht: " + str(_http.fehler_uebersicht()))

    ziel = os.environ.get("GITHUB_STEP_SUMMARY")
    if ziel:
        with open(ziel, "a", encoding="utf-8") as f:
            f.write("\n".join(zeilen_ausgabe) + "\n")


if __name__ == "__main__":
    main()
