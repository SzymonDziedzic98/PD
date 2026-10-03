"""
Schemat dla projektantów (recenzja UDI): jedno skrzyżowanie ze strefą odsunięcia 15/20 m i zalecanym układem krzewów,
plus wycinek Parku Grabiszyńskiego (sieć po poprawkach, nasadzenia 1× gęstości, kępy 20 m od skrzyżowań).
Wymaga matplotlib i shapely.

    python udi_diagram.py --out DIR [--lang en|pl]
"""

import argparse
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import psm
import udi_experiments as ue
import udi_parks as up

INK = "#1f2328"
MUTED = "#57606a"
PATH = "#b8b2a7"
PATH_EDGE = "#8c857a"
ZONE_IN = "#f3c9a8"      # 0–15 m: bez krzewów zasłaniających widok
ZONE_OUT = "#fbe7d6"     # 15–20 m: strefa przejściowa
BUSH = "#3f7d3a"
BUSH_BAD = "#b0413e"
PATH_OFF = 1.0          # m, krawędź krzewu od osi ścieżki (jak bush_path_offset w modelu)

TXT = {
    "en": {
        "title_a": "A  One junction: where shrubs go",
        "title_b": "B  Park Grabiszyński, Wrocław (excerpt)",
        "zone_in": "0–15 m: keep sightlines open\n(lawn, low planting, tree trunks;\nno view-blocking shrubs)",
        "zone_out": "15–20 m: minimum setback 15 m,\n20 m where every junction must be clear",
        "bush_ok": "Shrub clumps or bands ≥ 20 m from\nthe junction, ≥ 1 m from the path centreline",
        "bush_bad": "Shrubs in the junction corner\nraised simulated stress\n7–12× (generated park),\n1.2–8× (five real parks)",
        "social": "social zone of the visitor\nmodel: 3.6 m × 4 = 14.4 m",
        "leg_zone_in": "0–15 m from a junction",
        "leg_zone_out": "15–20 m from a junction",
        "leg_bush": "shrubs (1× density, clumps, 20 m setback)",
        "leg_path": "paths (OSM, simplified)",
        "scale": "50 m",
    },
    "pl": {
        "title_a": "A  Jedno skrzyżowanie: gdzie sadzić krzewy",
        "title_b": "B  Park Grabiszyński, Wrocław (wycinek)",
        "zone_in": "0–15 m: widok otwarty\n(trawnik, niskie nasadzenia, pnie drzew;\nbez krzewów zasłaniających widok)",
        "zone_out": "15–20 m: odsunięcie minimum 15 m,\n20 m, gdy każde skrzyżowanie ma być pewne",
        "bush_ok": "Kępy albo pasy krzewów ≥ 20 m\nod skrzyżowania, ≥ 1 m od osi ścieżki",
        "bush_bad": "Krzewy w narożniku skrzyżowania\npodniosły stres w modelu\n7–12× (park generowany),\n1,2–8× (pięć parków rzeczywistych)",
        "social": "strefa społeczna w modelu:\n3,6 m × 4 = 14,4 m",
        "leg_zone_in": "0–15 m od skrzyżowania",
        "leg_zone_out": "15–20 m od skrzyżowania",
        "leg_bush": "krzewy (gęstość 1×, kępy, odsunięcie 20 m)",
        "leg_path": "ścieżki (OSM, po uproszczeniu)",
        "scale": "50 m",
    },
}


def fill(ax, geom, **kw):
    geoms = getattr(geom, "geoms", [geom])
    for g in geoms:
        if g.is_empty:
            continue
        ax.add_patch(MplPolygon(list(g.exterior.coords), closed=True, **kw))
        for hole in g.interiors:
            ax.add_patch(MplPolygon(list(hole.coords), closed=True, facecolor="white", edgecolor="none",
                                    zorder=kw.get("zorder", 1) + 0.01))


def panel_junction(ax, t):
    arms = [0, 95, 200, 275]          # kąty ramion (stopnie), typowe skrzyżowanie parkowe
    L = 42.0
    lines = [LineString([(0, 0), (L * math.cos(math.radians(a)), L * math.sin(math.radians(a)))]) for a in arms]
    z20 = Point(0, 0).buffer(20, 64)
    z15 = Point(0, 0).buffer(15, 64)
    fill(ax, z20, facecolor=ZONE_OUT, edgecolor="none", zorder=1)
    fill(ax, z15, facecolor=ZONE_IN, edgecolor="none", zorder=1.5)
    for r, ls in ((15, "-"), (20, (0, (4, 3)))):
        ax.add_patch(plt.Circle((0, 0), r, fill=False, edgecolor=MUTED, linewidth=1, linestyle=ls, zorder=2))
    # ścieżki jako osie, tak jak w modelu (agenci chodzą po liniach, ścieżka nie ma szerokości)
    for l in lines:
        xs, ys = zip(*l.coords)
        ax.plot(xs, ys, color=PATH_EDGE, linewidth=1.6, solid_capstyle="round", zorder=3)
    # zalecane kępy: wzdłuż ramion, krawędź 20 m od węzła, 1 m od osi ścieżki
    rb = 4.0
    for a in arms:
        ux, uy = math.cos(math.radians(a)), math.sin(math.radians(a))
        nx, ny = -uy, ux
        if a == arms[3]:   # pas wzdłuż ścieżki, 2 × 20 m, też od 20 m
            for s in (1, -1):
                o1, o2 = PATH_OFF, PATH_OFF + 2
                q = [(20 * ux + s * o1 * nx, 20 * uy + s * o1 * ny), (40 * ux + s * o1 * nx, 40 * uy + s * o1 * ny),
                     (40 * ux + s * o2 * nx, 40 * uy + s * o2 * ny), (20 * ux + s * o2 * nx, 20 * uy + s * o2 * ny)]
                ax.add_patch(MplPolygon(q, closed=True, facecolor=BUSH, edgecolor="white", linewidth=1.2, zorder=4))
            continue
        for s in (1, -1):
            for along in (20 + rb, 20 + rb + 11):
                off = PATH_OFF + rb
                ax.add_patch(plt.Circle((along * ux + s * off * nx, along * uy + s * off * ny), rb,
                                        facecolor=BUSH, edgecolor="white", linewidth=1.2, zorder=4))
    # przykład złego miejsca: kępa w narożniku przy węźle, przekreślona
    bis = math.radians((arms[0] + arms[1]) / 2)
    cx, cy = 8.5 * math.cos(bis), 8.5 * math.sin(bis)
    ax.add_patch(plt.Circle((cx, cy), rb, facecolor="none", edgecolor=BUSH_BAD, linewidth=1.6,
                            linestyle=(0, (3, 2)), zorder=4))
    ax.plot([cx - 3, cx + 3], [cy - 3, cy + 3], color=BUSH_BAD, linewidth=1.6, zorder=5)
    ax.plot([cx - 3, cx + 3], [cy + 3, cy - 3], color=BUSH_BAD, linewidth=1.6, zorder=5)
    # wymiary
    ang = math.radians(228)
    for r in (15, 20):
        ax.annotate("", xy=(r * math.cos(ang), r * math.sin(ang)), xytext=(0, 0),
                    arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=0.9, shrinkA=0, shrinkB=0), zorder=6)
    bb = dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.85)
    ax.text(15 * math.cos(ang) - 2.2, 15 * math.sin(ang) + 0.8, "15 m", fontsize=8.5, color=INK, ha="right", zorder=6, bbox=bb)
    ax.text(20 * math.cos(ang) - 1.5, 20 * math.sin(ang) - 2.2, "20 m", fontsize=8.5, color=INK, ha="right", zorder=6, bbox=bb)
    ax.plot([0], [0], marker="o", markersize=3.5, color=INK, zorder=6)
    # opisy z odnośnikami
    kw = dict(fontsize=8, color=INK, zorder=7, va="center")
    ax.annotate(t["zone_in"], xy=(-6, -6), xytext=(-47, -34), ha="left",
                arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.7), **kw)
    ax.annotate(t["zone_out"], xy=(12.5, -13), xytext=(8, -38), ha="left",
                arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.7), **kw)
    bx = (20 + rb) * math.cos(math.radians(arms[0])) + 0.0
    by = (PATH_OFF + rb) + 4
    ax.annotate(t["bush_ok"], xy=(bx, by), xytext=(20, 36), ha="left",
                arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.7), **kw)
    ax.annotate(t["bush_bad"], xy=(cx - 2.5, cy + 3), xytext=(-47, 36), ha="left",
                arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.7), **kw)
    ax.text(-47, 20, t["social"], fontsize=7.5, color=MUTED, ha="left", va="center", zorder=7)
    ax.set_xlim(-48, 48)
    ax.set_ylim(-44, 44)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(t["title_a"], fontsize=10.5, color=INK, loc="left")


def panel_park(ax, t, window=(-60, 260, -120, 200)):
    path = os.path.join(up.PARKS if hasattr(up, "PARKS") else "/mnt/project-files/doktorat/parki_osm",
                        "park_grabiszynski.geojson")
    roads = up.load(path)[0]
    nj, _l = up.park_stats(path)
    o = ue.cell(20.0, "clumps", 0, {"planting_seed": 1, "bush_area_total": up.REF_DENSITY * nj,
                                    "bush_setback_scope": "all"})
    obs, _info = psm.plant_bushes(roads, psm.resolved_params(dict(ue.BASE, **o)))
    x0, x1, y0, y1 = window
    J = [c for c, _a in psm.junctions(roads)]
    z15 = unary_union([Point(c).buffer(15, 32) for c in J])
    z20 = unary_union([Point(c).buffer(20, 32) for c in J])
    clip = Point((x0 + x1) / 2, (y0 + y1) / 2).buffer(1e4).intersection(
        LineString([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]).envelope)
    fill(ax, z20.intersection(clip), facecolor=ZONE_OUT, edgecolor="none", zorder=1)
    fill(ax, z15.intersection(clip), facecolor=ZONE_IN, edgecolor="none", zorder=1.5)
    for r in roads:
        xs, ys = zip(*r)
        ax.plot(xs, ys, color=PATH_EDGE, linewidth=1.6, solid_capstyle="round", zorder=3)
    for rings in obs:
        xs, ys = zip(*rings[0])
        if max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1:
            continue
        ax.fill(xs, ys, color=BUSH, zorder=4, linewidth=0)
    for c in J:
        if x0 <= c[0] <= x1 and y0 <= c[1] <= y1:
            ax.plot(c[0], c[1], marker="o", markersize=2.2, color=INK, zorder=5)
    # podziałka
    sx, sy = x1 - 70, y0 + 12
    ax.plot([sx, sx + 50], [sy, sy], color=INK, linewidth=2, solid_capstyle="butt", zorder=6)
    ax.text(sx + 25, sy + 5, t["scale"], fontsize=8, color=INK, ha="center", zorder=6)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#d0d7de")
    ax.set_title(t["title_b"], fontsize=10.5, color=INK, loc="left")
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=ZONE_IN), plt.Rectangle((0, 0), 1, 1, facecolor=ZONE_OUT),
               plt.Rectangle((0, 0), 1, 1, facecolor=BUSH), plt.Line2D([0], [0], color=PATH_EDGE, linewidth=1.6)]
    ax.legend(handles, [t["leg_zone_in"], t["leg_zone_out"], t["leg_bush"], t["leg_path"]], loc="upper left",
              bbox_to_anchor=(0.0, -0.02), ncol=2, frameon=False, fontsize=7.5)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=".")
    ap.add_argument("--lang", default="en", choices=["en", "pl"])
    ap.add_argument("--window", type=float, nargs=4, default=None, help="wycinek parku: x0 x1 y0 y1 (m)")
    a = ap.parse_args(argv)
    t = TXT[a.lang]
    plt.rcParams["font.family"] = "DejaVu Sans"
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.6), gridspec_kw={"width_ratios": [1.05, 1]})
    panel_junction(axes[0], t)
    if a.window:
        panel_park(axes[1], t, tuple(a.window))
    else:
        panel_park(axes[1], t)
    fig.tight_layout()
    name = "fig_schemat_odsuniecia_%s" % a.lang
    for ext in ("svg", "png"):
        fig.savefig(os.path.join(a.out, name + "." + ext), dpi=200, bbox_inches="tight", facecolor="white")
    print("zapisano", os.path.join(a.out, name))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
