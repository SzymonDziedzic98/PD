"""
E1 na prawdziwych parkach (GeoJSON z OSM): reguła odsunięcia krzewów od skrzyżowań.

Ilość nasadzeń skalowana liczbą skrzyżowań parku: gęstość referencyjna z E1 (1500 m² na 19 skrzyżowań
parku generowanego, ok. 79 m² na skrzyżowanie) × mnożnik 0,25 / 0,5 / 1.
Liczba odwiedzających skalowana długością ścieżek: 50 os. na 2557 m (ok. 19,6 os./km), jak średnia frekwencja w E1.
W każdym przebiegu 10 phantomów z osobną pamięcią strachu (fear_scope = individual); phantomy widzą tylko boty,
więc są niezależnymi obserwatorami tej samej symulacji. Boty nie znają strachu phantomów (bot_graph = plain).
Sieć z OSM jest upraszczana przy wczytywaniu (simplify_roads: równoległe ścieżki do 3 m, skupiska skrzyżowań do 6 m;
link_dead_ends: ślepe końce do 25 m od siebie wewnątrz parku, np. place nieoznaczone w OSM),
a odsunięcie krzewów liczy się od każdego skrzyżowania (bush_setback_scope = "all").

    python udi_parks.py PARK.geojson [PARK2.geojson ...] --reps 3 --jobs 4 --out wyniki
"""

import argparse
import csv
import math
import os
import sys
import time
from multiprocessing import Pool

# model jest w src/ (wymóg SoftwareX)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import psm
import udi_experiments as ue

REF_DENSITY = 1500.0 / 19        # m² krzewów na skrzyżowanie (park generowany, park_seed 1)
REF_BOTS_PER_M = 50 / 2556.86    # odwiedzający na metr ścieżek
MULTS = [0.25, 0.5, 1.0]
PHANTOMS = 10

_INPUTS = {}


def park_name(path):
    return os.path.splitext(os.path.basename(path))[0]


def load(path):
    if path not in _INPUTS:
        with open(path, "rb") as f:
            _INPUTS[path] = psm.load_inputs(f.read(), None, path)
    return _INPUTS[path]


def park_stats(path):
    roads = load(path)[0]
    return len(psm.junctions(roads)), sum(psm.polyline_length(r) for r in roads)


def plan(paths, reps, mults=MULTS, bots_per_m=REF_BOTS_PER_M):
    jobs = []
    for path in paths:
        nj, length = park_stats(path)
        bots = max(1, round(bots_per_m * length))
        for mult in mults:
            for form in ue.FORMS:
                for sb in ue.SETBACKS + [None]:
                    for r in range(reps):
                        o = ue.cell(sb, form, bots, {"planting_seed": 1 + r, "bush_area_total": REF_DENSITY * nj * mult,
                                                     "phantom_nb": PHANTOMS, "fear_scope": "individual",
                                                     "bush_setback_scope": "all"})
                        jobs.append((path, mult, ue.label_of(sb), r, o))
    return jobs


def run_job(job, cycles=10000):
    path, mult, label, rep, o = job
    params = dict(ue.BASE, **o)
    params.pop("park_seed", None)
    m = psm.make_model(params, 1 + rep, cycles, None, load(path)).run()
    info = m.planting_info or {}
    nj, length = park_stats(path)
    rows = []
    for k, ph in enumerate(m.phantoms):
        rows.append({"park": park_name(path), "junctions": nj, "path_length": round(length), "bot_nb": o["bot_nb"],
                     "mult": mult, "bush_form": o["bush_form"], "label": label, "rep": rep, "phantom": k,
                     "bush_area_target": round(info.get("area_target", 0), 1), "bush_area": round(info.get("area", 0), 1),
                     "junction_share_real": info.get("junction_share", ""), "setback_real": info.get("setback_mean", ""),
                     "total_adrenaline": round(ph.total_adrenaline, 3), "total_vigilance": round(ph.total_vigilance, 3),
                     "fear_events": ph.fear_events})
    return rows


def _run(args):
    job, cycles = args
    return run_job(job, cycles)


def summarize(rows):
    out = ue.summarize(rows, ["park", "mult", "bush_form", "label"],
                       outs=["total_adrenaline", "total_vigilance", "fear_events"],
                       extra=["bush_area", "junction_share_real", "setback_real"])
    return sorted(out, key=lambda r: (r["park"], float(r["mult"]), r["bush_form"], r["label"]))


def thresholds(rows):
    return ue.thresholds(rows, group_keys=("park", "mult", "bush_form"))


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parks", nargs="+")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--cycles", type=int, default=10000)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--out", default="wyniki_parki")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    all_rows = []
    for path in a.parks:   # park po parku, żeby wyniki mniejszych parków były gotowe wcześniej
        t0 = time.time()
        jobs = plan([path], a.reps)
        rows = []
        with Pool(a.jobs) as pool:
            for i, rs in enumerate(pool.imap_unordered(_run, [(j, a.cycles) for j in jobs]), 1):
                rows.extend(rs)
                print("\r  %s %d/%d" % (park_name(path), i, len(jobs)), end="", file=sys.stderr, flush=True)
        print("\n  %s: %.0f s" % (park_name(path), time.time() - t0), file=sys.stderr, flush=True)
        all_rows.extend(rows)
        ue.write(os.path.join(a.out, "parki_runs.csv"), all_rows)
        ue.write(os.path.join(a.out, "parki_summary.csv"), summarize(all_rows))
        ue.write(os.path.join(a.out, "parki_threshold.csv"), thresholds(all_rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
