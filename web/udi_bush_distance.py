"""
Odległość krzewów od najbliższej ścieżki w układach Study 3 (recenzja UDI: czy odsunięcie od skrzyżowania nie jest
pomieszane z odsunięciem od ścieżki). Dla każdego parku, gęstości, formy, odsunięcia (0, 15, 20 m i kontrola) i nasadzenia
(planting_seed 1..reps, jak w udi_parks.plan) liczy odległość krawędzi każdego krzewu od najbliższej osi ścieżki
(w modelu ścieżka to linia) i odległość od najbliższego skrzyżowania. Bez symulacji: tylko układ krzewów.
Wymaga shapely.

    python udi_bush_distance.py <parki .geojson ...> [--reps 10] [--setbacks 0 15 20] --out DIR
"""

import argparse
import csv
import os
import statistics
import sys

from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.strtree import STRtree

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import psm
import udi_experiments as ue
import udi_parks as up


def layout(path, mult, form, sb, seed):
    roads, nj = up.load(path)[0], up.park_stats(path)[0]
    o = ue.cell(sb, form, 0, {"planting_seed": seed, "bush_area_total": up.REF_DENSITY * nj * mult,
                              "bush_setback_scope": "all"})
    obs, _info = psm.plant_bushes(roads, psm.resolved_params(dict(ue.BASE, **o)))
    return roads, obs


def bush_rows(path, mult, form, sb, seed):
    roads, obs = layout(path, mult, form, sb, seed)
    net = MultiLineString([LineString(r) for r in roads if len(r) > 1])
    J = [Point(c) for c, _a in psm.junctions(roads)]
    jt = STRtree(J)
    out = []
    for rings in obs:
        poly = Polygon(rings[0])
        dj = poly.distance(J[jt.nearest(poly)])
        out.append((poly.distance(net), dj, poly.area))
    return out


def stats(v):
    v = sorted(v)
    q = lambda p: v[min(len(v) - 1, int(p * (len(v) - 1) + 0.5))]
    return {"n": len(v), "mean": round(statistics.fmean(v), 2), "median": round(statistics.median(v), 2),
            "min": round(v[0], 2), "p10": round(q(0.1), 2), "p90": round(q(0.9), 2), "max": round(v[-1], 2)}


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parks", nargs="+")
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--setbacks", type=float, nargs="+", default=[0.0, 15.0, 20.0])
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    raw, summ = [], []
    for path in a.parks:
        park = up.park_name(path)
        for mult in up.MULTS:
            for form in ue.FORMS:
                for sb in a.setbacks + [None]:
                    d_path, d_junc, w = [], [], []
                    for seed in range(1, a.reps + 1):
                        for dp, dj, ar in bush_rows(path, mult, form, sb, seed):
                            raw.append([park, mult, form, ue.label_of(sb), seed, round(dp, 3), round(dj, 3), round(ar, 2)])
                            d_path.append(dp); d_junc.append(dj); w.append(ar)
                    s = stats(d_path)
                    near = sum(ar for dp, ar in zip(d_path, w) if dp <= 1.5) / sum(w)
                    summ.append(dict(park=park, mult=mult, bush_form=form, setback=ue.label_of(sb),
                                     **{"path_" + k: v for k, v in s.items()},
                                     area_share_within_1_5m=round(near, 3),
                                     junc_median=round(statistics.median(d_junc), 2),
                                     junc_min=round(min(d_junc), 2)))
                    print(park, mult, form, ue.label_of(sb), s["mean"], s["median"], s["min"], flush=True)
    with open(os.path.join(a.out, "krzew_sciezka_raw.csv"), "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["park", "mult", "bush_form", "setback", "planting_seed", "dist_path_m", "dist_junction_m", "area_m2"])
        wr.writerows(raw)
    with open(os.path.join(a.out, "krzew_sciezka_summary.csv"), "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(summ[0]))
        wr.writeheader()
        wr.writerows(summ)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
