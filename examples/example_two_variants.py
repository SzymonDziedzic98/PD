"""
Illustrative example of the SoftwareX paper (section 3, Fig. 3): two planting variants with the same shrub area.
Variant A: shrub clumps at junction corners (0 m setback). Variant B: the same clumps 20 m from the junctions.
Generated park, 50 bots, 10 runs of 10,000 cycles per variant.
Run from the repository root: python examples/example_two_variants.py
Writes examples/output/example_two_variants.csv and Figure3_two_variants.png/.svg (the figure needs matplotlib).
"""
import json, statistics as st, sys, time, csv, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import psm

OUT = os.path.join(HERE, "output")
os.makedirs(OUT, exist_ok=True)
BASE = {"planting": "controlled", "bush_area_total": 1500.0, "bush_junction_share": 1.0,
        "park_seed": 1, "bot_nb": 50, "bot_graph": "plain", "bush_form": "clumps"}
VARIANTS = {"A": {"bush_junction_distance": 0.0}, "B": {"bush_junction_distance": 20.0}}
REPS, CYCLES = 10, 10000

res, geo = {}, {}
for name, ov in VARIANTS.items():
    tot, edge_acc, secs = [], None, []
    for r in range(REPS):
        t0 = time.time()
        m = psm.make_model(dict(BASE, **ov), seed=r + 1, cycles=CYCLES)
        m.run(CYCLES)
        secs.append(time.time() - t0)
        tot.append(m.metrics()["total_adrenaline"])
        if edge_acc is None:
            edge_acc = [[0, 0.0] for _ in m.edge_stats]
        for i, s in enumerate(m.edge_stats):
            edge_acc[i][0] += s[0]; edge_acc[i][1] += s[1]
    geo[name] = json.loads(m.network_json())
    res[name] = {"total_adrenaline": tot, "seconds": secs,
                 "edge_mean_adrenaline": [a / v if v >= 30 else None for v, a in edge_acc]}
    print(name, "Σa mean %.0f sd %.0f | %.1f s/run" % (st.mean(tot), st.stdev(tot), st.mean(secs)))

with open(os.path.join(OUT, "example_two_variants.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["variant", "seed", "total_adrenaline", "seconds"])
    for n in res:
        for i, (a, s) in enumerate(zip(res[n]["total_adrenaline"], res[n]["seconds"])):
            w.writerow([n, i + 1, round(a, 2), round(s, 2)])

import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Polygon
vals = [v for n in res for v in res[n]["edge_mean_adrenaline"] if v is not None]
vmax = sorted(vals)[int(0.98 * len(vals))]
fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), constrained_layout=True)
titles = {"A": "A: shrubs at junctions (0 m)", "B": "B: same shrub area, 20 m setback"}
for ax, n in zip(axes, res):
    g = geo[n]
    for poly in g["obstacles"]:
        ax.add_patch(Polygon(poly, closed=True, fc="#9bc59d", ec="none"))
    segs, cols = [], []
    for pts, v in zip(g["edges"], res[n]["edge_mean_adrenaline"]):
        for p, q in zip(pts[:-1], pts[1:]):
            segs.append([p, q]); cols.append(0.0 if v is None else v)
    lc = LineCollection(segs, array=cols, cmap="magma_r", linewidths=2.2)
    lc.set_clim(0, vmax); ax.add_collection(lc)
    ax.set_xlim(g["bbox"][0], g["bbox"][2]); ax.set_ylim(g["bbox"][1], g["bbox"][3])
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title("%s\nΣ adrenaline %.0f ± %.0f (n = %d)" % (titles[n], st.mean(res[n]["total_adrenaline"]),
                 st.stdev(res[n]["total_adrenaline"]), REPS), fontsize=10)
fig.colorbar(lc, ax=axes, shrink=0.8, label="mean phantom adrenaline on path segment")
for ext in ("png", "svg"):
    fig.savefig(os.path.join(OUT, "Figure3_two_variants." + ext), dpi=300)
