"""Temporaeres Diagnose-Skript (siehe diagnose_laufzeit.yml): testet
verschiedene Worker-Zahlen fuer die DE-Kaskade (hoerzu.de/tvmovie.de,
die bekannten Rate-Limiting-Kandidaten) und optional TVPassport gegen
eine Stichprobe echter sender.txt-Sender - OHNE die komplette EPG zu
generieren oder irgendetwas zu schreiben/committen.

Nutzung: python3 laufzeit_test.py <de_worker_liste> <de_stichprobe>
                                   <tvp_worker_liste> <tvp_stichprobe>
z.B.:    python3 laufzeit_test.py "3,6,9,12" 250 "16,24,32" 200

WICHTIG: mehrere Worker-Stufen laufen NACHEINANDER im selben Skript -
eine hoehere Stufe kann den Server bereits in einen gedrosselten
Zustand versetzt haben, der die naechste Stufe kuenstlich schlechter
aussehen laesst (Nachwirkung, nicht ursaechlich durch die Worker-Zahl
selbst). Kurze Pause zwischen den Stufen mildert das, garantiert aber
keine 100% saubere Trennung - Ergebnis ist eine Orientierung, kein
Laborexperiment.
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

# Skript liegt in .github/workflows/_diagnose_tmp/, "quellen" aber im
# Repo-Root - Python setzt sys.path[0] sonst nur auf das Skript-
# Verzeichnis selbst. Setzt voraus, dass das Skript aus dem Repo-Root
# heraus aufgerufen wird (so wie es diagnose_laufzeit.yml tut).
sys.path.insert(0, os.getcwd())

from quellen import _http
from quellen.tvmovie_epg import tvmovie_kanal_finden, tvmovie_hole_programme
from quellen.hoerzu_epg import hoerzu_kanal_finden, hoerzu_hole_programme
from quellen.tvpassport_epg import tvpassport_kanal_finden, tvpassport_hole_programme

PAUSE_ZWISCHEN_STUFEN_SEKUNDEN = 15


def _sender_namen_lesen(praefixe, limit):
    """Liest bis zu `limit` Sendernamen aus sender.txt, deren Zeile mit
    einem der `praefixe` beginnt (z.B. "DE|", "TVPASSPORT:"). Rein
    string-basiert, keine Abhaengigkeit von generate_epg.py (das wuerde
    beim Import sofort die komplette EPG-Generierung anstossen)."""
    namen = []
    with open("sender.txt", "r", encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.rstrip("\n")
            if not zeile or zeile.startswith("#"):
                continue
            for praefix in praefixe:
                if zeile.startswith(praefix):
                    rest = zeile[len(praefix):]
                    teile = rest.split("|")
                    if len(teile) >= 2:
                        name = teile[1].strip() if praefix.startswith("TVPASSPORT") else teile[0].strip()
                        if name:
                            namen.append(name)
                    break
            if len(namen) >= limit:
                break
    return namen


def _statistik_snapshot():
    return {host: dict(werte) for host, werte in _http._STATISTIK.items()}


def _statistik_delta(vorher, nachher):
    hosts = set(vorher) | set(nachher)
    zeilen = []
    for host in hosts:
        v = vorher.get(host, {"versuche": 0, "rate_limit": 0, "fehlgeschlagen": 0, "wartezeit_gesamt": 0.0, "retry_after_header_treffer": 0})
        n = nachher.get(host, v)
        delta = {k: n.get(k, 0) - v.get(k, 0) for k in v}
        if delta["versuche"]:
            zeilen.append((host, delta))
    return zeilen


def _de_kaskade_worker(name):
    try:
        slug = tvmovie_kanal_finden(name)
        if slug is not None:
            tvmovie_hole_programme(slug, 1)
    except Exception:
        pass
    try:
        slug = hoerzu_kanal_finden(name)
        if slug is not None:
            hoerzu_hole_programme(slug)
    except Exception:
        pass


def _tvpassport_worker(name):
    try:
        site_id = tvpassport_kanal_finden(name)
        if site_id is not None:
            tvpassport_hole_programme(site_id, 2)
    except Exception:
        pass


def _stufe_testen(titel, namen, worker, abruf_fn):
    print(f"\n=== {titel}: {worker} Worker, {len(namen)} Sender ===", flush=True)
    vorher = _statistik_snapshot()
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=worker) as pool:
        list(pool.map(abruf_fn, namen))
    dauer = time.monotonic() - start
    nachher = _statistik_snapshot()

    print(f"Dauer: {dauer:.1f}s ({len(namen) / dauer:.1f} Sender/s)")
    for host, delta in _statistik_delta(vorher, nachher):
        print(
            f"  {host}: {delta['versuche']} Versuche, {delta['rate_limit']}x 429/503, "
            f"{delta['fehlgeschlagen']} endgueltig fehlgeschlagen, "
            f"{delta['wartezeit_gesamt']:.1f}s Retry-Wartezeit "
            f"({delta['retry_after_header_treffer']}x mit Retry-After-Header)"
        )
    return dauer


def main():
    de_worker_liste = [int(w) for w in sys.argv[1].split(",") if w.strip()] if len(sys.argv) > 1 else [6]
    de_stichprobe_n = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].strip() else 250
    tvp_worker_liste = [int(w) for w in sys.argv[3].split(",") if w.strip()] if len(sys.argv) > 3 else []
    tvp_stichprobe_n = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4].strip() else 0

    de_namen = _sender_namen_lesen(("DE|", "GO|", "PRIME|", "JOYN|", "WOW|"), de_stichprobe_n)
    print(f"DE-Kaskade-Stichprobe: {len(de_namen)} Sender gelesen.")

    ergebnisse = []
    for i, worker in enumerate(de_worker_liste):
        dauer = _stufe_testen(f"DE-Kaskade (hoerzu.de/tvmovie.de)", de_namen, worker, _de_kaskade_worker)
        ergebnisse.append(("DE-Kaskade", worker, dauer))
        if i < len(de_worker_liste) - 1:
            print(f"Pause {PAUSE_ZWISCHEN_STUFEN_SEKUNDEN}s vor der naechsten Stufe...", flush=True)
            time.sleep(PAUSE_ZWISCHEN_STUFEN_SEKUNDEN)

    if tvp_worker_liste and tvp_stichprobe_n:
        tvp_namen = _sender_namen_lesen(("TVPASSPORT:",), tvp_stichprobe_n)
        print(f"\nTVPassport-Stichprobe: {len(tvp_namen)} Sender gelesen.")
        for i, worker in enumerate(tvp_worker_liste):
            dauer = _stufe_testen("TVPassport", tvp_namen, worker, _tvpassport_worker)
            ergebnisse.append(("TVPassport", worker, dauer))
            if i < len(tvp_worker_liste) - 1:
                print(f"Pause {PAUSE_ZWISCHEN_STUFEN_SEKUNDEN}s vor der naechsten Stufe...", flush=True)
                time.sleep(PAUSE_ZWISCHEN_STUFEN_SEKUNDEN)

    print("\n=== Zusammenfassung ===")
    for quelle, worker, dauer in ergebnisse:
        print(f"  {quelle} @ {worker} Worker: {dauer:.1f}s")


if __name__ == "__main__":
    main()
