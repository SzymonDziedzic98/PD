"""
Wykresy do wyników udi_experiments.py (wymaga matplotlib: pip install matplotlib).

    python udi_figures.py wyniki_PSM_UDI
Zapisuje fig_e1_setback.png/svg, fig_e1b_networks.png/svg, fig_e2_isovist.png/svg, fig_e3_elasticity.png/svg.
"""

import csv
import os
import sys

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# kolejność kategorii stała (odwiedzający 20 / 50 / 80); kolor + kształt znacznika + etykieta bezpośrednia
COLORS = {20: "#2a78d6", 50: "#eb6834", 80: "#1baf7a"}
MARKERS = {20: "o", 50: "s", 80: "^"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
SETBACKS = [0.0, 5.0, 10.0, 15.0, 20.0]
FORM_PL = {"clumps": "Zwarte kępy", "band": "Pas wzdłuż ścieżki"}


def read(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def save(fig, out, name):
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(out, name + "." + ext), dpi=200, bbox_inches="tight")
    plt.close(fig)


def fig_e1(out):
    rows = read(os.path.join(out, "e1_summary.csv"))
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8), sharey=True)
    for ax, form in zip(axes, ["clumps", "band"]):
        style(ax)
        ends = []
        for v in (20, 50, 80):
            rs = {r["label"]: r for r in rows if r["bush_form"] == form and int(r["bot_nb"]) == v}
            xs = [float(rs["%g" % s]["setback_real_mean"]) for s in SETBACKS if "%g" % s in rs]
            ys = [float(rs["%g" % s]["total_adrenaline_mean"]) for s in SETBACKS if "%g" % s in rs]
            ci = [float(rs["%g" % s]["total_adrenaline_ci95"]) for s in SETBACKS if "%g" % s in rs]
            ax.errorbar(xs, ys, yerr=ci, color=COLORS[v], marker=MARKERS[v], markersize=6, linewidth=2,
                        capsize=3, elinewidth=1)
            if "none" in rs:
                c = float(rs["none"]["total_adrenaline_mean"])
                ax.axhline(c, color=COLORS[v], linewidth=1, linestyle=(0, (4, 3)))
            ends.append((ys[-1], v, xs[-1]))
        ax.set_title(FORM_PL[form], fontsize=11, color=INK, loc="left")
        ax.set_xlabel("Faktyczny odstęp krzewów od skrzyżowania (m)", fontsize=9, color=MUTED)
        ax.set_xlim(-1, 26)
        # etykiety bezpośrednie na końcu linii, rozsunięte w pionie
        lo, hi = ax.get_ylim()
        gap = 0.09 * (hi - lo)
        last = None
        for y, v, x in sorted(ends):
            y = y if last is None else max(y, last + gap)
            ax.annotate("%d os." % v, (x, y), xytext=(8, 0), textcoords="offset points",
                        ha="left", va="center", fontsize=9, color=INK)
            last = y
    axes[0].set_ylabel("Σ adrenaliny phantoma (średnia ± 95% CI)", fontsize=9, color=MUTED)
    fig.text(0.01, -0.04, "Linie przerywane: ta sama powierzchnia krzewów wzdłuż ścieżek, poza strefą skrzyżowań "
             "(kontrola). Etykieta: liczba odwiedzających.", fontsize=8, color=MUTED)
    save(fig, out, "fig_e1_setback")


def fig_e1b(out):
    p = os.path.join(out, "e1b_summary_by_network.csv")
    if not os.path.exists(p):
        return
    rows = read(p)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    nets = sorted({int(r["park_seed"]) for r in rows})
    for ax, form in zip(axes, ["clumps", "band"]):
        style(ax)
        for n in nets:
            rs = {r["label"]: r for r in rows if r["bush_form"] == form and int(r["park_seed"]) == n}
            c = float(rs["none"]["total_adrenaline_mean"]) if "none" in rs else None
            ys = [float(rs["%g" % s]["total_adrenaline_mean"]) / c if c else None for s in SETBACKS]
            ax.plot(SETBACKS, ys, color="#2a78d6", alpha=0.45, linewidth=1.5, marker="o", markersize=4)
        ax.axhline(1.0, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
        ax.set_title(FORM_PL[form], fontsize=11, color=INK, loc="left")
        ax.set_xlabel("Zadany odstęp od skrzyżowania (m)", fontsize=9, color=MUTED)
    axes[0].set_ylabel("Σ adrenaliny / kontrola", fontsize=9, color=MUTED)
    fig.text(0.01, -0.04, "Każda linia to jedna z %d sieci ścieżek, 50 odwiedzających; 1 = poziom kontroli." % len(nets),
             fontsize=8, color=MUTED)
    save(fig, out, "fig_e1b_networks")


def fig_e2(out):
    p = os.path.join(out, "e2_summary.csv")
    if not os.path.exists(p):
        return
    rows = read(p)
    fig, ax = plt.subplots(figsize=(5.5, 4))
    style(ax)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    for v in (20, 80):
        rs = [r for r in rows if int(r["bot_nb"]) == v]
        xs = [float(r["isovist_area_mean_mean"]) for r in rs]
        ys = [float(r["total_adrenaline_mean"]) for r in rs]
        ax.scatter(xs, ys, color=COLORS[v], marker=MARKERS[v], s=40, edgecolor="white", linewidth=1,
                   label="%d odwiedzających" % v, zorder=3)
    for form, name in FORM_PL.items():
        xs = [float(r["isovist_area_mean_mean"]) for r in rows if r["bush_form"] == form]
        if xs:
            ax.annotate(name, (sum(xs) / len(xs), 1), xycoords=("data", "axes fraction"), ha="center", va="top",
                        fontsize=9, color=MUTED)
    ax.set_xlabel("Średnie pole izowisty wzdłuż ścieżek (m²)", fontsize=9, color=MUTED)
    ax.set_ylabel("Σ adrenaliny phantoma (średnia)", fontsize=9, color=MUTED)
    ax.legend(frameon=False, fontsize=9)
    ax.set_title("Widoczność a stres (warianty E1)", fontsize=11, color=INK, loc="left")
    save(fig, out, "fig_e2_isovist")


def fig_e3(out):
    p = os.path.join(out, "e3_elasticity.csv")
    if not os.path.exists(p):
        return
    rows = [r for r in read(p) if float(r["setback"]) == 0.0]
    params = []
    for r in rows:
        if r["parameter"] not in params:
            params.append(r["parameter"])
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    style(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    h = 0.36
    for k, v in enumerate((20, 80)):
        vals = [next((float(r["elasticity_total_adrenaline"]) for r in rows
                      if r["parameter"] == pn and int(r["bot_nb"]) == v and r["elasticity_total_adrenaline"] != ""), 0.0)
                for pn in params]
        ys = [i + (k - 0.5) * (h + 0.04) for i in range(len(params))]
        ax.barh(ys, vals, height=h, color=COLORS[v], label="%d odwiedzających" % v, edgecolor="white", linewidth=1)
    ax.set_yticks(range(len(params)))
    ax.set_yticklabels(params, fontsize=9, color=INK)
    ax.axvline(0, color=MUTED, linewidth=1)
    ax.set_xlabel("Elastyczność Σ adrenaliny (OAT ±20%)", fontsize=9, color=MUTED)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    ax.set_title("Wrażliwość stałych (krzewy przy skrzyżowaniach)", fontsize=11, color=INK, loc="left")
    fig.text(0.01, -0.04, "Brak słupka = elastyczność 0 (kortyzol nie wpływa zwrotnie na adrenalinę).", fontsize=8, color=MUTED)
    save(fig, out, "fig_e3_elasticity")


PARK_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
PARK_MARKERS = ["o", "s", "^", "D", "v"]
PARK_PL = {"park_staszica": "Staszica", "park_poludniowy": "Południowy", "park_grabiszynski": "Grabiszyński",
           "park_zachodni": "Zachodni", "park_szczytnicki": "Szczytnicki"}


def fig_parks(out):
    p = os.path.join(out, "parki_threshold.csv")
    if not os.path.exists(p):
        return
    rows = [r for r in read(p) if r["setback"] != "threshold"]
    parks = [k for k in PARK_PL if any(r["park"] == k for r in rows)]
    mults = sorted({float(r["mult"]) for r in rows})
    fig, axes = plt.subplots(2, len(mults), figsize=(3.3 * len(mults), 6.4), sharex=True, sharey=True)
    for i, form in enumerate(["clumps", "band"]):
        for j, mult in enumerate(mults):
            ax = axes[i][j]
            style(ax)
            ax.set_yscale("log")
            ax.axhline(1.0, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
            for k, park in enumerate(parks):
                rs = sorted((r for r in rows if r["park"] == park and r["bush_form"] == form and float(r["mult"]) == mult),
                            key=lambda r: float(r["setback"]))
                ax.plot([float(r["setback"]) for r in rs], [float(r["ratio_to_control"]) for r in rs],
                        color=PARK_COLORS[k], marker=PARK_MARKERS[k], markersize=5, linewidth=1.8,
                        label=PARK_PL[park] if (i, j) == (0, 0) else None)
            if i == 0:
                ax.set_title("%g× gęstości z E1" % mult, fontsize=10, color=INK, loc="left")
            if j == 0:
                ax.set_ylabel("%s\nΣ adrenaliny / kontrola" % FORM_PL[form], fontsize=9, color=MUTED)
            if i == 1:
                ax.set_xlabel("Odstęp od skrzyżowania (m)", fontsize=9, color=MUTED)
            ax.set_xticks(SETBACKS)
    ax0 = axes[0][0]
    ax0.set_yticks([0.5, 1, 2, 5, 10, 20])
    ax0.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _p: "%g" % v))
    fig.legend(loc="upper center", ncol=len(parks), frameon=False, fontsize=9, bbox_to_anchor=(0.5, 1.03))
    fig.text(0.01, -0.02, "Parki z OSM, średnia frekwencja (ok. 20 os./km ścieżek), 30 phantomów na punkt. "
             "Linia przerywana = kontrola (ta sama powierzchnia poza strefą 15 m od skrzyżowań). Oś pionowa logarytmiczna.",
             fontsize=8, color=MUTED)
    save(fig, out, "fig_parki_setback")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "wyniki_PSM_UDI"
    fig_e1(out)
    fig_e1b(out)
    fig_e2(out)
    fig_e3(out)
    fig_parks(out)
    print("zapisano wykresy w", out)
