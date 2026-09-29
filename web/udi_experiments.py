"""
Eksperymenty E1–E3 do artykułu PSM (URBAN DESIGN International), liczone na porcie psm.py.

E1  kontrolowany eksperyment nasadzeń: stała powierzchnia krzewów (1500 m²), wszystkie jako skupiska ekranujące
    przy skrzyżowaniach; odsunięcie od węzła 0/5/10/15/20 m × forma (kępy / pas) × 20/50/80 odwiedzających.
    Kontrola "none": ta sama powierzchnia wzdłuż ścieżek, poza strefą skrzyżowań (15 m).
E1b odporność reguły na układ ścieżek: 10 innych sieci generowanych, 50 odwiedzających.
E2  izowisty co 2 m wzdłuż ścieżek vs stres (warianty E1 przy 20 i 80 odwiedzających).
E1h czy próg odsunięcia skaluje się z promieniem stref: park generowany (seed 1), kępy i pas, odsunięcie
    0–30 m co 5 m + kontrola, 50 odwiedzających, hall_multiplier 2 / 3 / 4 / 5 (strefa społeczna 7,2–18 m).
E2r izowisty E2 przy innym zasięgu: 100 m oraz bez limitu (400 m = przekątna parku generowanego), obok 40 m.
E3  wrażliwość OAT ±20% stałych modelu przy 20 i 80 odwiedzających, dla nasadzeń S0 (odsunięcie 0 m)
    i S20 (odsunięcie 20 m); kryterium: czy ranking S20 < S0 się utrzymuje.

Uruchomienie (CPython, kilka procesów):
    python udi_experiments.py e1 --reps 50 --jobs 4 --out wyniki
    python udi_experiments.py e1b e2 e3 --jobs 4 --out wyniki
Park: sieć generowana (park_seed 1 = sieć referencyjna). Wynik "setback_real" to faktyczny odstęp krawędzi
krzewów od węzła (0 m jest geometrycznie niemożliwe przy odstępie 1 m od ścieżek, więc realnie ok. 3 m).
"""

import argparse
import csv
import math
import os
import sys
import time

# model jest w src/ (wymóg SoftwareX)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import psm

BASE = {
    "planting": "controlled",
    "bush_area_total": 1500.0,
    "bush_junction_share": 1.0,
    "park_seed": 1,
    "isovist_spacing": 2.0,
    "bot_graph": "plain",  # boty nie znają strachu phantoma
}
SETBACKS = [0.0, 5.0, 10.0, 15.0, 20.0]
SETBACKS_H = [0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0]
HALL_MULTS = [2.0, 3.0, 4.0, 5.0]
ISOVIST_RADII = [("100", 100.0), ("unbounded", 400.0)]   # 400 m = przekątna parku generowanego (320 × 240 m)
NI_MARGIN = 1.10                                          # równoważność: górne 95% CI ilorazu do kontroli < 1,10
FORMS = ["clumps", "band"]
VISITORS = [20, 50, 80]
OUT_KEYS = ["total_adrenaline", "total_cortisol", "total_vigilance", "fear_events", "edge_stress_sd"]


def cell(setback, form, bots, extra=None):
    o = {"bush_form": form, "bot_nb": bots}
    if setback is None:
        o["bush_junction_share"] = 0.0
        o["bush_junction_distance"] = 0.0
    else:
        o["bush_junction_distance"] = setback
    if extra:
        o.update(extra)
    return o


def label_of(setback):
    return "none" if setback is None else "%g" % setback


def e1_plan(reps, visitors=VISITORS, networks=(1,), seed0=1, setbacks=SETBACKS, extra=None):
    plan = []
    for net in networks:
        for bots in visitors:
            for form in FORMS:
                for sb in setbacks + [None]:
                    for r in range(reps):
                        seed = seed0 + r
                        o = cell(sb, form, bots, dict(extra or {}, park_seed=net, planting_seed=seed))
                        plan.append((o, seed, label_of(sb)))
    return plan


def e1h_plan(reps, seed0=1):
    plan = []
    for hm in HALL_MULTS:
        plan += e1_plan(reps, visitors=[50], seed0=seed0, setbacks=SETBACKS_H, extra={"hall_multiplier": hm})
    return plan


E3_PARAMS = ["adrenaline_threshold", "adrenaline_cooldown", "cortisol_cooldown", "cortisol_gain", "hall_multiplier"]


def e3_plan(reps, delta=0.2, seed0=1):
    base = psm.resolved_params(BASE)
    plan = []
    for bots in (20, 80):
        for sb in (0.0, 20.0):
            conds = [("base", {})]
            for n in E3_PARAMS:
                for sign, tag in ((-1, "-"), (1, "+")):
                    conds.append((n + tag, {n: psm._perturb(n, base[n], delta, sign)}))
            for lab, o in conds:
                for r in range(reps):
                    seed = seed0 + r
                    oo = cell(sb, "clumps", bots, dict(o, planting_seed=seed))
                    plan.append((oo, seed, lab))
    return plan


# ---------------------------------------------------------------------------
# statystyki
# ---------------------------------------------------------------------------

def mean(v):
    return sum(v) / len(v)


def sd(v):
    return psm._sd(v)


def summarize(rows, keys, outs=OUT_KEYS, extra=()):
    groups = {}
    for r in rows:
        groups.setdefault(tuple(r[k] for k in keys), []).append(r)
    out = []
    for g, rs in groups.items():
        row = dict(zip(keys, g))
        row["n"] = len(rs)
        for o in list(outs) + list(extra):
            vals = [float(r[o]) for r in rs if r.get(o) not in ("", None)]
            if not vals:
                continue
            m, s = mean(vals), sd(vals)
            row[o + "_mean"] = round(m, 4)
            row[o + "_sd"] = round(s, 4)
            row[o + "_ci95"] = round(1.96 * s / math.sqrt(len(vals)), 4)
        out.append(row)
    return out


def welch(a, b):
    """t Welcha i przybliżona wartość p (rozkład normalny; n >= 30)."""
    ma, mb = mean(a), mean(b)
    va, vb = sd(a) ** 2, sd(b) ** 2
    se = math.sqrt(va / len(a) + vb / len(b))
    if se == 0:
        return 0.0, 1.0
    t = (ma - mb) / se
    p = math.erfc(abs(t) / math.sqrt(2))
    return t, p


def ratio_upper(v, ctrl, z=1.645):
    """Jednostronna górna granica 95% CI ilorazu średnich v / ctrl (metoda delta na log ilorazu)."""
    mv, mc = mean(v), mean(ctrl)
    if mv <= 0 or mc <= 0:
        return None
    se = math.sqrt(sd(v) ** 2 / (len(v) * mv * mv) + sd(ctrl) ** 2 / (len(ctrl) * mc * mc))
    return mv / mc * math.exp(z * se)


def thresholds(rows, group_keys=("bot_nb", "bush_form"), out="total_adrenaline", alpha=0.05, setbacks=SETBACKS,
               margin=NI_MARGIN):
    """Dla każdej grupy: różnica względem kontroli "none" przy każdym odsunięciu i najmniejsze odsunięcie,
    od którego stres nie różni się istotnie od kontroli (reguła projektowa). Drugi próg (threshold_ni): najmniejsze
    odsunięcie, od którego górna granica jednostronnego 95% CI ilorazu do kontroli jest poniżej `margin`
    (test równoważności, ang. non-inferiority)."""
    res = []
    groups = {}
    for r in rows:
        groups.setdefault(tuple(r[k] for k in group_keys), []).append(r)
    for g, rs in sorted(groups.items()):
        ctrl = [float(r[out]) for r in rs if r["label"] == "none"]
        thr = thr_ni = None
        for sb in setbacks:
            v = [float(r[out]) for r in rs if r["label"] == label_of(sb)]
            if not v or not ctrl:
                continue
            t, p = welch(v, ctrl)
            row = dict(zip(group_keys, g))
            up = ratio_upper(v, ctrl)
            row.update({"setback": sb, "mean": round(mean(v), 2), "control_mean": round(mean(ctrl), 2),
                        "ratio_to_control": round(mean(v) / mean(ctrl), 3) if mean(ctrl) else "",
                        "t": round(t, 3), "p": round(p, 5), "significant": p < alpha,
                        "ratio_upper95": round(up, 3) if up is not None else "",
                        "noninferior": up is not None and up < margin})
            res.append(row)
            if thr is None and p >= alpha:
                thr = sb
            if thr_ni is None and up is not None and up < margin:
                thr_ni = sb
        row = dict(zip(group_keys, g))
        row.update({"setback": "threshold", "mean": thr if thr is not None else ">%g" % setbacks[-1],
                    "threshold_ni": thr_ni if thr_ni is not None else ">%g" % setbacks[-1]})
        res.append(row)
    return res


def e3_analysis(rows, delta=0.2):
    """Elastyczności OAT oraz sprawdzenie rankingu S20 < S0 w każdym warunku."""
    base = psm.resolved_params(BASE)
    out = []
    by = {}
    for r in rows:
        by.setdefault((r["bot_nb"], r["bush_junction_distance"], r["label"]), []).append(float(r["total_adrenaline"]))
    labels = sorted({k[2] for k in by})
    for bots in (20, 80):
        for lab in labels:
            s0 = by.get((bots, 0.0, lab))
            s20 = by.get((bots, 20.0, lab))
            if not s0 or not s20:
                continue
            t, p = welch(s20, s0)
            out.append({"bot_nb": bots, "condition": lab, "S0_mean": round(mean(s0), 1), "S20_mean": round(mean(s20), 1),
                        "S20_lt_S0": mean(s20) < mean(s0), "t": round(t, 3), "p": round(p, 5)})
    el = []
    for bots in (20, 80):
        for sb in (0.0, 20.0):
            b = by.get((bots, sb, "base"))
            for n in E3_PARAMS:
                lo, hi = by.get((bots, sb, n + "-")), by.get((bots, sb, n + "+"))
                if not (b and lo and hi):
                    continue
                x0 = (1 - base[n]) if n in psm.RATE_PARAMS else base[n]
                dx = 2 * delta * x0
                el.append({"bot_nb": bots, "setback": sb,
                           "parameter": n + (" (1 - c)" if n in psm.RATE_PARAMS else ""),
                           "elasticity_total_adrenaline": round(((mean(hi) - mean(lo)) / mean(b)) / (dx / x0), 3)
                           if mean(b) else ""})
    return out, el


def write(path, rows):
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("which", nargs="+", choices=["e1", "e1b", "e1h", "e2", "e2r", "e3"])
    ap.add_argument("--reps", type=int, default=None, help="powtórzenia (domyślnie: e1 50, e1b 5, e1h 30, e2 10, e2r 10, e3 30)")
    ap.add_argument("--cycles", type=int, default=10000)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--out", default="wyniki_PSM_UDI")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    prog = lambda i, n: print("\r  %d/%d" % (i, n), end="", file=sys.stderr, flush=True)
    for which in a.which:
        t0 = time.time()
        print("==", which, file=sys.stderr)
        if which == "e1":
            plan = e1_plan(a.reps or 50)
            rows = psm.run_plan(plan, a.cycles, BASE, None, prog, a.jobs)
            write(os.path.join(a.out, "e1_runs.csv"), rows)
            write(os.path.join(a.out, "e1_summary.csv"),
                  summarize(rows, ["bot_nb", "bush_form", "label"], extra=["setback_real", "bush_area"]))
            write(os.path.join(a.out, "e1_threshold.csv"), thresholds(rows))
        elif which == "e1b":
            plan = e1_plan(a.reps or 5, visitors=[50], networks=range(2, 12))
            rows = psm.run_plan(plan, a.cycles, BASE, None, prog, a.jobs)
            write(os.path.join(a.out, "e1b_runs.csv"), rows)
            write(os.path.join(a.out, "e1b_summary.csv"),
                  summarize(rows, ["bush_form", "label"], extra=["setback_real"]))
            write(os.path.join(a.out, "e1b_summary_by_network.csv"),
                  summarize(rows, ["park_seed", "bush_form", "label"], outs=["total_adrenaline"]))
            write(os.path.join(a.out, "e1b_threshold.csv"), thresholds(rows, ("bush_form",)))
        elif which == "e2":
            plan = e1_plan(a.reps or 10, visitors=[20, 80])
            rows = psm.run_plan(plan, a.cycles, BASE, None, prog, a.jobs, isovist=True)
            write(os.path.join(a.out, "e2_runs.csv"), rows)
            write(os.path.join(a.out, "e2_summary.csv"),
                  summarize(rows, ["bot_nb", "bush_form", "label"],
                            outs=["total_adrenaline", "total_vigilance", "isovist_area_mean", "isovist_blocked_mean",
                                  "rho_area_adrenaline", "rho_area_vigilance", "rho_blocked_adrenaline"]))
        elif which == "e1h":
            plan = e1h_plan(a.reps or 30)
            rows = psm.run_plan(plan, a.cycles, BASE, None, prog, a.jobs)
            write(os.path.join(a.out, "e1h_runs.csv"), rows)
            write(os.path.join(a.out, "e1h_summary.csv"),
                  summarize(rows, ["hall_multiplier", "bush_form", "label"], extra=["setback_real"]))
            write(os.path.join(a.out, "e1h_threshold.csv"),
                  thresholds(rows, ("hall_multiplier", "bush_form"), setbacks=SETBACKS_H))
        elif which == "e2r":
            rows = []
            for tag, radius in ISOVIST_RADII:
                plan = [(dict(o, isovist_radius=radius), sd_, lab) for o, sd_, lab in e1_plan(a.reps or 10, visitors=[20, 80])]
                rs = psm.run_plan(plan, a.cycles, BASE, None, prog, a.jobs, isovist=True)
                for r in rs:
                    r["isovist_range"] = tag
                rows += rs
                write(os.path.join(a.out, "e2r_runs.csv"), rows)
            write(os.path.join(a.out, "e2r_summary.csv"),
                  summarize(rows, ["isovist_range", "bot_nb", "bush_form", "label"],
                            outs=["total_adrenaline", "isovist_area_mean", "isovist_blocked_mean",
                                  "rho_area_adrenaline", "rho_area_vigilance", "rho_blocked_adrenaline"]))
        elif which == "e3":
            plan = e3_plan(a.reps or 30)
            rows = psm.run_plan(plan, a.cycles, BASE, None, prog, a.jobs)
            write(os.path.join(a.out, "e3_runs.csv"), rows)
            rank, el = e3_analysis(rows)
            write(os.path.join(a.out, "e3_ranking.csv"), rank)
            write(os.path.join(a.out, "e3_elasticity.csv"), el)
        print("\n  %s: %.0f s" % (which, time.time() - t0), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
