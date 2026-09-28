"""
PSM – Proxemic Stress Model z awersją do tras (port models/Hall_AC_aversion.gaml).

Czysty Python (tylko biblioteka standardowa), uruchamialny lokalnie (CPython)
i w przeglądarce (Pyodide, zob. web/index.html).

Odwzorowane z GAML:
- sieć ścieżek (graf krawędziowy, as_edge_graph) z wagami długość * (1 + aversion_strength * fear_memory),
  przeliczana co reweight_every cykli razem z zanikaniem pamięci strachu (fear_decay);
- boty i phantomy poruszające się goto po ważonym grafie do losowego punktu na losowej ścieżce;
- strefy proksemiczne Halla (intimate/personal/social/public * hall_multiplier) maskowane przeszkodami;
- czujność (vigilance), adrenalina i kortyzol phantoma, próg lęku 11.5, agenci fear,
  odkładanie strachu na odcinku, na którym stoi phantom;
- zapis summary.csv w cyklu end_cycle - 1 i zatrzymanie w end_cycle.

Kolejność kroku jak w GAMA: reflexy globalne (stop, update_aversion, save_results)
-> bot -> phantom (aktualizacja stref, psychofizjologia, ruch).

Różnice względem GAMA (nie da się ich usunąć albo są świadomym uproszczeniem):
- inny generator liczb losowych: wyniki zgadzają się statystycznie, nie liczba w liczbę;
- masked_by liczone jako linia widoczności phantom -> bot (GAMA: wielokąt widoczności z promieni);
- "road closest_to self" to odcinek, na którym phantom właśnie stoi (phantom zawsze jest na sieci);
- odcinek częściowy przy wyznaczaniu trasy ma wagę proporcjonalną do przebytej części krawędzi;
- przy niespójnej sieci agenci są osadzani tylko na największej składowej
  (GAMA zostawiłaby agenta bez trasy w miejscu); parametr largest_component = False wyłącza to;
- GeoJSON/OSM w stopniach jest rzutowany lokalnie na metry (odwzorowanie równoodległościowe).

Uruchomienie:
    python psm.py --test
    python psm.py --run --cycles 10000 --roads Staszica_SHP_sciezki_01.shp --obstacles Staszica_SHP_krzaki_09.shp
    python psm.py --batch --aversion 0,2.5,5 --repeat 5 --cycles 3000
    python psm.py --fetch-osm "Park Staszica" --out ../includes/park_staszica.geojson
"""

import csv
import heapq
import io
import json
import math
import random
import struct
import sys
import time

# ---------------------------------------------------------------------------
# Parametry (wartości domyślne = global w Hall_AC_aversion.gaml)
# ---------------------------------------------------------------------------

DEFAULTS = {
    "step_min": 0.005,             # step <- 0.005 #mn (0.3 s)
    "hall_multiplier": 4.0,
    # promienie stref; None = bazowy promień Halla * hall_multiplier
    "intimate": None, "personal": None, "social": None, "public": None,
    "aversion_strength": 5.0,
    "fear_deposit": 1.0,
    "fear_decay": 0.999,
    "reweight_every": 20,
    "end_cycle": 10000,
    "phantom_nb": 1,
    "bot_nb": 80,
    # stałe z ciała modelu, wyciągnięte jako parametry
    "phantom_speed_kmh": 4.0,
    "bot_speed_kmh": 4.0,
    "bot_speed_sd": 0.3,           # gauss(0, 0.3) w m/s
    "adrenaline_threshold": 11.5,
    "fear_spacing": 8.0,           # fear at_distance 8
    "adrenaline_cooldown": 0.99,
    "cortisol_cooldown": 0.999,
    "initial_level": 0.5,          # startowe vigilance / adrenaline / cortisol
    # tylko port Pythona
    "largest_component": True,
    "park": "generated",           # "generated" albo "file" (sieć podana z zewnątrz)
    "park_seed": 1,
    "park_width": 320.0,
    "park_height": 240.0,
    "park_bushes": 70,
    # --- rozszerzenia (wartości domyślne = zachowanie jak w GAMA) ---
    # graf botów: "weighted" = ten sam ważony graf co phantom (jak w GAMA), "plain" = same długości
    "bot_graph": "weighted",
    # pamięć strachu: "shared" = na odcinku, wspólna (jak w GAMA), "individual" = osobna dla każdego phantoma
    "fear_scope": "shared",
    # nasadzenia: "default" = park generowany -> losowe krzewy, plik -> przeszkody z pliku;
    # "controlled" = sterowane nasadzenia przy stałej powierzchni; "none" = bez przeszkód
    "planting": "default",
    "planting_seed": 1,
    "bush_area_total": 2500.0,     # m², łączna powierzchnia krzewów (stała między wariantami)
    "bush_radius": 4.0,            # m
    "bush_junction_share": 0.5,    # udział powierzchni w narożnikach skrzyżowań
    "bush_junction_distance": 2.0, # m, odstęp krawędzi krzewu od węzła skrzyżowania
    "bush_path_offset": 1.0,       # m, odstęp krawędzi krzewu od osi ścieżki
    "junction_zone": 15.0,         # m, krzewy "przy ścieżce" leżą dalej niż tyle od skrzyżowań
    # izowisty (analiza widoczności)
    "isovist_spacing": 5.0,        # m, co ile próbkować ścieżki
    "isovist_rays": 72,
    "isovist_radius": None,        # None = strefa publiczna
}

CHOICES = {
    "bot_graph": ["weighted", "plain"],
    "fear_scope": ["shared", "individual"],
    "planting": ["default", "controlled", "none"],
}

HALL_BASE = {"intimate": 0.45, "personal": 1.2, "social": 3.6, "public": 10.0}

GUI_PARAMETERS = [
    ("Populacja", [
        ("bot_nb", "Liczba botów"),
        ("phantom_nb", "Liczba phantomów"),
        ("phantom_speed_kmh", "Prędkość phantoma (km/h)"),
        ("bot_speed_kmh", "Średnia prędkość botów (km/h)"),
        ("bot_speed_sd", "Odch. std. prędkości botów (m/s)"),
    ]),
    ("Strefy Halla", [
        ("hall_multiplier", "Mnożnik stref"),
        ("intimate", "Intymna (m, puste = z mnożnika)"),
        ("personal", "Osobista (m)"),
        ("social", "Społeczna (m)"),
        ("public", "Publiczna (m)"),
    ]),
    ("Psychofizjologia", [
        ("adrenaline_threshold", "Próg lęku (adrenalina)"),
        ("adrenaline_cooldown", "Wygaszanie adrenaliny"),
        ("cortisol_cooldown", "Wygaszanie kortyzolu"),
        ("initial_level", "Poziom startowy"),
        ("fear_spacing", "Min. odstęp znaczników strachu (m)"),
    ]),
    ("Awersja do tras", [
        ("aversion_strength", "Siła awersji (0 = baseline)"),
        ("fear_deposit", "Depozyt strachu"),
        ("fear_decay", "Zanikanie strachu"),
        ("reweight_every", "Przeliczanie grafu co (cykli)"),
    ]),
    ("Warianty mechaniki", [
        ("bot_graph", "Graf botów (weighted = jak GAMA)"),
        ("fear_scope", "Pamięć strachu (shared = jak GAMA)"),
    ]),
    ("Nasadzenia", [
        ("planting", "Nasadzenia"),
        ("planting_seed", "Seed nasadzeń"),
        ("bush_area_total", "Łączna powierzchnia krzewów (m²)"),
        ("bush_radius", "Promień krzewu (m)"),
        ("bush_junction_share", "Udział w narożnikach skrzyżowań"),
        ("bush_junction_distance", "Odstęp od węzła skrzyżowania (m)"),
        ("bush_path_offset", "Odstęp od osi ścieżki (m)"),
        ("junction_zone", "Strefa skrzyżowania (m)"),
    ]),
    ("Przebieg", [
        ("end_cycle", "Koniec (cykl)"),
        ("step_min", "Krok (min)"),
    ]),
    ("Park generowany", [
        ("park_seed", "Seed parku"),
        ("park_width", "Szerokość (m)"),
        ("park_height", "Wysokość (m)"),
        ("park_bushes", "Liczba krzewów"),
    ]),
]

# parametry, których zmiana wymaga ponownej inicjalizacji
RESTART_KEYS = {"bot_nb", "phantom_nb", "bot_speed_kmh", "bot_speed_sd", "phantom_speed_kmh",
                "park_seed", "park_width", "park_height", "park_bushes", "step_min", "largest_component",
                "bot_graph", "fear_scope", "planting", "planting_seed", "bush_area_total", "bush_radius",
                "bush_junction_share", "bush_junction_distance", "bush_path_offset", "junction_zone"}


def resolved_params(params=None):
    p = dict(DEFAULTS)
    if params:
        for k, v in params.items():
            if k not in DEFAULTS:
                raise KeyError("nieznany parametr: " + k)
            p[k] = v
    for k, base in HALL_BASE.items():
        if p[k] in (None, ""):
            p[k] = base * float(p["hall_multiplier"])
    if p["isovist_radius"] in (None, ""):
        p["isovist_radius"] = p["public"]
    for k, opts in CHOICES.items():
        if p[k] not in opts:
            raise ValueError("%s musi być jednym z %s" % (k, opts))
    return p


# ---------------------------------------------------------------------------
# Geometria
# ---------------------------------------------------------------------------

def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segments_intersect(p1, p2, q1, q2):
    d1 = _orient(q1, q2, p1)
    d2 = _orient(q1, q2, p2)
    d3 = _orient(p1, p2, q1)
    d4 = _orient(p1, p2, q2)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return False


def point_in_ring(pt, ring):
    x, y = pt
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def polyline_length(pts):
    return sum(dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


# ---------------------------------------------------------------------------
# Wczytywanie danych: shapefile, GeoJSON, OSM (Overpass)
# ---------------------------------------------------------------------------

def read_shp(data):
    """Minimalny czytnik .shp: zwraca listę (typ, części), typ ∈ {"line", "polygon", "point"}."""
    if len(data) < 100:
        raise ValueError("plik .shp jest za krótki")
    if struct.unpack(">i", data[0:4])[0] != 9994:
        raise ValueError("to nie jest plik .shp (zły nagłówek)")
    pos = 100
    out = []
    while pos + 8 <= len(data):
        _num, clen = struct.unpack(">ii", data[pos:pos + 8])
        rec = data[pos + 8:pos + 8 + clen * 2]
        pos += 8 + clen * 2
        if len(rec) < 4:
            continue
        stype = struct.unpack("<i", rec[0:4])[0]
        if stype == 0:
            continue
        if stype in (1, 11, 21):
            x, y = struct.unpack("<dd", rec[4:20])
            out.append(("point", [[(x, y)]]))
            continue
        if stype not in (3, 5, 13, 15, 23, 25):
            continue
        nparts, npts = struct.unpack("<ii", rec[36:44])
        parts = list(struct.unpack("<%di" % nparts, rec[44:44 + 4 * nparts]))
        base = 44 + 4 * nparts
        coords = [struct.unpack("<dd", rec[base + 16 * i:base + 16 * i + 16]) for i in range(npts)]
        parts.append(npts)
        rings = [coords[parts[i]:parts[i + 1]] for i in range(nparts)]
        out.append(("line" if stype in (3, 13, 23) else "polygon", rings))
    return out


def write_shp(shapes, kind):
    """Zapis prostego .shp (tylko do testów): shapes = lista list części."""
    stype = 3 if kind == "line" else 5
    recs = []
    for i, parts in enumerate(shapes):
        pts = [p for part in parts for p in part]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        body = struct.pack("<i4d2i", stype, min(xs), min(ys), max(xs), max(ys), len(parts), len(pts))
        off = 0
        for part in parts:
            body += struct.pack("<i", off)
            off += len(part)
        for p in pts:
            body += struct.pack("<2d", *p)
        recs.append(struct.pack(">2i", i + 1, len(body) // 2) + body)
    total = 100 + sum(len(r) for r in recs)
    header = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, total // 2) + struct.pack("<2i", 1000, stype)
    header += struct.pack("<8d", 0, 0, 0, 0, 0, 0, 0, 0)
    return header + b"".join(recs)


def looks_geographic(points):
    """Stopnie: wszystkie współrzędne w zakresie lon/lat i rozpiętość < 2° (park w metrach jest większy)."""
    if not points:
        return False
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs) >= -180.0 and max(xs) <= 180.0 and min(ys) >= -90.0 and max(ys) <= 90.0
            and max(xs) - min(xs) < 2.0 and max(ys) - min(ys) < 2.0)


def project_lonlat(features):
    """Rzut lokalny równoodległościowy: stopnie -> metry (y na północ)."""
    pts = [p for _k, parts in features for part in parts for p in part]
    if not pts:
        return features
    lon0 = sum(p[0] for p in pts) / len(pts)
    lat0 = sum(p[1] for p in pts) / len(pts)
    kx = 6371008.8 * math.pi / 180.0 * math.cos(math.radians(lat0))
    ky = 6371008.8 * math.pi / 180.0
    return [(k, [[((x - lon0) * kx, (y - lat0) * ky) for x, y in part] for part in parts]) for k, parts in features]


def geojson_features(obj):
    """GeoJSON -> lista (rodzaj, części); rodzaj z properties.layer albo z typu geometrii."""
    feats = obj.get("features", []) if obj.get("type") == "FeatureCollection" else [obj]
    out = []
    for f in feats:
        geom = f.get("geometry") if f.get("type") == "Feature" else f
        if not geom:
            continue
        layer = (f.get("properties") or {}).get("layer")
        t = geom.get("type")
        c = geom.get("coordinates")
        if t == "LineString":
            out.append((layer or "line", [[tuple(p[:2]) for p in c]]))
        elif t == "MultiLineString":
            out.append((layer or "line", [[tuple(p[:2]) for p in part] for part in c]))
        elif t == "Polygon":
            out.append((layer or "polygon", [[tuple(p[:2]) for p in ring] for ring in c]))
        elif t == "MultiPolygon":
            for poly in c:
                out.append((layer or "polygon", [[tuple(p[:2]) for p in ring] for ring in poly]))
    return out


def split_layers(features):
    roads, obstacles, boundary = [], [], []
    for kind, parts in features:
        if kind in ("roads", "line"):
            roads.extend(parts)
        elif kind in ("obstacles", "polygon"):
            obstacles.append(parts)
        elif kind == "boundary":
            boundary.extend(parts)
    return roads, obstacles, boundary


OSM_PATH_TAGS = "footway|path|pedestrian|cycleway|track|steps|living_street|service|bridleway"


def overpass_query(park_name, city="Wrocław"):
    """Zapytanie Overpass: park o nazwie zawierającej park_name w mieście city."""
    name = park_name.replace('"', "")
    return (
        '[out:json][timeout:90];\n'
        'area["name"="%s"]["boundary"="administrative"]->.city;\n'
        '(way["leisure"="park"]["name"~"%s",i](area.city);'
        'relation["leisure"="park"]["name"~"%s",i](area.city);)->.parks;\n'
        '.parks map_to_area->.p;\n'
        '(way["highway"~"^(%s)$"](area.p);)->.roads;\n'
        '(way["natural"="scrub"](area.p);way["barrier"="hedge"](area.p);'
        'way["building"](area.p);way["natural"="tree_row"](area.p);)->.obs;\n'
        '(.parks;.roads;.obs;);\nout geom;' % (city, name, name, OSM_PATH_TAGS)
    )


def osm_to_features(osm):
    """Odpowiedź Overpass (out geom) -> cechy w stopniach, drogi podzielone na skrzyżowaniach."""
    ways = [e for e in osm.get("elements", []) if e.get("type") == "way" and e.get("geometry")]
    roads, obs, boundary = [], [], []
    for w in ways:
        tags = w.get("tags", {})
        if "highway" in tags:
            roads.append(w)
        elif tags.get("leisure") == "park":
            boundary.append(w)
        else:
            obs.append(w)
    for rel in (e for e in osm.get("elements", []) if e.get("type") == "relation"):
        for m in rel.get("members", []):
            if m.get("role") == "outer" and m.get("geometry"):
                boundary.append({"geometry": m["geometry"], "nodes": [], "tags": {}})
    use = {}
    for w in roads:
        for i, n in enumerate(w["nodes"]):
            use[n] = use.get(n, 0) + (2 if i in (0, len(w["nodes"]) - 1) else 1)
    feats = []
    for w in roads:
        coords = [(g["lon"], g["lat"]) for g in w["geometry"]]
        cur = [coords[0]]
        for i in range(1, len(coords)):
            cur.append(coords[i])
            if i < len(coords) - 1 and use.get(w["nodes"][i], 0) >= 2:
                feats.append(("roads", [cur]))
                cur = [coords[i]]
        if len(cur) >= 2:
            feats.append(("roads", [cur]))
    for w in obs:
        coords = [(g["lon"], g["lat"]) for g in w["geometry"]]
        closed = len(coords) >= 4 and w["nodes"][0] == w["nodes"][-1]
        if closed:
            feats.append(("obstacles", [coords]))
        else:
            # żywopłot / szpaler jako cienki wielokąt (linia blokuje widoczność tak samo)
            feats.append(("obstacles", [coords + coords[::-1][1:]]))
    for w in boundary:
        feats.append(("boundary", [[(g["lon"], g["lat"]) for g in w["geometry"]]]))
    return feats


def features_to_geojson(features):
    out = []
    for kind, parts in features:
        if kind == "roads":
            for part in parts:
                out.append({"type": "Feature", "properties": {"layer": "roads"},
                            "geometry": {"type": "LineString", "coordinates": [list(p) for p in part]}})
        else:
            out.append({"type": "Feature", "properties": {"layer": kind},
                        "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in r] for r in parts]}})
    return {"type": "FeatureCollection", "features": out}


def fetch_osm(park_name, city="Wrocław"):
    """Pobiera park z Overpass API (wymaga internetu; w przeglądarce robi to index.html)."""
    import urllib.parse
    import urllib.request
    data = urllib.parse.urlencode({"data": overpass_query(park_name, city)}).encode()
    req = urllib.request.Request("https://overpass-api.de/api/interpreter", data=data,
                                 headers={"User-Agent": "psm-port/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def generate_park(seed=1, width=320.0, height=240.0, bushes=70):
    """Losowy park: pętla obwodowa + wewnętrzna siatka alejek z łukami, krzewy przy alejkach."""
    rng = random.Random(seed)
    cols, rows = 6, 5
    nodes = {}
    for i in range(cols):
        for j in range(rows):
            edge_i = i in (0, cols - 1)
            edge_j = j in (0, rows - 1)
            jx = 0.0 if edge_i else rng.uniform(-0.18, 0.18) * width / (cols - 1)
            jy = 0.0 if edge_j else rng.uniform(-0.18, 0.18) * height / (rows - 1)
            nodes[(i, j)] = (i * width / (cols - 1) + jx, j * height / (rows - 1) + jy)
    cand = []
    for i in range(cols):
        for j in range(rows):
            if i + 1 < cols:
                cand.append(((i, j), (i + 1, j)))
            if j + 1 < rows:
                cand.append(((i, j), (i, j + 1)))
    perimeter = [e for e in cand if (e[0][1] == e[1][1] and e[0][1] in (0, rows - 1))
                 or (e[0][0] == e[1][0] and e[0][0] in (0, cols - 1))]
    inner = [e for e in cand if e not in perimeter]
    rng.shuffle(inner)
    # drzewo rozpinające (spójność) + część pozostałych krawędzi
    parent = {k: k for k in nodes}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    chosen = []
    for e in perimeter + inner:
        ra, rb = find(e[0]), find(e[1])
        if ra != rb:
            parent[ra] = rb
            chosen.append(e)
        elif e in perimeter or rng.random() < 0.45:
            chosen.append(e)
    # przekątne w komórkach bez skrzyżowań
    for i in range(cols - 1):
        for j in range(rows - 1):
            if rng.random() < 0.18:
                chosen.append(((i, j), (i + 1, j + 1)) if rng.random() < 0.5 else ((i + 1, j), (i, j + 1)))
    roads = []
    for a, b in chosen:
        pa, pb = nodes[a], nodes[b]
        is_perim = (a, b) in perimeter
        bend = 0.0 if is_perim else rng.uniform(-0.12, 0.12)
        mx, my = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
        dx, dy = pb[0] - pa[0], pb[1] - pa[1]
        cx, cy = mx - dy * bend, my + dx * bend
        pts = []
        for k in range(9):
            t = k / 8.0
            pts.append(((1 - t) ** 2 * pa[0] + 2 * (1 - t) * t * cx + t * t * pb[0],
                        (1 - t) ** 2 * pa[1] + 2 * (1 - t) * t * cy + t * t * pb[1]))
        pts[0], pts[-1] = pa, pb
        roads.append(pts)
    segs = [(r[k], r[k + 1]) for r in roads for k in range(len(r) - 1)]

    def dist_to_paths(p):
        best = 1e18
        for a, b in segs:
            best = min(best, _point_seg_dist(p, a, b))
        return best

    obstacles = []

    def try_bush(c, r):
        if not (r <= c[0] <= width - r and r <= c[1] <= height - r):
            return False
        if dist_to_paths(c) < r + 0.6:
            return False
        if any(dist(c, o[1]) < r + o[2] + 0.5 for o in obstacles):
            return False
        n = rng.randint(7, 11)
        ring = []
        for k in range(n):
            ang = 2 * math.pi * k / n
            rr = r * rng.uniform(0.75, 1.0)
            ring.append((c[0] + rr * math.cos(ang), c[1] + rr * math.sin(ang)))
        ring.append(ring[0])
        obstacles.append(([ring], c, r))
        return True

    # ślepe narożniki: krzew w klinie między ramionami skrzyżowania (zasłania nadchodzących)
    arms = {}
    for r_ in roads:
        for end, nxt in ((r_[0], r_[1]), (r_[-1], r_[-2])):
            key = (round(end[0], 6), round(end[1], 6))
            arms.setdefault(key, (end, []))[1].append(math.atan2(nxt[1] - end[1], nxt[0] - end[0]))
    for _key, (node, angs) in sorted(arms.items()):
        angs.sort()
        for k in range(len(angs)):
            a0 = angs[k]
            a1 = angs[(k + 1) % len(angs)] + (2 * math.pi if k == len(angs) - 1 else 0.0)
            gap = a1 - a0
            if len(angs) == 1 or gap < math.radians(50) or gap > math.radians(200):
                continue
            if rng.random() > 0.75 * bushes / 70.0:
                continue
            r = rng.uniform(2.5, 5.0)
            d = (r + 1.2) / math.sin(min(gap, math.pi) / 2)
            mid = a0 + gap / 2
            try_bush((node[0] + d * math.cos(mid), node[1] + d * math.sin(mid)), r)
    # pozostałe krzewy blisko alejek (0.6–4 m od krawędzi)
    tries = 0
    target = len(obstacles) + bushes
    while len(obstacles) < target and tries < bushes * 80:
        tries += 1
        seg = segs[rng.randrange(len(segs))]
        t = rng.random()
        px, py = seg[0][0] + (seg[1][0] - seg[0][0]) * t, seg[0][1] + (seg[1][1] - seg[0][1]) * t
        dx, dy = seg[1][0] - seg[0][0], seg[1][1] - seg[0][1]
        L = math.hypot(dx, dy) or 1.0
        side = 1 if rng.random() < 0.5 else -1
        r = rng.uniform(2.0, 7.0)
        off = r + rng.uniform(0.6, 4.0)
        try_bush((px - side * dy / L * off, py + side * dx / L * off), r)
    boundary = [[(0.0, 0.0), (width, 0.0), (width, height), (0.0, height), (0.0, 0.0)]]
    return roads, [o[0] for o in obstacles], boundary


def _point_seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


class SegIndex:
    """Siatka przestrzenna odcinków: szybka odległość punktu od najbliższej ścieżki."""

    def __init__(self, polylines, cell=20.0):
        self.cell = cell
        self.grid = {}
        for pts in polylines:
            for k in range(len(pts) - 1):
                a, b = pts[k], pts[k + 1]
                for i in range(int(math.floor(min(a[0], b[0]) / cell)), int(math.floor(max(a[0], b[0]) / cell)) + 1):
                    for j in range(int(math.floor(min(a[1], b[1]) / cell)), int(math.floor(max(a[1], b[1]) / cell)) + 1):
                        self.grid.setdefault((i, j), []).append((a, b))

    def nearest(self, p, limit=60.0):
        """Odległość do najbliższego odcinka (albo limit, gdy dalej)."""
        c = self.cell
        k = int(math.ceil(limit / c))
        ci, cj = int(math.floor(p[0] / c)), int(math.floor(p[1] / c))
        best = limit
        for i in range(ci - k, ci + k + 1):
            for j in range(cj - k, cj + k + 1):
                for a, b in self.grid.get((i, j), ()):
                    d = _point_seg_dist(p, a, b)
                    if d < best:
                        best = d
        return best


def circle_ring(c, r, n=16):
    ring = [(c[0] + r * math.cos(2 * math.pi * k / n), c[1] + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    ring.append(ring[0])
    return ring


def ring_area(ring):
    return abs(sum(ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1] for i in range(len(ring) - 1))) / 2.0


def junctions(roads, probe=5.0):
    """Węzły stopnia >= 3 z kierunkami ramion (kąt do punktu ok. probe m wzdłuż ścieżki)."""
    net = Network(roads, largest_component=False)
    out = []
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
        out.append((net.nodes[n], sorted(angs)))
    return out


def plant_bushes(roads, p):
    """Sterowane nasadzenia przy stałej łącznej powierzchni.

    Krzewy są kołami (16-kąt) o promieniu bush_radius. Część bush_junction_share powierzchni trafia
    w narożniki skrzyżowań (na dwusiecznej kąta między ramionami, krawędź krzewu bush_junction_distance
    od węzła i co najmniej bush_path_offset od osi ścieżek), reszta wzdłuż ścieżek (krawędź dokładnie
    bush_path_offset od osi, cały krzew dalej niż junction_zone od skrzyżowań).
    Gdy narożników brakuje, reszta powierzchni idzie wzdłuż ścieżek (zob. info["junction_share"]).
    """
    rng = random.Random(int(p["planting_seed"]))
    r = float(p["bush_radius"])
    off = float(p["bush_path_offset"])
    jd = float(p["bush_junction_distance"])
    zone = float(p["junction_zone"])
    one = ring_area(circle_ring((0.0, 0.0), r))
    n_total = int(round(float(p["bush_area_total"]) / one))
    n_junc = int(round(n_total * float(p["bush_junction_share"])))
    idx = SegIndex(roads)
    juncs = junctions(roads)
    placed = []
    grid = {}
    gc = max(2 * r + 1.0, 5.0)

    def free(c):
        if idx.nearest(c, r + off + 1.0) < r + off - 1e-6:
            return False
        gi, gj = int(math.floor(c[0] / gc)), int(math.floor(c[1] / gc))
        for i in range(gi - 1, gi + 2):
            for j in range(gj - 1, gj + 2):
                for q in grid.get((i, j), ()):
                    if dist(c, q) < 2 * r + 0.3:
                        return False
        return True

    def put(c):
        placed.append(c)
        grid.setdefault((int(math.floor(c[0] / gc)), int(math.floor(c[1] / gc))), []).append(c)

    cands = []
    for node, angs in juncs:
        for k in range(len(angs)):
            a0 = angs[k]
            a1 = angs[(k + 1) % len(angs)] + (2 * math.pi if k == len(angs) - 1 else 0.0)
            gap = a1 - a0
            if gap < math.radians(30):
                continue
            half = min(gap / 2, math.pi / 2)
            d = max(jd + r, (r + off) / math.sin(half))
            mid = a0 + gap / 2
            cands.append((node[0] + d * math.cos(mid), node[1] + d * math.sin(mid)))
    rng.shuffle(cands)
    n_j = 0
    for c in cands:
        if n_j >= n_junc:
            break
        if free(c):
            put(c)
            n_j += 1
    # wzdłuż ścieżek, z dala od skrzyżowań
    segs = [(rd[k], rd[k + 1]) for rd in roads for k in range(len(rd) - 1) if dist(rd[k], rd[k + 1]) > 0]
    cum = []
    tot = 0.0
    for a, b in segs:
        tot += dist(a, b)
        cum.append(tot)
    jnodes = [n for n, _a in juncs]
    jgrid = {}
    for q in jnodes:
        jgrid.setdefault((int(math.floor(q[0] / 50.0)), int(math.floor(q[1] / 50.0))), []).append(q)

    def far_from_junctions(c):
        gi, gj = int(math.floor(c[0] / 50.0)), int(math.floor(c[1] / 50.0))
        k = int(math.ceil((zone + r) / 50.0))
        for i in range(gi - k, gi + k + 1):
            for j in range(gj - k, gj + k + 1):
                for q in jgrid.get((i, j), ()):
                    if dist(c, q) < zone + r:
                        return False
        return True

    tries = 0
    while len(placed) < n_total and tries < 400 * max(1, n_total) and segs:
        tries += 1
        u = rng.random() * tot
        lo, hi = 0, len(cum) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if cum[mid] < u:
                lo = mid + 1
            else:
                hi = mid
        a, b = segs[lo]
        L = dist(a, b)
        t = rng.random()
        px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        side = 1.0 if rng.random() < 0.5 else -1.0
        nx, ny = -(b[1] - a[1]) / L * side, (b[0] - a[0]) / L * side
        c = (px + nx * (r + off), py + ny * (r + off))
        if far_from_junctions(c) and free(c):
            put(c)
    obstacles = [[circle_ring(c, r)] for c in placed]
    info = {"n_bushes": len(placed), "n_target": n_total, "area": round(one * len(placed), 1),
            "area_target": float(p["bush_area_total"]), "n_junction": n_j,
            "junction_share": round(n_j / len(placed), 3) if placed else 0.0,
            "n_junctions": len(juncs), "junction_candidates": len(cands)}
    return obstacles, info


# ---------------------------------------------------------------------------
# Izowisty (analiza widoczności)
# ---------------------------------------------------------------------------

def _ray_hit(p, dx, dy, a, b):
    """Odległość wzdłuż promienia p + t(dx, dy) do odcinka a-b (albo None)."""
    ex, ey = b[0] - a[0], b[1] - a[1]
    den = dx * ey - dy * ex
    if abs(den) < 1e-12:
        return None
    wx, wy = a[0] - p[0], a[1] - p[1]
    t = (wx * ey - wy * ex) / den
    u = (wx * dy - wy * dx) / den
    if t >= 0 and 0 <= u <= 1:
        return t
    return None


def isovist(p, obstacles, radius, rays=72, ignore=()):
    """Izowista w punkcie p: (pole m², średnia długość promienia, udział promieni zasłoniętych)."""
    segs = []
    seen = set()
    for key in obstacles._cells(p[0] - radius, p[1] - radius, p[0] + radius, p[1] + radius):
        for a, b, pi in obstacles.grid.get(key, ()):
            if pi in ignore or (a, b) in seen:
                continue
            seen.add((a, b))
            if _point_seg_dist(p, a, b) <= radius:
                segs.append((a, b))
    lengths = []
    for k in range(rays):
        ang = 2 * math.pi * k / rays
        dx, dy = math.cos(ang), math.sin(ang)
        best = radius
        for a, b in segs:
            t = _ray_hit(p, dx, dy, a, b)
            if t is not None and t < best:
                best = t
        lengths.append(best)
    dth = 2 * math.pi / rays
    area = sum(0.5 * lengths[k] * lengths[(k + 1) % rays] * math.sin(dth) for k in range(rays))
    blocked = sum(1 for L in lengths if L < radius - 1e-9) / rays
    return area, sum(lengths) / rays, blocked


def isovist_by_edge(net, obstacles, radius, spacing=5.0, rays=72):
    """Średnia izowista na każdym odcinku (próbki co spacing m, co najmniej jedna na odcinek)."""
    out = []
    for e in net.edges:
        n = max(1, int(e.length // spacing))
        vals = []
        for k in range(n):
            q = e.point_at((k + 0.5) * e.length / n)[0]
            vals.append(isovist(q, obstacles, radius, rays, obstacles.containing(q)))
        out.append((sum(v[0] for v in vals) / n, sum(v[1] for v in vals) / n, sum(v[2] for v in vals) / n))
    return out


def _sd(v):
    if len(v) < 2:
        return 0.0
    m = sum(v) / len(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))


def spearman(x, y):
    """Korelacja rang Spearmana (rangi wiązane uśrednione)."""
    n = len(x)
    if n < 3:
        return float("nan")

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        rk = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                rk[order[k]] = (i + j) / 2.0
            i = j + 1
        return rk

    rx, ry = ranks(x), ranks(y)
    mx, my = sum(rx) / n, sum(ry) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return sxy / (sx * sy) if sx and sy else float("nan")


# ---------------------------------------------------------------------------
# Sieć ścieżek (as_edge_graph)
# ---------------------------------------------------------------------------

class Edge:
    __slots__ = ("id", "a", "b", "pts", "cum", "length", "fear_memory", "weight")

    def __init__(self, eid, a, b, pts):
        self.id = eid
        self.a = a
        self.b = b
        self.pts = pts
        self.cum = [0.0]
        for i in range(len(pts) - 1):
            self.cum.append(self.cum[-1] + dist(pts[i], pts[i + 1]))
        self.length = self.cum[-1]
        self.fear_memory = 0.0
        self.weight = self.length

    def point_at(self, s):
        """Punkt i kierunek (rad) w odległości s od początku krawędzi."""
        s = max(0.0, min(self.length, s))
        cum = self.cum
        lo, hi = 0, len(cum) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if cum[mid] <= s:
                lo = mid
            else:
                hi = mid
        p, q = self.pts[lo], self.pts[lo + 1]
        seg = cum[lo + 1] - cum[lo]
        t = 0.0 if seg == 0 else (s - cum[lo]) / seg
        return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t), math.atan2(q[1] - p[1], q[0] - p[0])


class Network:
    def __init__(self, polylines, largest_component=True, snap=1e-3):
        self.nodes = []
        index = {}

        def node_of(p):
            key = (round(p[0] / snap), round(p[1] / snap))
            if key not in index:
                index[key] = len(self.nodes)
                self.nodes.append(p)
            return index[key]

        edges = []
        for pts in polylines:
            pts = [tuple(p) for p in pts]
            clean = [pts[0]]
            for p in pts[1:]:
                if dist(p, clean[-1]) > 1e-9:
                    clean.append(p)
            if len(clean) < 2 or polyline_length(clean) <= 0:
                continue
            a, b = node_of(clean[0]), node_of(clean[-1])
            edges.append((a, b, clean))
        self.adj = [[] for _ in self.nodes]
        self.edges = []
        for a, b, pts in edges:
            e = Edge(len(self.edges), a, b, pts)
            self.edges.append(e)
            self.adj[a].append(e)
            self.adj[b].append(e)
        self.components = self._components()
        if largest_component and self.edges:
            best = max(set(self.components), key=lambda c: sum(e.length for e in self.edges if self.components[e.a] == c))
            self.active = [e for e in self.edges if self.components[e.a] == best]
        else:
            self.active = list(self.edges)
        if not self.active:
            raise ValueError("sieć ścieżek jest pusta")
        self.lengths = [e.length for e in self.edges]
        self.weights = list(self.lengths)
        self.active_len = [e.length for e in self.active]
        self.total_len = sum(self.active_len)

    def _components(self):
        comp = [-1] * len(self.nodes)
        c = 0
        for s in range(len(self.nodes)):
            if comp[s] >= 0:
                continue
            stack = [s]
            comp[s] = c
            while stack:
                u = stack.pop()
                for e in self.adj[u]:
                    v = e.b if e.a == u else e.a
                    if comp[v] < 0:
                        comp[v] = c
                        stack.append(v)
            c += 1
        return comp

    def n_components(self):
        return len(set(self.components)) if self.components else 0

    def reweight(self, aversion_strength):
        # waga = długość * (1 + aversion_strength * fear_memory)
        for e in self.edges:
            e.weight = e.length * (1.0 + aversion_strength * e.fear_memory)
        self.weights = [e.weight for e in self.edges]

    def random_location(self, rng):
        """any_location_in(one_of(road)): losowa ścieżka, losowy punkt na niej."""
        e = self.active[rng.randrange(len(self.active))]
        return (e, rng.uniform(0.0, e.length))

    def route(self, src, dst, weights=None):
        """Najkrótsza trasa (wagi) z (krawędź, s) do (krawędź, s): lista (krawędź, s_od, s_do).

        weights: lista wag indeksowana id krawędzi; None = wagi krawędzi (graf wspólny).
        """
        W = weights if weights is not None else self.weights
        e0, s0 = src
        e1, s1 = dst
        if e0 is e1:
            return [(e0, s0, s1)]
        f0 = W[e0.id] / e0.length if e0.length else 1.0
        f1 = W[e1.id] / e1.length if e1.length else 1.0
        best = {}
        prev = {}
        heap = []
        for node, cost, first in ((e0.a, s0 * f0, 0.0), (e0.b, (e0.length - s0) * f0, e0.length)):
            if cost < best.get(node, 1e300):
                best[node] = cost
                prev[node] = ("start", first)
                heapq.heappush(heap, (cost, node))
        goal = {e1.a: s1 * f1, e1.b: (e1.length - s1) * f1}
        best_total = 1e300
        best_end = None
        while heap:
            cost, u = heapq.heappop(heap)
            if cost > best.get(u, 1e300):
                continue
            if cost >= best_total:
                break
            if u in goal and cost + goal[u] < best_total:
                best_total = cost + goal[u]
                best_end = u
            for e in self.adj[u]:
                v = e.b if e.a == u else e.a
                nc = cost + W[e.id]
                if nc < best.get(v, 1e300):
                    best[v] = nc
                    prev[v] = (e, u)
                    heapq.heappush(heap, (nc, v))
        if best_end is None:
            return None
        legs = []
        if best_end == e1.a:
            legs.append((e1, 0.0, s1))
        else:
            legs.append((e1, e1.length, s1))
        u = best_end
        while True:
            p = prev[u]
            if p[0] == "start":
                legs.append((e0, s0, p[1]))
                break
            e, w = p
            legs.append((e, 0.0, e.length) if e.a == w else (e, e.length, 0.0))
            u = w
        legs.reverse()
        return [leg for leg in legs if leg[1] != leg[2] or len(legs) == 1]


class Obstacles:
    """Przeszkody (masked_by): odcinki blokujące widoczność w siatce przestrzennej."""

    def __init__(self, polygons, cell=10.0):
        self.polygons = polygons
        self.cell = cell
        self.grid = {}
        self.bboxes = []
        for pi, rings in enumerate(polygons):
            pts = [p for r in rings for p in r]
            self.bboxes.append((min(p[0] for p in pts), min(p[1] for p in pts),
                                max(p[0] for p in pts), max(p[1] for p in pts)))
            for r in rings:
                for k in range(len(r) - 1):
                    a, b = r[k], r[k + 1]
                    for key in self._cells(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])):
                        self.grid.setdefault(key, []).append((a, b, pi))

    def _cells(self, x0, y0, x1, y1):
        c = self.cell
        for i in range(int(math.floor(x0 / c)), int(math.floor(x1 / c)) + 1):
            for j in range(int(math.floor(y0 / c)), int(math.floor(y1 / c)) + 1):
                yield (i, j)

    def containing(self, p):
        out = set()
        for key in self._cells(p[0], p[1], p[0], p[1]):
            for _a, _b, pi in self.grid.get(key, ()):
                if pi in out:
                    continue
                x0, y0, x1, y1 = self.bboxes[pi]
                if x0 <= p[0] <= x1 and y0 <= p[1] <= y1 and point_in_ring(p, self.polygons[pi][0]):
                    out.add(pi)
        return out

    def visible(self, p, q, ignore=()):
        """Czy odcinek p->q nie przecina żadnej przeszkody (poza tymi, w których stoi obserwator)."""
        seen = set()
        for key in self._cells(min(p[0], q[0]), min(p[1], q[1]), max(p[0], q[0]), max(p[1], q[1])):
            for a, b, pi in self.grid.get(key, ()):
                if pi in ignore:
                    continue
                k = (a, b)
                if k in seen:
                    continue
                seen.add(k)
                if segments_intersect(p, q, a, b):
                    return False
        # cel całkowicie wewnątrz przeszkody też jest zasłonięty
        for pi in self.containing(q):
            if pi not in ignore:
                return False
        return True


# ---------------------------------------------------------------------------
# Agenci
# ---------------------------------------------------------------------------

class Mover:
    __slots__ = ("edge", "s", "loc", "heading", "speed", "target", "target_loc", "route", "route_ver")

    def __init__(self, net, rng, speed):
        self.edge, self.s = net.random_location(rng)
        self.loc, self.heading = self.edge.point_at(self.s)
        self.speed = speed          # m/s
        self.target = (self.edge, self.s)
        self.target_loc = self.loc
        self.route = None
        self.route_ver = -1

    def normal_move(self, model):
        # if target distance_to location < 1: nowy cel, w przeciwnym razie goto po road_network
        if dist(self.target_loc, self.loc) < 1.0:
            self.target = model.net.random_location(model.rng)
            self.target_loc = self.target[0].point_at(self.target[1])[0]
            self.route = None
        else:
            self.goto(model)

    def route_weights(self, model):
        # bot: graf ważony jak w GAMA albo same długości (bot_graph = "plain")
        return model.bot_weights

    def goto(self, model):
        if self.route is None or self.route_ver != model.graph_version:
            self.route = model.net.route((self.edge, self.s), self.target, self.route_weights(model))
            self.route_ver = model.graph_version
            if self.route is None:
                return
        remaining = self.speed * model.step_s
        while remaining > 0 and self.route:
            e, s_from, s_to = self.route[0]
            left = abs(s_to - self.s) if e is self.edge else abs(s_to - s_from)
            if e is not self.edge:
                self.edge, self.s = e, s_from
            direction = 1.0 if s_to >= self.s else -1.0
            if remaining >= left:
                self.s = s_to
                remaining -= left
                self.route.pop(0)
            else:
                self.s += direction * remaining
                remaining = 0.0
            if e.length:
                self.loc, h = e.point_at(self.s)
                self.heading = h if direction > 0 else h + math.pi


class Phantom(Mover):
    __slots__ = ("vigilance", "adrenaline", "cortisol", "total_adrenaline", "total_cortisol",
                 "total_vigilance", "where_are_they", "where_were_they", "fear_events", "fear", "weights")

    def __init__(self, net, rng, speed, level):
        Mover.__init__(self, net, rng, speed)
        self.vigilance = level
        self.adrenaline = level
        self.cortisol = level
        self.total_adrenaline = 0.0
        self.total_cortisol = 0.0
        self.total_vigilance = 0.0
        self.where_are_they = []
        self.where_were_they = []
        self.fear_events = 0
        self.fear = {}          # własna pamięć strachu (fear_scope = "individual"): id odcinka -> wartość
        self.weights = None

    def route_weights(self, model):
        # phantom: wspólny graf (jak w GAMA) albo własne wagi z własnej pamięci strachu
        return self.weights if model.p["fear_scope"] == "individual" else None

    def distance_number(self, model, q):
        d = dist(self.loc, q)
        p = model.p
        if d > p["public"]:
            return 0
        if not model.obstacles.visible(self.loc, q, model._ignore):
            return 0
        if d <= p["intimate"]:
            return 4
        if d <= p["personal"]:
            return 3
        if d <= p["social"]:
            return 2
        return 1

    def required_vigilance(self):
        if not self.where_were_they:
            return 0.0
        total = 0.0
        for was, now in zip(self.where_were_they, self.where_are_they):
            if was < now:
                diff = now - was
                total += diff * diff - 0.99
        return total

    def update_psychophysiology(self, model):
        p = model.p
        model._ignore = model.obstacles.containing(self.loc)
        self.where_are_they = [self.distance_number(model, b.loc) for b in model.bots]
        self.cortisol = self.cortisol * p["cortisol_cooldown"]
        self.cortisol = self.cortisol + 0.2 * self.adrenaline / ((self.cortisol + 1.0) * (self.cortisol + 1.0))
        self.vigilance = self.required_vigilance()
        self.adrenaline = self.adrenaline * p["adrenaline_cooldown"]
        self.adrenaline = self.adrenaline + self.vigilance
        self.where_were_they = self.where_are_they
        feared = self.adrenaline > p["adrenaline_threshold"]
        if feared:
            if not any(dist(f[0], self.loc) <= p["fear_spacing"] for f in model.fears):
                model.fears.append((self.loc, int(min(255.0, 255.0 * self.adrenaline / 20.0))))
            # odłóż strach na odcinku, na którym stoi phantom (fear_memory odcinka = suma wszystkich phantomów)
            self.edge.fear_memory += p["fear_deposit"]
            self.fear[self.edge.id] = self.fear.get(self.edge.id, 0.0) + p["fear_deposit"]
            self.fear_events += 1
        # mapa stresu: bodźce odebrane na odcinku, na którym phantom stoi w tym cyklu
        st = model.edge_stats[self.edge.id]
        st[0] += 1
        st[1] += self.adrenaline
        st[2] += self.vigilance
        if feared:
            st[3] += 1
        self.total_adrenaline += self.adrenaline
        self.total_cortisol += self.cortisol
        self.total_vigilance += self.vigilance


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

SUMMARY_HEADER = ["bot_nb", "phantom_nb", "total_adrenaline", "total_cortisol", "total_vigilance"]


class Model:
    def __init__(self, params=None, seed=None, roads=None, obstacles=None, boundary=None):
        self.p = resolved_params(params)
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.rng = random.Random(self.seed)
        p = self.p
        if roads is None:
            roads, obstacles, boundary = generate_park(int(p["park_seed"]), float(p["park_width"]),
                                                       float(p["park_height"]), int(p["park_bushes"]))
            self.source = "generated"
        else:
            self.source = "file"
        roads, obstacles, boundary = self._normalize(roads, obstacles or [], boundary or [])
        self.planting_info = {}
        if p["planting"] == "controlled":
            obstacles, self.planting_info = plant_bushes(roads, p)
        elif p["planting"] == "none":
            obstacles = []
        self.boundary = boundary
        self.net = Network(roads, largest_component=bool(p["largest_component"]))
        self.obstacles = Obstacles(obstacles)
        self.bot_weights = None if p["bot_graph"] == "weighted" else self.net.lengths
        # [cykle phantoma na odcinku, suma adrenaliny, suma czujności, epizody lęku]
        self.edge_stats = [[0, 0.0, 0.0, 0] for _ in self.net.edges]
        self.isovist_edges = None
        self._ignore = set()
        self.step_s = float(p["step_min"]) * 60.0
        self.cycle = 0
        self.graph_version = 0
        self.finished = False
        self.fears = []
        self.summary_rows = []
        self.history = []   # (cycle, adrenaline, cortisol, vigilance) phantoma 0
        kmh = 1000.0 / 3600.0
        self.bots = []
        for _ in range(int(p["bot_nb"])):
            sp = float(p["bot_speed_kmh"]) * kmh + self.rng.gauss(0.0, float(p["bot_speed_sd"]))
            self.bots.append(Mover(self.net, self.rng, max(0.0, sp)))
        self.phantoms = [Phantom(self.net, self.rng, float(p["phantom_speed_kmh"]) * kmh, float(p["initial_level"]))
                         for _ in range(int(p["phantom_nb"]))]
        self.rebuild_graph()

    @staticmethod
    def _normalize(roads, obstacles, boundary):
        feats = [("roads", roads)] + [("obstacles", o) for o in obstacles] + [("boundary", boundary)]
        # współrzędne w metrach (stopnie rzutuje wcześniej load_inputs); przesunięcie do (0, 0) jak envelope w GAMA
        pts = [p for _k, parts in feats for part in parts for p in part]
        x0 = min(p[0] for p in pts)
        y0 = min(p[1] for p in pts)
        feats = [(k, [[(x - x0, y - y0) for x, y in part] for part in parts]) for k, parts in feats]
        return feats[0][1], [f[1] for f in feats[1:-1]], feats[-1][1]

    # --- reflexy globalne ---
    def rebuild_graph(self):
        beta = float(self.p["aversion_strength"])
        self.net.reweight(beta)
        if self.p["fear_scope"] == "individual":
            for ph in self.phantoms:
                w = list(self.net.lengths)
                for eid, f in ph.fear.items():
                    w[eid] = self.net.lengths[eid] * (1.0 + beta * f)
                ph.weights = w
        self.graph_version += 1

    def update_aversion(self):
        decay = float(self.p["fear_decay"])
        for e in self.net.edges:
            e.fear_memory *= decay
        for ph in self.phantoms:
            for eid in ph.fear:
                ph.fear[eid] *= decay
        self.rebuild_graph()

    def save_results(self):
        for ph in self.phantoms:
            self.summary_rows.append([int(self.p["bot_nb"]), int(self.p["phantom_nb"]),
                                      ph.total_adrenaline, ph.total_cortisol, ph.total_vigilance])

    def step(self):
        if self.finished:
            return False
        p = self.p
        if self.cycle >= int(p["end_cycle"]):
            self.finished = True
            return False
        if self.cycle % int(p["reweight_every"]) == 0:
            self.update_aversion()
        if self.cycle == int(p["end_cycle"]) - 1:
            self.save_results()
        for b in self.bots:
            b.normal_move(self)
        for ph in self.phantoms:
            ph.update_psychophysiology(self)
            ph.normal_move(self)
        if self.phantoms:
            ph = self.phantoms[0]
            self.history.append((self.cycle, ph.adrenaline, ph.cortisol, ph.vigilance))
        self.cycle += 1
        return True

    def run(self, cycles=None):
        target = int(self.p["end_cycle"]) if cycles is None else self.cycle + cycles
        while self.cycle < target and self.step():
            pass
        return self

    # --- eksport ---
    def summary_csv(self):
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(SUMMARY_HEADER)
        w.writerows(self.summary_rows)
        return buf.getvalue()

    def timeseries_csv(self):
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["cycle", "adrenaline", "cortisol", "vigilance"])
        w.writerows(self.history)
        return buf.getvalue()

    def fear_csv(self):
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["edge_id", "length_m", "fear_memory", "weight"])
        for e in self.net.edges:
            w.writerow([e.id, round(e.length, 3), e.fear_memory, e.weight])
        return buf.getvalue()

    def edge_csv(self):
        """Mapa stresu i widoczności na odcinkach."""
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["edge_id", "length_m", "phantom_cycles", "mean_adrenaline", "vigilance_sum",
                    "fear_events", "fear_memory", "weight", "isovist_area_m2", "isovist_mean_ray_m", "isovist_blocked_share"])
        for e in self.net.edges:
            v, a, g, f = self.edge_stats[e.id]
            iso = self.isovist_edges[e.id] if self.isovist_edges else ("", "", "")
            w.writerow([e.id, round(e.length, 3), v, round(a / v, 4) if v else "", round(g, 4), f,
                        round(e.fear_memory, 4), round(e.weight, 3)] +
                       [round(x, 3) if x != "" else "" for x in iso])
        return buf.getvalue()

    def compute_isovists(self):
        p = self.p
        self.isovist_edges = isovist_by_edge(self.net, self.obstacles, float(p["isovist_radius"]),
                                             float(p["isovist_spacing"]), int(p["isovist_rays"]))
        return self.isovist_edges

    def isovist_comparison(self, min_cycles=30):
        """Spearman: widoczność odcinka vs stres na nim (odcinki odwiedzone co najmniej min_cycles cykli)."""
        if self.isovist_edges is None:
            self.compute_isovists()
        rows = [(self.isovist_edges[i], st) for i, st in enumerate(self.edge_stats) if st[0] >= min_cycles]
        area = [r[0][0] for r in rows]
        blocked = [r[0][2] for r in rows]
        adr = [r[1][1] / r[1][0] for r in rows]
        vig = [r[1][2] / r[1][0] for r in rows]
        fear = [r[1][3] / r[1][0] for r in rows]
        return {
            "n_edges": len(rows),
            "rho_area_adrenaline": spearman(area, adr),
            "rho_area_vigilance": spearman(area, vig),
            "rho_area_fear": spearman(area, fear),
            "rho_blocked_adrenaline": spearman(blocked, adr),
            "rho_blocked_vigilance": spearman(blocked, vig),
            "rho_blocked_fear": spearman(blocked, fear),
        }

    def metrics(self):
        ph = self.phantoms[0] if self.phantoms else None
        fear = [e.fear_memory for e in self.net.edges]
        stress = [st[1] / st[0] for st in self.edge_stats if st[0] >= 30]
        return {
            "cycle": self.cycle,
            "adrenaline": ph.adrenaline if ph else 0.0,
            "cortisol": ph.cortisol if ph else 0.0,
            "vigilance": ph.vigilance if ph else 0.0,
            "total_adrenaline": ph.total_adrenaline if ph else 0.0,
            "total_cortisol": ph.total_cortisol if ph else 0.0,
            "total_vigilance": ph.total_vigilance if ph else 0.0,
            "fear_events": ph.fear_events if ph else 0,
            "fear_markers": len(self.fears),
            "feared_edges": sum(1 for f in fear if f > 0.01),
            "max_fear_memory": max(fear) if fear else 0.0,
            "n_bushes": len(self.obstacles.polygons),
            "bush_area": round(sum(ring_area(r[0]) for r in self.obstacles.polygons), 1),
            # rozkład stresu w przestrzeni: odchylenie standardowe średniej adrenaliny między odcinkami
            "edge_stress_sd": _sd(stress),
        }

    # --- dane do przeglądarki ---
    def network_json(self):
        r = lambda v: round(v, 2)
        active = {e.id for e in self.net.active}
        xs = [p[0] for e in self.net.edges for p in e.pts]
        ys = [p[1] for e in self.net.edges for p in e.pts]
        return json.dumps({
            "edges": [[[r(x), r(y)] for x, y in e.pts] for e in self.net.edges],
            "active": [1 if e.id in active else 0 for e in self.net.edges],
            "obstacles": [[[r(x), r(y)] for x, y in rings[0]] for rings in self.obstacles.polygons],
            "boundary": [[[r(x), r(y)] for x, y in ring] for ring in self.boundary],
            "bbox": [0.0, 0.0, max(xs), max(ys)],
            "n_edges": len(self.net.edges), "n_nodes": len(self.net.nodes),
            "n_components": self.net.n_components(), "length": r(self.net.total_len),
            "source": self.source,
            "planting": self.planting_info,
        })

    def snapshot_json(self):
        r = lambda v: round(v, 2)
        p = self.p
        return json.dumps({
            "cycle": self.cycle, "finished": self.finished,
            "bots": [[r(b.loc[0]), r(b.loc[1]), round(b.heading, 2)] for b in self.bots],
            "phantoms": [[r(ph.loc[0]), r(ph.loc[1]), round(ph.heading, 2)] for ph in self.phantoms],
            "zones": [p["intimate"], p["personal"], p["social"], p["public"]],
            "fears": [[r(f[0][0]), r(f[0][1]), f[1]] for f in self.fears],
            "fear_memory": [round(e.fear_memory, 3) for e in self.net.edges],
            "edge_stress": [round(st[1] / st[0], 3) if st[0] else None for st in self.edge_stats],
            "metrics": self.metrics(),
        })

    def history_json(self, since=0):
        return json.dumps([[c, round(a, 4), round(co, 4), round(v, 4)] for c, a, co, v in self.history[since:]])


# ---------------------------------------------------------------------------
# Wczytywanie danych do modelu (wspólne dla CLI i przeglądarki)
# ---------------------------------------------------------------------------

def load_inputs(roads_data=None, obstacles_data=None, roads_name="", obstacles_name=""):
    """Bajty/tekst plików -> (roads, obstacles, boundary). Obsługuje .shp i .geojson/.json."""
    roads, obstacles, boundary = [], [], []

    def feats_of(data, name):
        if name.lower().endswith(".shp"):
            return [("roads" if k == "line" else "obstacles" if k == "polygon" else "point", parts)
                    for k, parts in read_shp(bytes(data))]
        text = data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else data
        obj = json.loads(text)
        if obj.get("elements") is not None:
            return osm_to_features(obj)
        return geojson_features(obj)

    feats = []
    if roads_data is not None:
        feats += feats_of(roads_data, roads_name)
    if obstacles_data is not None:
        # w pliku przeszkód linie też są przeszkodami (np. żywopłoty)
        for k, parts in feats_of(obstacles_data, obstacles_name):
            if k in ("line", "roads"):
                for part in parts:
                    feats.append(("obstacles", [part + part[::-1][1:]]))
            elif k != "point":
                feats.append(("obstacles", parts))
    if feats and looks_geographic([p for _k, parts in feats for part in parts for p in part]):
        feats = project_lonlat(feats)
    roads, obstacles, boundary = split_layers(feats)
    if not roads:
        raise ValueError("w danych nie ma ścieżek (linii)")
    return roads, obstacles, boundary


def load_files(roads_path, obstacles_path=None):
    with open(roads_path, "rb") as f:
        rd = f.read()
    od = None
    if obstacles_path:
        with open(obstacles_path, "rb") as f:
            od = f.read()
    return load_inputs(rd, od, roads_path, obstacles_path or "")


# ---------------------------------------------------------------------------
# Eksperymenty: przegląd parametrów, eksperyment nasadzeń, analiza wrażliwości
# ---------------------------------------------------------------------------

OUTPUTS = ["total_adrenaline", "total_cortisol", "total_vigilance", "fear_events", "fear_markers",
           "feared_edges", "max_fear_memory", "edge_stress_sd", "n_bushes", "bush_area"]

# parametry analizy wrażliwości: (dolna, górna granica dla LHS); OAT zmienia wartość bazową o ±delta.
# Dla współczynników wygaszania zaburzana jest szybkość wygaszania 1 - c, a nie samo c.
SENS_PARAMS = {
    "adrenaline_threshold": (8.0, 15.0),
    "adrenaline_cooldown": (0.98, 0.995),
    "cortisol_cooldown": (0.998, 0.9995),
    "hall_multiplier": (3.0, 5.0),
    "aversion_strength": (0.0, 10.0),
    "fear_deposit": (0.5, 2.0),
    "fear_decay": (0.995, 0.9999),
    "bot_nb": (40, 120),
}
RATE_PARAMS = {"adrenaline_cooldown", "cortisol_cooldown", "fear_decay"}


def batch_plan(sweep, repeat, base_seed):
    """sweep: {parametr: [wartości]} -> lista (nadpisania, seed, etykieta); iloczyn kartezjański × powtórzenia."""
    keys = list(sweep)
    combos = [{}]
    for k in keys:
        combos = [dict(c, **{k: v}) for c in combos for v in sweep[k]]
    plan = []
    for c in combos:
        for r in range(repeat):
            # ten sam seed dla danego powtórzenia we wszystkich wariantach (wspólne liczby losowe)
            plan.append((c, base_seed + r, ""))
    return plan


def planting_plan(distances=(1.0, 4.0, 8.0, 12.0), shares=(0.0, 0.5, 1.0), repeat=5, base_seed=1, planting_seeds=1):
    """Eksperyment nasadzeń: stała powierzchnia krzewów, zmienny odstęp od skrzyżowań i udział w narożnikach.

    planting_seeds > 1 powtarza każdy wariant na kilku losowaniach nasadzeń (seed nasadzeń = seed przebiegu).
    """
    sweep = {"bush_junction_distance": list(distances), "bush_junction_share": list(shares)}
    plan = []
    for c, seed, _l in batch_plan(sweep, repeat, base_seed):
        c = dict(c, planting="controlled")
        if planting_seeds > 1:
            c["planting_seed"] = 1 + (seed - base_seed) % planting_seeds
        plan.append((c, seed, ""))
    return plan


def _perturb(name, base, delta, sign):
    if name in RATE_PARAMS:
        return 1.0 - (1.0 - base) * (1.0 + sign * delta)
    v = base * (1.0 + sign * delta)
    return int(round(v)) if isinstance(DEFAULTS[name], int) else v


def oat_plan(names=None, delta=0.1, repeat=5, base_seed=1, params=None):
    """Wrażliwość lokalna (one-at-a-time): baza + każdy parametr ±delta, te same seedy."""
    names = list(names or SENS_PARAMS)
    base = resolved_params(params)
    plan = []
    for r in range(repeat):
        plan.append(({}, base_seed + r, "base"))
    for n in names:
        for sign, tag in ((-1, "-"), (1, "+")):
            v = _perturb(n, base[n], delta, sign)
            for r in range(repeat):
                plan.append(({n: v}, base_seed + r, n + tag))
    return plan


def lhs_plan(names=None, n=40, base_seed=1):
    """Wrażliwość globalna: próbkowanie hipersześcianu łacińskiego w zakresach SENS_PARAMS."""
    names = list(names or SENS_PARAMS)
    rng = random.Random(base_seed * 7919 + 17)
    cols = {}
    for name in names:
        lo, hi = SENS_PARAMS[name]
        strata = [(k + rng.random()) / n for k in range(n)]
        rng.shuffle(strata)
        vals = [lo + (hi - lo) * u for u in strata]
        if isinstance(DEFAULTS[name], int):
            vals = [int(round(v)) for v in vals]
        cols[name] = vals
    return [({name: cols[name][i] for name in names}, base_seed + i, "lhs") for i in range(n)]


def make_model(overrides, seed, cycles, params=None, inputs=None):
    pp = dict(params or {})
    pp.update(overrides)
    pp["end_cycle"] = cycles
    if inputs:
        return Model(pp, seed=seed, roads=inputs[0], obstacles=inputs[1], boundary=inputs[2])
    return Model(pp, seed=seed)


def result_row(i, model, overrides, label=""):
    m = model.metrics()
    row = {"run": i, "seed": model.seed, "label": label, "cycles": model.cycle}
    for k in sorted(overrides):
        row[k] = overrides[k]
    for k in OUTPUTS:
        v = m[k]
        row[k] = round(v, 4) if isinstance(v, float) else v
    if model.planting_info:
        row["junction_share_real"] = model.planting_info["junction_share"]
    return row


def run_plan(plan, cycles=3000, params=None, inputs=None, progress=None):
    rows = []
    for i, (overrides, seed, label) in enumerate(plan):
        model = make_model(overrides, seed, cycles, params, inputs).run()
        rows.append(result_row(i, model, overrides, label))
        if progress:
            progress(i + 1, len(plan))
    return rows


def run_batch(sweep, repeat=3, cycles=3000, base_seed=1, params=None, inputs=None, progress=None):
    return run_plan(batch_plan(sweep, repeat, base_seed), cycles, params, inputs, progress)


def dict_rows_csv(rows):
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=keys)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def rows_csv(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def group_summary(rows, keys, outputs=None):
    """Średnia ± SD wyników w grupach o tych samych wartościach keys."""
    outputs = outputs or ["total_adrenaline", "total_cortisol", "total_vigilance", "fear_events", "edge_stress_sd"]
    groups = {}
    for r in rows:
        groups.setdefault(tuple(r.get(k) for k in keys), []).append(r)
    out = []
    for g, rs in groups.items():
        row = dict(zip(keys, g))
        row["n"] = len(rs)
        for o in outputs:
            vals = [r[o] for r in rs]
            row[o + "_mean"] = round(sum(vals) / len(vals), 4)
            row[o + "_sd"] = round(_sd(vals), 4)
        out.append(row)
    return out


def oat_analysis(rows, params=None, outputs=None):
    """Elastyczności: (ΔY / Y_baza) / (ΔX / X_baza) z różnicy centralnej (średnie po powtórzeniach)."""
    outputs = outputs or ["total_adrenaline", "total_cortisol", "total_vigilance", "fear_events"]
    base = resolved_params(params)
    by = {}
    for r in rows:
        by.setdefault(r["label"], []).append(r)
    mean = lambda rs, o: sum(r[o] for r in rs) / len(rs)
    out = []
    names = [l[:-1] for l in by if l.endswith("+")]
    for n in names:
        lo, hi = by.get(n + "-"), by.get(n + "+")
        if not lo or not hi or "base" not in by:
            continue
        x0 = (1.0 - base[n]) if n in RATE_PARAMS else base[n]
        xl = (1.0 - lo[0][n]) if n in RATE_PARAMS else lo[0][n]
        xh = (1.0 - hi[0][n]) if n in RATE_PARAMS else hi[0][n]
        row = {"parameter": n + (" (1 - c)" if n in RATE_PARAMS else ""), "base": round(x0, 6),
               "low": round(xl, 6), "high": round(xh, 6)}
        for o in outputs:
            y0 = mean(by["base"], o)
            dy = mean(hi, o) - mean(lo, o)
            dx = xh - xl
            row[o] = round((dy / y0) / (dx / x0), 3) if y0 and dx and x0 else float("nan")
        out.append(row)
    return out


def lhs_analysis(rows, names=None, outputs=None):
    """Korelacja rang Spearmana parametr–wynik w próbie LHS."""
    names = list(names or [k for k in SENS_PARAMS if rows and k in rows[0]])
    outputs = outputs or ["total_adrenaline", "total_cortisol", "total_vigilance", "fear_events"]
    out = []
    for n in names:
        row = {"parameter": n}
        for o in outputs:
            row[o] = round(spearman([r[n] for r in rows], [r[o] for r in rows]), 3)
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Testy
# ---------------------------------------------------------------------------

def _square_net():
    # kwadrat 100 x 100 m z dwiema trasami z (0,0) do (100,100)
    return [[(0, 0), (100, 0)], [(100, 0), (100, 100)], [(0, 0), (0, 100)], [(0, 100), (100, 100)]]


def _tiny_model(params=None, obstacles=None, seed=1):
    pp = {"bot_nb": 0, "phantom_nb": 1}
    pp.update(params or {})
    return Model(pp, seed=seed, roads=_square_net(), obstacles=obstacles or [], boundary=[])


def test_defaults_match_gaml():
    p = resolved_params()
    assert abs(p["intimate"] - 1.8) < 1e-9 and abs(p["personal"] - 4.8) < 1e-9
    assert abs(p["social"] - 14.4) < 1e-9 and abs(p["public"] - 40.0) < 1e-9
    assert p["bot_nb"] == 80 and p["phantom_nb"] == 1 and p["end_cycle"] == 10000
    m = _tiny_model()
    assert abs(m.step_s - 0.3) < 1e-12
    assert abs(m.phantoms[0].speed - 4 / 3.6) < 1e-12


def test_zero_aversion_weights_equal_length():
    m = _tiny_model({"aversion_strength": 0.0})
    for e in m.net.edges:
        e.fear_memory = 3.0
    m.rebuild_graph()
    assert all(abs(e.weight - e.length) < 1e-12 for e in m.net.edges)


def test_weights_formula():
    m = _tiny_model({"aversion_strength": 5.0})
    e = m.net.edges[0]
    e.fear_memory = 2.0
    m.rebuild_graph()
    assert abs(e.weight - e.length * (1 + 5.0 * 2.0)) < 1e-9


def test_route_avoids_feared_edge():
    m = _tiny_model({"aversion_strength": 5.0})
    net = m.net
    e_bottom, e_right, e_left, e_top = net.edges
    src = (e_bottom, 0.0)
    dst = (e_top, 100.0)          # punkt (100,100)
    e_bottom.weight = e_bottom.length * 1.0
    r1 = net.route(src, dst)
    # obie trasy mają 200 m; po nałożeniu strachu na prawą ścianę wybrana jest lewa
    e_right.fear_memory = 1.0
    m.rebuild_graph()
    r2 = net.route(src, dst)
    assert all(leg[0] is not e_right for leg in r2), r2
    assert abs(sum(abs(l[2] - l[1]) for l in r2) - 200.0) < 1e-9
    assert r1 is not None


def test_mover_follows_route_and_arrives():
    m = _tiny_model({"phantom_nb": 1, "aversion_strength": 0.0})
    ph = m.phantoms[0]
    ph.edge, ph.s = m.net.edges[0], 0.0
    ph.loc = (0.0, 0.0)
    ph.target = (m.net.edges[1], 50.0)
    ph.target_loc = (100.0, 50.0)
    ph.route = None
    steps = 0
    while dist(ph.loc, ph.target_loc) >= 1.0 and steps < 1000:
        ph.goto(m)
        steps += 1
    expected = 149.0 / (ph.speed * m.step_s)
    assert abs(steps - expected) <= 2, (steps, expected)


def test_zones_and_line_of_sight():
    bush = [[(20, 1), (22, 1), (22, 9), (20, 9), (20, 1)]]
    m = _tiny_model(obstacles=[bush])
    ph = m.phantoms[0]
    ph.loc = (10.0, 5.0)
    m._ignore = set()
    assert ph.distance_number(m, (11.0, 5.0)) == 4
    assert ph.distance_number(m, (13.0, 5.0)) == 3
    assert ph.distance_number(m, (10.0, 17.0)) == 2
    assert ph.distance_number(m, (10.0, 40.0)) == 1
    assert ph.distance_number(m, (10.0, 56.0)) == 0
    # za krzakiem: zasłonięte
    assert ph.distance_number(m, (30.0, 5.0)) == 0
    assert ph.distance_number(m, (30.0, 25.0)) == 1
    # wewnątrz krzaka: zasłonięte
    assert ph.distance_number(m, (21.0, 5.0)) == 0


def test_psychophysiology_equations():
    m = _tiny_model({"bot_nb": 2})
    ph = m.phantoms[0]
    ph.loc = (50.0, 0.0)
    ph.edge, ph.s = m.net.edges[0], 50.0
    m.bots[0].loc = (95.0, 0.0)      # poza public
    m.bots[1].loc = (50.0, 30.0)     # public
    ph.update_psychophysiology(m)
    assert ph.where_are_they == [0, 1]
    assert ph.vigilance == 0.0       # pierwsze wywołanie: brak where_were_they
    c = 0.5 * 0.999
    c = c + 0.2 * 0.5 / ((c + 1) ** 2)
    assert abs(ph.cortisol - c) < 1e-12
    assert abs(ph.adrenaline - 0.5 * 0.99) < 1e-12
    m.bots[0].loc = (51.0, 0.0)      # 0 -> 4: 16 - 0.99
    m.bots[1].loc = (50.0, 10.0)     # 1 -> 2: 1 - 0.99
    a_prev = ph.adrenaline
    ph.update_psychophysiology(m)
    assert abs(ph.vigilance - (15.01 + 0.01)) < 1e-9
    assert abs(ph.adrenaline - (a_prev * 0.99 + ph.vigilance)) < 1e-12
    # oddalanie się nie daje czujności
    m.bots[0].loc = (95.0, 0.0)
    ph.update_psychophysiology(m)
    assert ph.vigilance == 0.0


def test_fear_deposit_and_marker_spacing():
    m = _tiny_model({"bot_nb": 1, "fear_deposit": 1.0})
    ph = m.phantoms[0]
    ph.loc = (50.0, 0.0)
    ph.edge, ph.s = m.net.edges[0], 50.0
    ph.adrenaline = 20.0
    m.bots[0].loc = (90.0, 90.0)
    ph.update_psychophysiology(m)
    assert m.net.edges[0].fear_memory == 1.0 and len(m.fears) == 1
    ph.loc = (55.0, 0.0)            # 5 m od znacznika: bez nowego znacznika, ale depozyt jest
    ph.update_psychophysiology(m)
    assert m.net.edges[0].fear_memory == 2.0 and len(m.fears) == 1
    ph.loc = (70.0, 0.0)
    ph.update_psychophysiology(m)
    assert len(m.fears) == 2


def test_decay_every_reweight():
    m = _tiny_model({"reweight_every": 20, "fear_decay": 0.5, "end_cycle": 100})
    m.net.edges[0].fear_memory = 8.0
    m.phantoms = []
    m.step()                          # cykl 0: zanikanie
    assert m.net.edges[0].fear_memory == 4.0
    for _ in range(19):
        m.step()
    assert m.net.edges[0].fear_memory == 4.0
    m.step()                          # cykl 20
    assert m.net.edges[0].fear_memory == 2.0


def test_end_and_summary():
    m = Model({"bot_nb": 5, "end_cycle": 50, "park_bushes": 10}, seed=3)
    m.run()
    assert m.finished is False and m.cycle == 50
    assert m.step() is False and m.finished
    assert len(m.summary_rows) == 1
    ph = m.phantoms[0]
    # zapis w cyklu 49 przed ruchem agentów: sumy z 49 kroków
    assert m.summary_rows[0][:2] == [5, 1]
    assert m.summary_rows[0][2] <= ph.total_adrenaline
    assert m.summary_csv().splitlines()[0] == ",".join(SUMMARY_HEADER)


def test_determinism():
    a = Model({"bot_nb": 20, "end_cycle": 300}, seed=7).run().metrics()
    b = Model({"bot_nb": 20, "end_cycle": 300}, seed=7).run().metrics()
    assert a == b


def test_generated_park_connected():
    for s in range(1, 6):
        roads, obs, _b = generate_park(s)
        net = Network(roads, largest_component=False)
        assert net.n_components() == 1, s
        assert len(obs) > 20
        o = Obstacles(obs)
        # żaden wierzchołek alejki nie leży w krzaku
        for r in roads:
            for p in r:
                assert not o.containing(p)


def test_shp_roundtrip():
    lines = [[[(0.0, 0.0), (10.0, 0.0)]], [[(10.0, 0.0), (10.0, 10.0), (20.0, 10.0)]]]
    polys = [[[(2.0, 2.0), (4.0, 2.0), (4.0, 4.0), (2.0, 2.0)]]]
    roads, obstacles, _b = load_inputs(write_shp(lines, "line"), write_shp(polys, "polygon"), "r.shp", "o.shp")
    assert roads == [[(0.0, 0.0), (10.0, 0.0)], [(10.0, 0.0), (10.0, 10.0), (20.0, 10.0)]]
    assert obstacles == [[[(2.0, 2.0), (4.0, 2.0), (4.0, 4.0), (2.0, 2.0)]]]
    net = Network(roads)
    assert len(net.nodes) == 3 and net.n_components() == 1


def test_osm_conversion_splits_at_junctions():
    g = lambda lon, lat: {"lon": lon, "lat": lat}
    osm = {"elements": [
        {"type": "way", "id": 1, "tags": {"highway": "footway"}, "nodes": [1, 2, 3],
         "geometry": [g(17.0, 51.1), g(17.001, 51.1), g(17.002, 51.1)]},
        {"type": "way", "id": 2, "tags": {"highway": "path"}, "nodes": [2, 4],
         "geometry": [g(17.001, 51.1), g(17.001, 51.101)]},
        {"type": "way", "id": 3, "tags": {"natural": "scrub"}, "nodes": [5, 6, 7, 5],
         "geometry": [g(17.0005, 51.1002), g(17.0007, 51.1002), g(17.0006, 51.1004), g(17.0005, 51.1002)]},
        {"type": "way", "id": 4, "tags": {"leisure": "park", "name": "Park Testowy"}, "nodes": [8, 9, 10, 8],
         "geometry": [g(16.999, 51.099), g(17.003, 51.099), g(17.003, 51.102), g(16.999, 51.099)]},
    ]}
    roads, obstacles, boundary = load_inputs(json.dumps(osm), None, "park.json")
    assert len(roads) == 3, roads          # droga 1 podzielona w węźle 2
    assert len(obstacles) == 1 and len(boundary) == 1
    net = Network(roads)
    assert net.n_components() == 1 and len(net.nodes) == 4
    # ok. 70 m na 0.001° długości przy 51.1° N
    assert 65 < net.edges[0].length < 75, net.edges[0].length
    gj = features_to_geojson(osm_to_features(osm))
    back = load_inputs(json.dumps(gj), None, "park.geojson")
    assert len(back[0]) == 3 and len(back[1]) == 1


def test_query_mentions_park_and_city():
    q = overpass_query("Park Staszica")
    assert "Park Staszica" in q and "Wrocław" in q and "scrub" in q


def test_bots_share_weighted_graph():
    m = _tiny_model({"bot_nb": 3, "aversion_strength": 5.0})
    m.net.edges[1].fear_memory = 1.0
    v = m.graph_version
    m.rebuild_graph()
    assert m.graph_version == v + 1
    for b in m.bots:
        b.route = []
        b.route_ver = v
        b.target_loc = (1000.0, 1000.0)
        b.goto(m)
        assert b.route_ver == m.graph_version


def test_full_default_run_smoke():
    m = Model({"end_cycle": 400}, seed=11)
    t = time.time()
    m.run()
    assert m.cycle == 400
    assert m.phantoms[0].total_cortisol > 0
    assert time.time() - t < 60


def test_individual_memory_equals_shared_for_one_phantom():
    a = Model({"bot_nb": 30, "end_cycle": 1500}, seed=3).run().metrics()
    b = Model({"bot_nb": 30, "end_cycle": 1500, "fear_scope": "individual"}, seed=3).run().metrics()
    assert a == b


def test_individual_memory_is_separate():
    m = _tiny_model({"phantom_nb": 2, "fear_scope": "individual", "aversion_strength": 5.0})
    p0, p1 = m.phantoms
    p0.fear[1] = 2.0
    m.net.edges[1].fear_memory = 2.0
    m.rebuild_graph()
    assert abs(p0.weights[1] - 100.0 * 11.0) < 1e-9
    assert p1.weights[1] == 100.0
    assert p0.route_weights(m) is p0.weights


def test_plain_bot_graph_ignores_fear():
    m = _tiny_model({"bot_nb": 1, "bot_graph": "plain", "aversion_strength": 5.0})
    m.net.edges[1].fear_memory = 10.0
    m.rebuild_graph()
    bot = m.bots[0]
    assert bot.route_weights(m) == m.net.lengths
    r = m.net.route((m.net.edges[0], 90.0), (m.net.edges[3], 99.0), bot.route_weights(m))
    assert any(leg[0] is m.net.edges[1] for leg in r)   # krótsza droga przez "straszny" odcinek
    m2 = _tiny_model({"bot_nb": 1, "aversion_strength": 5.0})
    assert m2.bots[0].route_weights(m2) is None           # domyślnie jak w GAMA: graf ważony


def test_edge_stats_accumulate():
    m = Model({"bot_nb": 10, "end_cycle": 200, "phantom_nb": 2}, seed=2).run()
    assert sum(st[0] for st in m.edge_stats) == 200 * 2
    ev = sum(st[3] for st in m.edge_stats)
    assert ev == sum(ph.fear_events for ph in m.phantoms)
    assert m.edge_csv().splitlines()[0].startswith("edge_id,length_m,phantom_cycles")


def test_controlled_planting_constant_area():
    roads, _o, _b = generate_park(2)
    areas = []
    for d in (1.0, 6.0, 12.0):
        for share in (0.0, 0.5, 1.0):
            p = resolved_params({"planting": "controlled", "bush_junction_distance": d, "bush_junction_share": share})
            obs, info = plant_bushes(roads, p)
            areas.append(info["area"])
            r, off = p["bush_radius"], p["bush_path_offset"]
            idx = SegIndex(roads)
            js = [n for n, _a in junctions(roads)]
            for rings in obs:
                ring = rings[0]
                c = (sum(q[0] for q in ring[:-1]) / (len(ring) - 1), sum(q[1] for q in ring[:-1]) / (len(ring) - 1))
                assert idx.nearest(c) >= r + off - 1e-6
                dj = min(dist(c, q) for q in js)
                # narożny: krawędź >= d od węzła; przy ścieżce: poza strefą skrzyżowania
                assert dj - r >= min(d, p["junction_zone"]) - 1e-6, (d, dj)
            if share == 0.0:
                assert info["n_junction"] == 0
    one = ring_area(circle_ring((0, 0), 4.0))
    assert max(areas) - min(areas) <= one + 1e-6, areas
    assert abs(areas[0] - 2500.0) <= one


def test_isovist_open_and_blocked():
    empty = Obstacles([])
    area, mean_ray, blocked = isovist((0.0, 0.0), empty, 10.0, 72)
    assert abs(area - math.pi * 100) / (math.pi * 100) < 0.01 and blocked == 0.0 and mean_ray == 10.0
    wall = Obstacles([[[(2.0, -50.0), (3.0, -50.0), (3.0, 50.0), (2.0, 50.0), (2.0, -50.0)]]])
    area2, _m, blocked2 = isovist((0.0, 0.0), wall, 10.0, 72)
    # ściana x = 2 zasłania promienie o |kąt| < acos(0.2) ≈ 78.5° (ok. 44%)
    assert 0.4 < blocked2 < 0.47 and area2 < 0.65 * area


def test_spearman():
    assert abs(spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1.0) < 1e-12
    assert abs(spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-12
    assert abs(spearman([1, 2, 3, 4, 5], [2, 1, 4, 3, 5]) - 0.8) < 1e-12


def test_oat_plan_and_elasticity():
    plan = oat_plan(["hall_multiplier", "adrenaline_cooldown"], 0.1, 2, 1)
    labels = [l for _o, _s, l in plan]
    assert labels.count("base") == 2 and labels.count("hall_multiplier+") == 2
    hm = [o["hall_multiplier"] for o, _s, l in plan if l == "hall_multiplier-"]
    assert abs(hm[0] - 3.6) < 1e-9
    ac = [o["adrenaline_cooldown"] for o, _s, l in plan if l == "adrenaline_cooldown+"]
    assert abs((1 - ac[0]) - 0.011) < 1e-12      # zaburzana szybkość wygaszania
    # sztuczne wyniki: Y = 100 * hall_multiplier -> elastyczność 1
    rows = []
    for o, _s, l in plan:
        hmv = o.get("hall_multiplier", 4.0)
        rows.append(dict(o, label=l, total_adrenaline=100 * hmv, total_cortisol=1.0,
                         total_vigilance=1.0, fear_events=1.0))
    an = {r["parameter"]: r for r in oat_analysis(rows)}
    assert abs(an["hall_multiplier"]["total_adrenaline"] - 1.0) < 1e-9
    assert an["hall_multiplier"]["total_cortisol"] == 0.0


def test_lhs_plan_stratified():
    plan = lhs_plan(["adrenaline_threshold", "bot_nb"], 10, 1)
    vals = sorted(o["adrenaline_threshold"] for o, _s, _l in plan)
    for k, v in enumerate(vals):
        assert 8.0 + 0.7 * k <= v <= 8.0 + 0.7 * (k + 1)
    assert all(isinstance(o["bot_nb"], int) for o, _s, _l in plan)
    assert len({s for _o, s, _l in plan}) == 10


def test_run_plan_rows():
    rows = run_plan(planting_plan((2.0,), (0.0, 1.0), 1, 1), cycles=100)
    assert len(rows) == 2 and rows[0]["bush_junction_share"] == 0.0 and rows[1]["planting"] == "controlled"
    assert abs(rows[0]["bush_area"] - rows[1]["bush_area"]) <= ring_area(circle_ring((0, 0), 4.0)) + 1e-6
    assert "total_adrenaline" in dict_rows_csv(rows).splitlines()[0]
    summ = group_summary(rows, ["bush_junction_share"])
    assert len(summ) == 2 and summ[0]["n"] == 1


TESTS = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]


def run_tests(names=None):
    results = []
    for name, fn in TESTS:
        if names and name not in names:
            continue
        t = time.time()
        try:
            fn()
            results.append((name, True, "", round(time.time() - t, 3)))
        except Exception as ex:  # noqa: BLE001 - raport testu
            results.append((name, False, "%s: %s" % (type(ex).__name__, ex), round(time.time() - t, 3)))
    return results


def run_tests_json():
    return json.dumps(run_tests())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_list(s, cast=float):
    return [cast(x) for x in s.split(",") if x.strip()]


def _cast(k, v):
    d = DEFAULTS.get(k)
    if k in CHOICES:
        return v
    if isinstance(d, bool):
        return v.lower() in ("1", "true", "yes", "tak")
    if isinstance(d, int):
        return int(float(v))
    return float(v)


def _write(path, text):
    if path:
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)


def _table(rows):
    if not rows:
        return ""
    keys = list(rows[0])
    return "\n".join(["\t".join(keys)] + ["\t".join(str(r.get(k, "")) for k in keys) for r in rows])


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description="PSM – Proxemic Stress Model z awersją do tras (port GAMA).")
    ap.add_argument("--test", action="store_true", help="uruchom testy")
    ap.add_argument("--run", action="store_true", help="pojedynczy przebieg")
    ap.add_argument("--batch", action="store_true", help="przegląd parametrów (--sweep, --aversion, --bots)")
    ap.add_argument("--planting-experiment", action="store_true",
                    help="nasadzenia przy stałej powierzchni: odstęp od skrzyżowań × udział w narożnikach")
    ap.add_argument("--sensitivity", choices=["oat", "lhs"], help="analiza wrażliwości stałych modelu")
    ap.add_argument("--fetch-osm", metavar="NAZWA", help="pobierz park z OpenStreetMap (Overpass) i zapisz GeoJSON")
    ap.add_argument("--city", default="Wrocław")
    ap.add_argument("--out", default="park.geojson")
    ap.add_argument("--roads", help="plik ścieżek: .shp, .geojson albo odpowiedź Overpass .json")
    ap.add_argument("--obstacles", help="plik przeszkód: .shp albo .geojson")
    ap.add_argument("--cycles", type=int, default=None)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--sweep", action="append", default=[], metavar="PARAM=W1,W2",
                    help="przegląd dowolnego parametru (można podać kilka razy)")
    ap.add_argument("--aversion", default=None, help="skrót: --sweep aversion_strength=...")
    ap.add_argument("--bots", default=None, help="skrót: --sweep bot_nb=...")
    ap.add_argument("--distances", default="1,4,8,12", help="eksperyment nasadzeń: bush_junction_distance (m)")
    ap.add_argument("--shares", default="0,0.5,1", help="eksperyment nasadzeń: bush_junction_share")
    ap.add_argument("--planting-seeds", type=int, default=1, help="ile losowań nasadzeń na wariant")
    ap.add_argument("--params", default=None, help="parametry wrażliwości, np. adrenaline_threshold,hall_multiplier")
    ap.add_argument("--delta", type=float, default=0.1, help="OAT: względna zmiana parametru")
    ap.add_argument("--samples", type=int, default=40, help="LHS: liczba próbek")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--isovist", action="store_true", help="--run: policz izowisty i korelację ze stresem")
    ap.add_argument("--set", action="append", default=[], metavar="KLUCZ=WARTOŚĆ")
    ap.add_argument("--csv", default=None, help="plik wynikowy CSV (wiersz = przebieg)")
    ap.add_argument("--summary", default=None, help="plik CSV z podsumowaniem (średnie, elastyczności, korelacje)")
    ap.add_argument("--edges", default=None, help="--run: mapa stresu i widoczności na odcinkach (CSV)")
    a = ap.parse_args(argv)

    params = {}
    for kv in a.set:
        k, v = kv.split("=", 1)
        params[k] = _cast(k, v)

    if a.test:
        res = run_tests()
        for name, ok, msg, t in res:
            print("%s %-45s %6.2fs %s" % ("OK  " if ok else "FAIL", name, t, msg))
        bad = sum(1 for r in res if not r[1])
        print("%d/%d testów przeszło" % (len(res) - bad, len(res)))
        return 1 if bad else 0

    if a.fetch_osm:
        osm = fetch_osm(a.fetch_osm, a.city)
        feats = osm_to_features(osm)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(features_to_geojson(feats), f)
        roads, _o, _b = split_layers(feats)
        print("zapisano %s: %d odcinków ścieżek, %d przeszkód" % (a.out, len(roads),
                                                               sum(1 for k, _ in feats if k == "obstacles")))
        return 0

    inputs = load_files(a.roads, a.obstacles) if a.roads else None
    prog = lambda i, n: print("\r%d/%d" % (i, n), end="", file=sys.stderr)

    if a.run:
        if a.cycles:
            params["end_cycle"] = a.cycles
        kw = dict(roads=inputs[0], obstacles=inputs[1], boundary=inputs[2]) if inputs else {}
        m = Model(params, seed=a.seed, **kw)
        t = time.time()
        m.run()
        m.step()
        print("przebieg: %d cykli w %.1f s, sieć: %d krawędzi, %d składowych" %
              (m.cycle, time.time() - t, len(m.net.edges), m.net.n_components()))
        if m.planting_info:
            print("nasadzenia:", json.dumps(m.planting_info))
        print(json.dumps(m.metrics(), indent=1))
        if a.isovist:
            t = time.time()
            cmp_ = m.isovist_comparison()
            print("izowisty vs stres (Spearman, %.1f s):" % (time.time() - t),
                  json.dumps({k: round(v, 3) for k, v in cmp_.items()}))
        if a.edges:
            _write(a.edges, m.edge_csv())
        if a.csv:
            _write(a.csv, m.summary_csv())
        return 0

    cycles = a.cycles or 3000
    if a.batch or a.planting_experiment or a.sensitivity:
        if a.batch:
            sweep = {}
            for kv in a.sweep:
                k, v = kv.split("=", 1)
                sweep[k] = [_cast(k, x) for x in v.split(",") if x.strip()]
            if a.aversion:
                sweep["aversion_strength"] = _parse_list(a.aversion)
            if a.bots:
                sweep["bot_nb"] = _parse_list(a.bots, int)
            if not sweep:
                sweep = {"aversion_strength": [0.0, 5.0]}
            plan = batch_plan(sweep, a.repeat, a.seed)
            keys = list(sweep)
        elif a.planting_experiment:
            plan = planting_plan(_parse_list(a.distances), _parse_list(a.shares), a.repeat, a.seed, a.planting_seeds)
            keys = ["bush_junction_distance", "bush_junction_share"]
        elif a.sensitivity == "oat":
            plan = oat_plan(a.params.split(",") if a.params else None, a.delta, a.repeat, a.seed, params)
        else:
            plan = lhs_plan(a.params.split(",") if a.params else None, a.samples, a.seed)
        rows = run_plan(plan, cycles, params, inputs, prog)
        print(file=sys.stderr)
        if a.csv:
            _write(a.csv, dict_rows_csv(rows))
        if a.sensitivity == "oat":
            summ = oat_analysis(rows, params)
        elif a.sensitivity == "lhs":
            summ = lhs_analysis(rows, a.params.split(",") if a.params else None)
        else:
            summ = group_summary(rows, keys)
        print(_table(summ))
        if a.summary:
            _write(a.summary, dict_rows_csv(summ))
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
