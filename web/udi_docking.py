"""
Docking GAMA ↔ Python (recenzja UDI, punkt 4): te same wejścia (SHP) i te same parametry w obu implementacjach.

Scenariusze (pliki SHP Parku Staszica ze schematów A/B nie są dostępne, więc Study 1 odtwarzamy na sieci Staszica z OSM):
  S1_krzewy  Staszica (po_poprawkach), krzewy przy skrzyżowaniach (kępy, 0 m, gęstość 1), bez awersji tras
  S1_kontrola Staszica, ta sama powierzchnia krzewów wzdłuż ścieżek poza strefą skrzyżowań, bez awersji
  E1_awersja park generowany (seed 1), kępy 0 m, awersja tras β = 5 (komórka E1)
  E1_awersja_plain  jak E1_awersja, ale boty na grafie bez wag strachu (ustawienie z wyników artykułu)
  S1_krzewy_10ph    układ S1_krzewy, awersja β = 5, 10 phantomów z osobną pamięcią strachu, boty bez wag (jak Study 3)
Wspólne: 50 botów, 10 000 cykli po 0,3 s, strefy Halla ×4. Trzy pierwsze scenariusze: 1 phantom, boty na grafie ważonym
i wspólna pamięć strachu (dawne zachowanie GAML: w kopii modelu bots_plain_graph = false, move_by_length = false).
Nowe scenariusze: move_by_length = true (prędkość po długości, wagi strachu tylko do trasy). Przy kilku phantomach
porównanie idzie po średniej z phantomów w przebiegu (phantomy w jednym przebiegu dzielą boty, więc nie są niezależne).

    python udi_docking.py export --out DIR          # SHP + kopie modelu GAMA + plan XML
    python udi_docking.py python --out DIR --reps 30 --jobs 4
    gama-headless.sh DIR/<scen>/plan.xml DIR/<scen>/gama_out   (dla każdego scenariusza)
    python udi_docking.py compare --out DIR
"""

import argparse
import csv
import math
import os
import re
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import psm
import udi_experiments as ue
import udi_parks as up

HERE = os.path.dirname(os.path.abspath(__file__))
GAML = os.path.join(HERE, "..", "models", "Hall_AC_aversion.gaml")
PARKS = "/mnt/project-files/doktorat/parki_osm"
BOTS = 50
CYCLES = 10000
# PUWG 1992 (EPSG:2180); przesunięcie, żeby GAMA nie wzięła współrzędnych za stopnie
PRJ = ('PROJCS["ETRS89 / Poland CS92",GEOGCS["ETRS89",DATUM["European_Terrestrial_Reference_System_1989",'
       'SPHEROID["GRS 1980",6378137,298.257222101]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],'
       'PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",19],'
       'PARAMETER["scale_factor",0.9993],PARAMETER["false_easting",500000],PARAMETER["false_northing",-5300000],'
       'UNIT["metre",1]]')
OFFSET = (360000.0, 360000.0)
COMMON = {"phantom_nb": 1, "bot_nb": BOTS, "bot_graph": "weighted", "fear_scope": "shared", "planting": "default"}

SCENARIOS = {
    "S1_krzewy": {"aversion_strength": 0.0, "move_by_length": False},
    "S1_kontrola": {"aversion_strength": 0.0, "move_by_length": False},
    "E1_awersja": {"aversion_strength": 5.0, "move_by_length": False},
    # po zmianie GAML (boty bez wag strachu, osobna pamięć phantomów): ustawienia z wyników artykułu
    "E1_awersja_plain": {"aversion_strength": 5.0, "bot_graph": "plain", "layout": "E1_awersja"},
    "S1_krzewy_10ph": {"aversion_strength": 5.0, "bot_graph": "plain", "fear_scope": "individual", "phantom_nb": 10,
                       "layout": "S1_krzewy"},
}


def build_layout(name):
    """Model Pythona z właściwym układem -> (odcinki sieci, wielokąty krzewów) w metrach."""
    if name.startswith("S1"):
        path = os.path.join(PARKS, "park_staszica.geojson")
        inputs = up.load(path)
        nj, _length = up.park_stats(path)
        sb = 0.0 if name == "S1_krzewy" else None
        o = ue.cell(sb, "clumps", BOTS, {"planting_seed": 1, "bush_area_total": up.REF_DENSITY * nj,
                                          "bush_setback_scope": "all"})
        m = psm.make_model(dict(ue.BASE, **o), 1, 1, None, inputs)
    else:
        o = ue.cell(0.0, "clumps", BOTS, {"planting_seed": 1, "park_seed": 1})
        m = psm.make_model(dict(ue.BASE, **o), 1, 1)
    return [e.pts for e in m.net.edges], [list(rings) for rings in m.obstacles.polygons], m.planting_info


def write_shp(base, roads, polys):
    import shapefile   # pyshp
    sh = lambda q: [q[0] + OFFSET[0], q[1] + OFFSET[1]]
    with shapefile.Writer(base + "_sciezki", shapeType=shapefile.POLYLINE) as w:
        w.field("id", "N")
        for i, r in enumerate(roads):
            w.line([[sh(q) for q in r]])
            w.record(i)
    with shapefile.Writer(base + "_krzaki", shapeType=shapefile.POLYGON) as w:
        w.field("id", "N")
        for i, rings in enumerate(polys):
            w.poly([[sh(q) for q in ring] for ring in rings])
            w.record(i)
    for suf in ("_sciezki", "_krzaki"):
        with open(base + suf + ".prj", "w") as f:
            f.write(PRJ)


def gaml_copy(src, dst, roads_shp, obst_shp, aversion, bots, bot_graph="weighted", fear_scope="shared", phantoms=1,
              move_by_length=True):
    s = open(src, encoding="utf-8").read()
    s = s.replace('"Staszica_SHP_sciezki_01.shp"', '"%s"' % roads_shp)
    s = s.replace('"Staszica_SHP_krzaki_09.shp"', '"%s"' % obst_shp)
    s = re.sub(r"float aversion_strength <- [0-9.]+;", "float aversion_strength <- %s;" % aversion, s)
    s = re.sub(r"int bot_nb <- [0-9]+;", "int bot_nb <- %d;" % bots, s)
    s = re.sub(r"int phantom_nb <- [0-9]+;", "int phantom_nb <- %d;" % phantoms, s)
    s = re.sub(r"bool bots_plain_graph <- \w+;", "bool bots_plain_graph <- %s;" % str(bot_graph == "plain").lower(), s)
    s = re.sub(r"bool individual_fear <- \w+;", "bool individual_fear <- %s;" % str(fear_scope == "individual").lower(), s)
    s = re.sub(r"bool move_by_length <- \w+;", "bool move_by_length <- %s;" % str(move_by_length).lower(), s)
    open(dst, "w", encoding="utf-8").write(s)


def plan_xml(model_path, reps, seed0=1):
    sims = []
    for r in range(reps):
        sims.append('  <Simulation id="%d" sourcePath="%s" finalStep="%d" experiment="Hall" seed="%d">\n'
                    '    <Parameters/>\n    <Outputs/>\n  </Simulation>' % (r + 1, model_path, CYCLES, seed0 + r))
    return "<Experiment_plan>\n%s\n</Experiment_plan>\n" % "\n".join(sims)


def export(out, reps, names=None):
    rows = []
    for name in names or SCENARIOS:
        extra = SCENARIOS[name]
        d = os.path.abspath(os.path.join(out, name))
        os.makedirs(os.path.join(d, "results"), exist_ok=True)
        lay = extra.get("layout", name)
        roads, polys, info = build_layout(lay)
        write_shp(os.path.join(d, name), roads, polys)
        model = os.path.join(d, "Hall_AC_%s.gaml" % name)
        gaml_copy(GAML, model, name + "_sciezki.shp", name + "_krzaki.shp", extra["aversion_strength"], BOTS,
                  extra.get("bot_graph", "weighted"), extra.get("fear_scope", "shared"), extra.get("phantom_nb", 1),
                  extra.get("move_by_length", True))
        with open(os.path.join(d, "plan.xml"), "w") as f:
            f.write(plan_xml(model, reps))
        rows.append({"scenario": name, "edges": len(roads), "bushes": len(polys),
                     "bush_area": round(sum(psm.ring_area(p[0]) for p in polys), 1),
                     "aversion_strength": extra["aversion_strength"]})
        print(name, len(roads), "odcinków,", len(polys), "krzewów", file=sys.stderr)
    path = os.path.join(out, "docking_scenariusze.csv")
    if names and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r["scenario"] not in names] + rows
    ue.write(path, rows)


def _py_run(job):
    name, d, seed = job
    with open(os.path.join(d, name + "_sciezki.shp"), "rb") as f:
        rd = f.read()
    with open(os.path.join(d, name + "_krzaki.shp"), "rb") as f:
        od = f.read()
    inputs = psm.load_inputs(rd, od, "r.shp", "o.shp")
    params = dict(COMMON, **{k: v for k, v in SCENARIOS[name].items() if k not in ("layout", "move_by_length")})
    m = psm.make_model(params, seed, CYCLES, None, inputs).run()
    return [{"scenario": name, "impl": "python", "seed": seed, "phantom": i,
             "total_adrenaline": round(ph.total_adrenaline, 4), "total_cortisol": round(ph.total_cortisol, 4),
             "total_vigilance": round(ph.total_vigilance, 4)} for i, ph in enumerate(m.phantoms)]


def run_python(out, reps, jobs, names=None):
    names = names or list(SCENARIOS)
    work = [(name, os.path.abspath(os.path.join(out, name)), 1 + r) for name in names for r in range(reps)]
    with Pool(jobs) as pool:
        rows = [r for rs in pool.map(_py_run, work) for r in rs]
    path = os.path.join(out, "docking_python_runs.csv")
    if os.path.exists(path):   # dopisz: zachowaj wcześniejsze scenariusze
        with open(path, encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r["scenario"] not in names] + rows
    ue.write(path, rows)


def read_gama(out):
    rows = []
    for name in SCENARIOS:
        p = os.path.join(out, name, "results", "summary.csv")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            for i, r in enumerate(csv.DictReader(f)):
                rows.append({"scenario": name, "impl": "gama", "seed": "", "phantom": i,
                             **{k: float(r[k]) for k in ("total_adrenaline", "total_cortisol", "total_vigilance")}})
    return rows


def compare(out, margin=0.10):
    """Średnie ± 95% CI obu implementacji, iloraz GAMA/Python z 90% CI (metoda delta na log) i test równoważności
    TOST na ilorazie: równoważne, gdy 90% CI mieści się w [1/(1+margin), 1+margin]."""
    rows = read_gama(out)
    with open(os.path.join(out, "docking_python_runs.csv"), encoding="utf-8") as f:
        rows += [dict(r) for r in csv.DictReader(f)]
    ue.write(os.path.join(out, "docking_runs.csv"), rows)
    res = []
    for name in SCENARIOS:
        nph = SCENARIOS[name].get("phantom_nb", 1)
        for k in ("total_adrenaline", "total_vigilance"):
            g = [float(r[k]) for r in rows if r["scenario"] == name and r["impl"] == "gama"]
            p = [float(r[k]) for r in rows if r["scenario"] == name and r["impl"] == "python"]
            if nph > 1:   # średnia z phantomów w przebiegu (GAMA zapisuje phantomy jednego przebiegu po kolei)
                g = [ue.mean(g[i:i + nph]) for i in range(0, len(g) - nph + 1, nph)]
                p = [ue.mean(p[i:i + nph]) for i in range(0, len(p) - nph + 1, nph)]
            if len(g) < 2 or len(p) < 2:
                continue
            mg, mp = ue.mean(g), ue.mean(p)
            se = math.sqrt(ue.sd(g) ** 2 / (len(g) * mg * mg) + ue.sd(p) ** 2 / (len(p) * mp * mp))
            ratio = mg / mp
            lo, hi = ratio * math.exp(-1.645 * se), ratio * math.exp(1.645 * se)
            t, pv = ue.welch(g, p)
            res.append({"scenario": name, "output": k, "n_gama": len(g), "n_python": len(p),
                        "gama_mean": round(mg, 2), "gama_ci95": round(1.96 * ue.sd(g) / math.sqrt(len(g)), 2),
                        "python_mean": round(mp, 2), "python_ci95": round(1.96 * ue.sd(p) / math.sqrt(len(p)), 2),
                        "ratio_gama_python": round(ratio, 3), "ratio_ci90_lo": round(lo, 3), "ratio_ci90_hi": round(hi, 3),
                        "welch_p": round(pv, 4),
                        "equivalent_10pct": lo > 1 / (1 + margin) and hi < 1 + margin})
    ue.write(os.path.join(out, "docking_summary.csv"), res)
    for r in res:
        print(r)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["export", "python", "compare"])
    ap.add_argument("--out", default="docking")
    ap.add_argument("--reps", type=int, default=30)
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--only", nargs="+", choices=list(SCENARIOS), help="tylko te scenariusze (export, python)")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    if a.what == "export":
        export(a.out, a.reps, a.only)
    elif a.what == "python":
        run_python(a.out, a.reps, a.jobs, a.only)
    else:
        compare(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
