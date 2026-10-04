"""Pluto-TV-Diagnose (nur Messung, schreibt NICHTS ins EPG).

Beantwortet: Muss Pluto TV in der DE-Kaskade bleiben?
1. Ist die Datei erreichbar (HTTP-Status, Groesse, Kanaele, Zeitraum)?
2. Fuer welche DE-Sender aus sender.txt liefert Pluto Daten, und wie viele
   Sendeminuten (heute + 2 Tage, UTC) kommen NUR durch Pluto - also weder
   von deswird.org noch von iptv-epg.org noch von den epgshare01-Feeds
   DE1/AT1/CH1 (diese drei sind die moeglichen Ersatzquellen)?

Ausgabe: Zusammenfassung im Job-Log + $GITHUB_STEP_SUMMARY und
diagnose_pluto.csv (Artefakt). Umgebungsvariable DIAG_LIMIT=N begrenzt die
Senderzahl (Schnelltest).
"""

import csv
import gzip
import os
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)

from quellen import _http  # noqa: E402
from quellen.deswird_epg import deswird_kanal_finden, deswird_hole_programme  # noqa: E402
from quellen.plutotv_epg import plutotv_kanal_finden, plutotv_hole_programme  # noqa: E402
from quellen.iptvepg_de_epg import iptvepg_de_kanal_finden, iptvepg_de_hole_programme  # noqa: E402

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
PLUTO_URL = "https://i.mjh.nz/PlutoTV/de.xml.gz"
EPGSHARE_FEEDS = ["DE1", "AT1", "CH1"]
EPGSHARE_URL = "https://epgshare01.online/epgshare01/epg_ripper_{}.xml.gz"
# Namensabweichungen Playlist <-> epgshare01 (nach norm())
ALIAS = {"ard": "daserste", "kabel1": "kabeleins", "rtl2": "rtlzwei", "rtlii": "rtlzwei"}

HEUTE = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
FENSTER = (HEUTE, HEUTE + timedelta(days=2))

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


def minuten(intervalle):
    """Vereinigte Sendeminuten im Messfenster."""
    clip = sorted(
        (max(s, FENSTER[0]), min(e, FENSTER[1]))
        for s, e in intervalle
        if e > FENSTER[0] and s < FENSTER[1]
    )
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


def pluto_datei_pruefen():
    ausgabe("## Pluto TV: Erreichbarkeit (i.mjh.nz/PlutoTV/de.xml.gz)")
    t0 = time.time()
    try:
        r = requests.get(PLUTO_URL, headers=HEADERS, timeout=90)
        ausgabe(f"- HTTP {r.status_code}, {len(r.content)/1e6:.2f} MB, {time.time()-t0:.1f}s, final: {r.url}")
        r.raise_for_status()
        xml = ET.fromstring(gzip.decompress(r.content))
    except Exception as e:
        ausgabe(f"- FEHLER beim Abruf: {e}")
        return False
    starts = sorted(p.get("start", "")[:8] for p in xml.findall("programme"))
    ausgabe(f"- {len(xml.findall('channel'))} Kanaele, {len(starts)} Sendungen, Zeitraum {starts[0]}..{starts[-1]}")
    ausgabe("")
    return True


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
        for kanal in xml.findall("channel"):
            kid = kanal.get("id")
            for dn in [d.text for d in kanal.findall("display-name") if d.text] + [re.sub(r"\.(de|at|ch)$", "", kid)]:
                namen.setdefault(norm(dn), (feed, kid))
        for p in xml.findall("programme"):
            try:
                s = datetime.strptime(p.get("start"), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
                e = datetime.strptime(p.get("stop"), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
            except (TypeError, ValueError):
                continue
            pro_kanal.setdefault((feed, p.get("channel")), []).append((s, e))
        ausgabe(f"- epgshare01 {feed}: geladen")
    return namen, pro_kanal


def main():
    pluto_datei_pruefen()
    eg_namen, eg_intervalle = epgshare_laden()
    ausgabe("")

    namen = de_sendernamen()
    limit = int(os.environ.get("DIAG_LIMIT", "0") or 0)
    if limit:
        namen = namen[:limit]
    ausgabe(f"{len(namen)} DE-Kernsender geprueft (Fenster {FENSTER[0]:%Y-%m-%d} +2 Tage, UTC)\n")

    zeilen = []
    for n in namen:
        try:
            pl_id = plutotv_kanal_finden(n)
        except Exception:
            pl_id = None
        if not pl_id:
            continue
        try:
            dw_id = deswird_kanal_finden(n)
        except Exception:
            dw_id = None
        try:
            ip_id = iptvepg_de_kanal_finden(n)
        except Exception:
            ip_id = None
        eg = eg_namen.get(norm(n))
        pl = intervalle(plutotv_hole_programme(pl_id, 2))
        dw = intervalle(deswird_hole_programme(dw_id, 3)) if dw_id else []
        ip = intervalle(iptvepg_de_hole_programme(ip_id, 2)) if ip_id else []
        eg_iv = eg_intervalle.get(eg, []) if eg else []
        zeilen.append({
            "sender": n, "pluto_id": pl_id, "epgshare": eg[1] if eg else "",
            "pluto": minuten(pl), "deswird": minuten(dw), "iptvepg": minuten(ip), "epgshare_min": minuten(eg_iv),
            "mit": minuten(pl + dw + ip + eg_iv),
            "ohne": minuten(dw + ip + eg_iv),
            "ohne_ersatz": minuten(dw),
        })

    pfad = os.path.join(WURZEL, "diagnose_pluto.csv")
    with open(pfad, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sender", "pluto_id", "pluto_min", "deswird_min", "iptvepg_min", "epgshare_kanal",
                    "epgshare_min", "gesamt_mit_pluto", "gesamt_ohne_pluto", "nur_pluto_min"])
        for z in zeilen:
            w.writerow([z["sender"], z["pluto_id"], round(z["pluto"]), round(z["deswird"]), round(z["iptvepg"]),
                        z["epgshare"], round(z["epgshare_min"]), round(z["mit"]), round(z["ohne"]),
                        round(z["mit"] - z["ohne"])])

    ausgabe("## Auswertung: Wofuer wird Pluto gebraucht?")
    ausgabe(f"- {len(zeilen)} DE-Sender haben einen Pluto-Treffer")
    nur = [(z["sender"], z["mit"] - z["ohne"]) for z in zeilen if z["mit"] - z["ohne"] > 5]
    ausgabe(f"- davon liefert Pluto bei {len(nur)} mehr als 5 Min, die weder deswird.org noch iptv-epg.org noch epgshare01 haben")
    ausgabe(f"- Pluto-Gesamtbeitrag (nur dort vorhandene Minuten): {sum(m for _, m in nur):.0f} Min")
    ganz = [z["sender"] for z in zeilen if z["ohne"] < 1 and z["pluto"] >= 1]
    ausgabe(f"- Sender, die OHNE Pluto GAR keine echten Daten haetten: {len(ganz)}")
    for n in ganz:
        ausgabe(f"  - {n}")
    ausgabe("- Groesste Pluto-Beitraege (Minuten nur durch Pluto):")
    for n, m in sorted(nur, key=lambda x: -x[1])[:30]:
        ausgabe(f"  - {n}: {m:.0f} Min")
    gegenueber_dw = sum(1 for z in zeilen if z["pluto"] > 5 and z["deswird"] < 1)
    ausgabe(f"- Sender, bei denen deswird.org nichts hat, Pluto aber schon: {gegenueber_dw}")
    ausgabe("")
    ausgabe("Hinweis: tvmovie/hoerzu/Joyn-VOD sind bewusst NICHT in der Ersatzrechnung (nicht Teil dieser Diagnose).")

    ziel = os.environ.get("GITHUB_STEP_SUMMARY")
    if ziel:
        with open(ziel, "a", encoding="utf-8") as f:
            f.write("\n".join(zeilen_ausgabe) + "\n")


if __name__ == "__main__":
    main()
