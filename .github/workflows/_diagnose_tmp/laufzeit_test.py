"""Temporaeres Diagnose-Skript (siehe diagnose_laufzeit.yml): testet
JEDE grosse automatische Laender-Kaskade einzeln gegen eine Stichprobe
echter sender.txt-Sender, mit der jeweils in der Produktion genutzten
Worker-Zahl (DE-Kaskade probeweise erhoeht, siehe DE_KASKADE_WORKER
unten) - OHNE die komplette EPG zu generieren oder irgendetwas zu
schreiben/committen. Reine Diagnose, aendert NICHTS an generate_epg.py.

Nutzung: python3 laufzeit_test.py [stichprobe_n]
z.B.:    python3 laufzeit_test.py 200

Jede Quelle laeuft NACHEINANDER (mit kurzer Pause dazwischen) mit ihrer
eigenen festen Worker-Zahl - kein Worker-Vergleich mehr wie in der
ersten Version dieses Skripts (das Ergebnis von Run 1 zeigte bereits:
DE-Kaskade profitiert kaum von >6 Workern, TVPassport ueberhaupt nicht
von >16 - Details in docs/HISTORIE.md). Ziel jetzt: ein Gesamtbild ALLER
Kaskaden auf einmal, um zu sehen, wo die Zeit in der Praxis wirklich
hingeht, und ob eine leicht erhoehte DE-Kaskade-Worker-Zahl (9 statt der
produktiven 6) unter halbwegs realistischer Last noch verlustfrei
bleibt.

WICHTIG: jede Stufe laeuft in diesem Skript isoliert (nicht wie in der
echten Produktion mit mehreren Kaskaden gleichzeitig im Hintergrund-
Pool) - die absoluten Zeiten sind deshalb NICHT direkt mit den
"Laufzeit pro Quelle"-Werten aus einem echten Workflow-Lauf
vergleichbar, wohl aber die RELATIVEN Unterschiede/429-Raten zwischen
den Quellen.
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
from quellen.telemach_epg import telemach_kanal_finden, telemach_hole_programme
from quellen.mtel_epg import mtel_kanal_finden, mtel_hole_programme
from quellen.klix_epg import klix_kanal_finden, klix_hole_programme
from quellen.sky_epg import sky_kanal_finden, sky_hole_programme
from quellen.tvmovie_epg import tvmovie_kanal_finden, tvmovie_hole_programme
from quellen.hoerzu_epg import hoerzu_kanal_finden, hoerzu_hole_programme
from quellen.tvpassport_epg import tvpassport_kanal_finden, tvpassport_hole_programme
from quellen.mts_epg import mts_kanal_finden, mts_hole_programme
from quellen.arena_epg import arena_kanal_finden, arena_hole_programme
from quellen.rtv_rs_epg import rtv_rs_kanal_finden, rtv_rs_hole_programme
from quellen.scifi_epg import scifi_kanal_finden, scifi_hole_programme
from quellen.natgeo_epg import natgeo_kanal_finden, natgeo_hole_programme
from quellen.axn_epg import axn_kanal_finden, axn_hole_programme
from quellen.pickbox_epg import pickbox_kanal_finden, pickbox_hole_programme
from quellen.rtl_hr_epg import rtl_hr_kanal_finden, rtl_hr_hole_programme
from quellen.a1_epg import a1_kanal_finden, a1_hole_programme
from quellen.mojmaxtv_epg import mojmaxtv_kanal_finden, mojmaxtv_hole_programme
from quellen.sportklub_epg import sportklub_kanal_finden, sportklub_hole_programme
from quellen.mojtv_index_epg import mojtv_index_kanal_finden, mojtv_index_hole_programme
from quellen.siol_epg import siol_kanal_finden, siol_hole_programme
from quellen.tvprofil_net_epg import tvprofil_kanal_finden, tvprofil_hole_programme
from quellen.tvprogramrs_epg import tvprogramrs_kanal_finden, tvprogramrs_hole_programme
from quellen.tvprogramdanas_epg import tvprogramdanas_kanal_finden, tvprogramdanas_hole_programme

PAUSE_ZWISCHEN_STUFEN_SEKUNDEN = 10

# NUR fuer diesen Diagnose-Lauf probeweise erhoeht (Produktion bleibt bei
# GEDROSSELTE_QUELLE_WORKER=6 in generate_epg.py, siehe Modul-Docstring -
# diese Datei aendert NICHTS an generate_epg.py).
DE_KASKADE_WORKER = 9

PARALLEL_WORKER = 12
ERHOEHTE_QUELLE_WORKER = 16
TVPASSPORT_WORKER = 24


def _sender_namen_lesen(praefixe, limit):
    """Liest bis zu `limit` Sendernamen aus sender.txt, deren Zeile mit
    einem der `praefixe` beginnt (z.B. "DE|", "TVPASSPORT:"). Rein
    string-basiert, keine Abhaengigkeit von generate_epg.py (das wuerde
    beim Import sofort die komplette EPG-Generierung anstossen). Bei
    einem colon-Praefix (Opt-in-Format "PREFIX:<Land>|<Kanalname>|...")
    ist der Kanalname das zweite Pipe-Feld, sonst das erste."""
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
                        name = teile[1].strip() if ":" in praefix else teile[0].strip()
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


def _einfacher_worker(kanal_finden, hole_programme, tage=2):
    """Baut eine worker(name)-Funktion fuer das haeufigste Muster
    kanal_finden(name) -> id_or_None, hole_programme(id, tage)."""
    def worker(name):
        try:
            ergebnis = kanal_finden(name)
            if ergebnis is not None:
                hole_programme(ergebnis, tage)
        except Exception:
            pass
    return worker


def _telemach_worker(name):
    try:
        site_id = telemach_kanal_finden(name, "ba")
        if site_id is not None:
            telemach_hole_programme(site_id, "ba", 3)
    except Exception:
        pass


def _mtel_worker(name):
    try:
        site_id = mtel_kanal_finden(name)
        if site_id is not None:
            mtel_hole_programme(site_id, 2)
    except Exception:
        pass


def _klix_worker(name):
    try:
        site_id = klix_kanal_finden(name)
        if site_id is not None:
            klix_hole_programme(site_id, 3)
    except Exception:
        pass


def _sky_worker(name):
    try:
        site_id = sky_kanal_finden(name, "DE")
        if site_id is not None:
            sky_hole_programme(site_id, "DE", 2)
    except Exception:
        pass


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


def _arena_worker(name):
    try:
        site_id = arena_kanal_finden(name, "RS")
        if site_id is not None:
            arena_hole_programme(site_id, "RS", 2)
    except Exception:
        pass


def _siol_worker(name):
    try:
        site_id = siol_kanal_finden(name)
        if site_id is not None:
            siol_hole_programme(site_id, 2)
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
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].strip() else 200

    ba_namen = _sender_namen_lesen(("BA|",), n)
    rs_namen = _sender_namen_lesen(("RS|",), n)
    hr_namen = _sender_namen_lesen(("HR|",), n)
    si_namen = _sender_namen_lesen(("SI|",), n)
    de_namen = _sender_namen_lesen(("DE|", "GO|", "PRIME|", "JOYN|", "WOW|"), n)
    sky_namen = _sender_namen_lesen(("SKY:",), n)
    tvp_namen = _sender_namen_lesen(("TVPASSPORT:",), n)

    print(
        f"Stichproben: BA={len(ba_namen)} RS={len(rs_namen)} HR={len(hr_namen)} "
        f"SI={len(si_namen)} DE/GO/PRIME/JOYN/WOW={len(de_namen)} SKY={len(sky_namen)} "
        f"TVPASSPORT={len(tvp_namen)}"
    )

    # (titel, sender_liste, produktions_worker, hoeher_worker_oder_None, funktion)
    # hoeher_worker: probeweise erhoehte Worker-Zahl, NUR fuer diesen
    # Diagnose-Lauf - aendert nichts an generate_epg.py. None = nicht
    # erneut testen (TVPassport bereits im ersten Diagnose-Lauf bei
    # 16/24/32 als identisch gemessen, DE-Kaskade/A1 laufen hier ohnehin
    # schon mit der erhoehten Zahl als einzigem Wert).
    stufen = [
        ("Telemach", ba_namen, PARALLEL_WORKER, 20, _telemach_worker),
        ("mtel.ba", ba_namen, ERHOEHTE_QUELLE_WORKER, 24, _mtel_worker),
        ("klix.ba", ba_namen, PARALLEL_WORKER, 20, _klix_worker),
        ("Sky", sky_namen, PARALLEL_WORKER, 20, _sky_worker),
        ("TVPassport", tvp_namen, TVPASSPORT_WORKER, None, _tvpassport_worker),
        ("DE-Kaskade (hoerzu.de/tvmovie.de)", de_namen, DE_KASKADE_WORKER, None, _de_kaskade_worker),
        ("mts.rs", rs_namen, PARALLEL_WORKER, 20, _einfacher_worker(mts_kanal_finden, mts_hole_programme, 2)),
        ("SportKlub (RS)", rs_namen, PARALLEL_WORKER, 20, _einfacher_worker(sportklub_kanal_finden, sportklub_hole_programme, 2)),
        ("Arena Sport", rs_namen, PARALLEL_WORKER, 20, _arena_worker),
        ("RTV.rs", rs_namen, PARALLEL_WORKER, 20, _einfacher_worker(rtv_rs_kanal_finden, rtv_rs_hole_programme, 2)),
        ("scifi.rs", rs_namen, PARALLEL_WORKER, 20, _einfacher_worker(scifi_kanal_finden, scifi_hole_programme, 2)),
        ("NatGeo", rs_namen, PARALLEL_WORKER, 20, _einfacher_worker(natgeo_kanal_finden, natgeo_hole_programme, 2)),
        ("AXN Adria", rs_namen, PARALLEL_WORKER, 20, _einfacher_worker(axn_kanal_finden, axn_hole_programme, 2)),
        ("Pickbox", rs_namen, PARALLEL_WORKER, 20, _einfacher_worker(pickbox_kanal_finden, pickbox_hole_programme, 2)),
        ("RTL Adria (RS)", rs_namen, PARALLEL_WORKER, 20, _einfacher_worker(rtl_hr_kanal_finden, rtl_hr_hole_programme, 2)),
        ("A1", hr_namen, DE_KASKADE_WORKER, None, _einfacher_worker(a1_kanal_finden, a1_hole_programme, 6)),
        ("MojMaxTV", hr_namen, PARALLEL_WORKER, 20, _einfacher_worker(mojmaxtv_kanal_finden, mojmaxtv_hole_programme, 2)),
        ("SportKlub (HR)", hr_namen, PARALLEL_WORKER, 20, _einfacher_worker(sportklub_kanal_finden, sportklub_hole_programme, 2)),
        ("Pickbox (HR)", hr_namen, PARALLEL_WORKER, 20, _einfacher_worker(pickbox_kanal_finden, pickbox_hole_programme, 2)),
        ("RTL Adria (HR)", hr_namen, PARALLEL_WORKER, 20, _einfacher_worker(rtl_hr_kanal_finden, rtl_hr_hole_programme, 2)),
        ("index.hr (mojtv.hr)", hr_namen, PARALLEL_WORKER, 20, _einfacher_worker(mojtv_index_kanal_finden, mojtv_index_hole_programme, 2)),
        ("Siol/Delo.si/SportKlub", si_namen, PARALLEL_WORKER, 20, _siol_worker),
        ("TvProfil.net", rs_namen, PARALLEL_WORKER, 20, _einfacher_worker(tvprofil_kanal_finden, tvprofil_hole_programme, 3)),
        ("TvProgram.rs", rs_namen, PARALLEL_WORKER, 20, _einfacher_worker(tvprogramrs_kanal_finden, tvprogramrs_hole_programme, 1)),
        ("tvprogramdanas.net", rs_namen, PARALLEL_WORKER, 20, _einfacher_worker(tvprogramdanas_kanal_finden, tvprogramdanas_hole_programme, 3)),
    ]

    # Baut die tatsaechliche Test-Reihenfolge: pro Stufe erst der
    # aktuelle Produktions-Worker-Wert, DANN (falls angegeben) der
    # probeweise erhoehte Wert direkt danach - so lassen sich beide
    # Werte pro Quelle unmittelbar vergleichen.
    durchlaeufe = []
    for titel, namen, worker, hoeher, fn in stufen:
        durchlaeufe.append((titel, namen, worker, fn))
        if hoeher is not None:
            durchlaeufe.append((f"{titel} (erhoeht)", namen, hoeher, fn))

    ergebnisse = []
    for i, (titel, namen, worker, fn) in enumerate(durchlaeufe):
        if not namen:
            print(f"\n=== {titel}: uebersprungen (keine Sender in der Stichprobe) ===")
            continue
        dauer = _stufe_testen(titel, namen, worker, fn)
        ergebnisse.append((titel, worker, len(namen), dauer))
        if i < len(durchlaeufe) - 1:
            print(f"Pause {PAUSE_ZWISCHEN_STUFEN_SEKUNDEN}s vor der naechsten Stufe...", flush=True)
            time.sleep(PAUSE_ZWISCHEN_STUFEN_SEKUNDEN)

    print("\n=== Zusammenfassung (absteigend nach Dauer) ===")
    for titel, worker, anzahl, dauer in sorted(ergebnisse, key=lambda e: e[3], reverse=True):
        print(f"  {titel} @ {worker} Worker: {dauer:.1f}s ({anzahl} Sender)")


if __name__ == "__main__":
    main()
