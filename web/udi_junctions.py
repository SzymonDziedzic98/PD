"""
Study 3, recenzja UDI: stres przy krzewach 0 m rozbity na typ skrzyżowania (liczba ramion, najmniejszy kąt między ramionami).

Dla każdego skrzyżowania (węzeł stopnia >= 3) ekspozycja = średnia adrenalina phantomów na cykl spędzony na odcinkach
wychodzących z tego skrzyżowania (edge_stats modelu; 10 phantomów z osobną pamięcią strachu, jak w udi_parks.py).
Iloraz ekspozycji przy krzewach 0 m do tej samej miary w kontroli (ta sama powierzchnia poza strefą skrzyżowań, te same
seedy) pokazuje, gdzie krzewy przy skrzyżowaniu podnoszą stres. Brane są tylko skrzyżowania, przy których krzewy stoją
(krzew bliżej niż 12 m od węzła).

    python udi_junctions.py PARK.geojson [...] --reps 3 --mults 0.5 1 --jobs 4 --out DIR
"""

import argparse
import math
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import psm
import udi_experiments as ue
import udi_parks as up

NEAR = 12.0   # m, krzew "przy skrzyżowaniu"


def junction_types(net, probe=5.0):
    out = {}
    for n, edges in enumerate(net.adj):
        if len(edges) < 3:
            continue
        angs = []
        for e in edges:
            if e.a == n:
                q = e.point_at(min(probe, e.length))[0]
                angs.append(math.atan2(q[1] - net.nodes[n][1], q[0] - net.nodes[n][0]))
            if e.b == n:
                q = e.point_at(max(0.0, e.length - probe))[0]
                angs.append(math.atan2(q[1] - net.nodes[n][1], q[0] - net.nodes[n][0]))
        angs.sort()
        gaps = [(angs[(i + 1) % len(angs)] - angs[i]) % (2 * math.pi) for i in range(len(angs))]
        out[n] = {"arms": len(edges), "min_angle": round(math.degrees(min(gaps)), 1),
                  "edges": [e.id for e in edges]}
    return out


def run_job(job):
    path, mult, form, label, rep, cycles = job
    nj, length = up.park_stats(path)
    bots = max(1, round(up.REF_BOTS_PER_M * length))
    sb = None if label == "none" else float(label)
    o = ue.cell(sb, form, bots, {"planting_seed": 1 + rep, "bush_area_total": up.REF_DENSITY * nj * mult,
                                 "phantom_nb": up.PHANTOMS, "fear_scope": "individual", "bush_setback_scope": "all"})
    params = dict(ue.BASE, **o)
    params.pop("park_seed", None)
    m = psm.make_model(params, 1 + rep, cycles, None, up.load(path)).run()
    jt = junction_types(m.net)
    bush_pts = [p for rings in m.obstacles.polygons for p in rings[0]]
    rows = []
    for n, t in jt.items():
        c = m.net.nodes[n]
        near = any(psm.dist(c, q) < NEAR for q in bush_pts)
        cyc = sum(m.edge_stats[i][0] for i in t["edges"])
        adr = sum(m.edge_stats[i][1] for i in t["edges"])
        fear = sum(m.edge_stats[i][3] for i in t["edges"])
        rows.append({"park": up.park_name(path), "mult": mult, "bush_form": form, "label": label, "rep": rep,
                     "node": n, "arms": t["arms"], "min_angle": t["min_angle"], "bush_near": near,
                     "cycles": cyc, "adrenaline_per_cycle": round(adr / cyc, 4) if cyc else "",
                     "fear_per_1000": round(1000.0 * fear / cyc, 3) if cyc else ""})
    return rows


def angle_bin(a):
    return "<60" if a < 60 else ("60-90" if a < 90 else ">=90")


def analyse(rows):
    """Iloraz ekspozycji 0 m / kontrola dla każdego skrzyżowania z krzewami, potem średnie w grupach typu."""
    ctrl = {}
    for r in rows:
        if r["label"] == "none" and r["adrenaline_per_cycle"] != "":
            ctrl[(r["park"], r["mult"], r["bush_form"], r["rep"], r["node"])] = r
    per = []
    for r in rows:
        if r["label"] == "none" or not r["bush_near"] or r["adrenaline_per_cycle"] == "":
            continue
        c = ctrl.get((r["park"], r["mult"], r["bush_form"], r["rep"], r["node"]))
        if not c or not c["adrenaline_per_cycle"] or r["cycles"] < 100 or c["cycles"] < 100:
            continue
        per.append(dict(r, ratio=r["adrenaline_per_cycle"] / c["adrenaline_per_cycle"],
                        arms_group="3" if r["arms"] == 3 else ">=4", angle_bin=angle_bin(r["min_angle"])))
    out = []
    for keys in (("bush_form", "arms_group"), ("bush_form", "angle_bin"), ("bush_form", "arms_group", "angle_bin"),
                 ("park", "bush_form", "arms_group")):
        groups = {}
        for r in per:
            groups.setdefault(tuple(r[k] for k in keys), []).append(math.log(r["ratio"]))
        for g, v in sorted(groups.items()):
            m = ue.mean(v)
            se = ue.sd(v) / math.sqrt(len(v)) if len(v) > 1 else float("nan")
            row = {"grouping": "+".join(keys), **dict(zip(keys, g)), "n": len(v),
                   "ratio_geomean": round(math.exp(m), 3),
                   "ci95_lo": round(math.exp(m - 1.96 * se), 3) if se == se else "",
                   "ci95_hi": round(math.exp(m + 1.96 * se), 3) if se == se else ""}
            out.append(row)
    return per, out


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parks", nargs="+")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--mults", type=float, nargs="+", default=[0.5, 1.0])
    ap.add_argument("--cycles", type=int, default=10000)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--out", default="wyniki_skrzyzowania")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    jobs = [(p, mult, form, lab, r, a.cycles) for p in a.parks for mult in a.mults for form in ue.FORMS
            for lab in ("0", "none") for r in range(a.reps)]
    rows = []
    with Pool(a.jobs) as pool:
        for i, rs in enumerate(pool.imap_unordered(run_job, jobs), 1):
            rows.extend(rs)
            print("\r  %d/%d" % (i, len(jobs)), end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    ue.write(os.path.join(a.out, "skrzyzowania_runs.csv"), rows)
    per, out = analyse(rows)
    ue.write(os.path.join(a.out, "skrzyzowania_ilorazy.csv"), per)
    ue.write(os.path.join(a.out, "skrzyzowania_typy.csv"), out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
