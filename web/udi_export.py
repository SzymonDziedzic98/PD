"""
Eksport parków z OSM po poprawkach (łączenie kawałków, uproszczenie sieci) i wariantów nasadzeń E1 do GeoJSON (WGS84).

Dla każdego parku: sciezki.geojson (same ścieżki) oraz osobny plik na każdy wariant nasadzeń
(gęstość × forma × odsunięcie, plus kontrola), bez ścieżek. Warianty są takie jak w udi_parks.py (planting_seed 1).

    python udi_export.py PARK.geojson [PARK2.geojson ...] --out DIR
"""

import argparse
import csv
import json
import math
import os
import sys

import psm
import udi_experiments as ue
import udi_parks as up

FORM_PL = {"clumps": "kepy", "band": "pas"}


def origin(path):
    """Ten sam środek rzutu co psm.project_lonlat dla tego pliku."""
    with open(path, encoding="utf-8") as f:
        feats = psm.geojson_features(json.load(f))
    pts = [p for _k, parts in feats for part in parts for p in part]
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def unproject(lon0, lat0):
    kx = 6371008.8 * math.pi / 180.0 * math.cos(math.radians(lat0))
    ky = 6371008.8 * math.pi / 180.0
    return lambda q: [round(lon0 + q[0] / kx, 7), round(lat0 + q[1] / ky, 7)]


def write_fc(path, features):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)


def export_park(path, out):
    name = up.park_name(path)
    roads = up.load(path)[0]
    info = dict(psm.LOAD_INFO)
    ll = unproject(*origin(path))
    d = os.path.join(out, name)
    os.makedirs(d, exist_ok=True)
    write_fc(os.path.join(d, "sciezki.geojson"), [
        {"type": "Feature", "properties": {"layer": "roads", "length_m": round(psm.polyline_length(r), 1)},
         "geometry": {"type": "LineString", "coordinates": [ll(q) for q in r]}} for r in roads])
    nj, length = up.park_stats(path)
    rows = []
    for mult in up.MULTS:
        for form in ue.FORMS:
            for sb in ue.SETBACKS + [None]:
                o = ue.cell(sb, form, 0, {"planting_seed": 1, "bush_area_total": up.REF_DENSITY * nj * mult,
                                          "bush_setback_scope": "all"})
                p = psm.resolved_params(dict(ue.BASE, **o))
                obs, pinfo = psm.plant_bushes(roads, p)
                tag = "kontrola" if sb is None else "odstep%02d" % int(sb)
                fn = "nasadzenia_gestosc%s_%s_%s.geojson" % (("%g" % mult).replace(".", "_"), FORM_PL[form], tag)
                write_fc(os.path.join(d, fn), [
                    {"type": "Feature", "properties": {"layer": "obstacles", "area_m2": round(psm.ring_area(rings[0]), 1)},
                     "geometry": {"type": "Polygon", "coordinates": [[ll(q) for q in ring] for ring in rings]}}
                    for rings in obs])
                rows.append({"park": name, "plik": fn, "gestosc_mnoznik": mult, "gestosc_m2_na_skrzyzowanie":
                             round(up.REF_DENSITY * mult, 1), "forma": FORM_PL[form],
                             "odstep_m": "kontrola" if sb is None else sb, "liczba_krzewow": pinfo["n_bushes"],
                             "powierzchnia_cel_m2": round(pinfo["area_target"]), "powierzchnia_m2": round(pinfo["area"]),
                             "udzial_przy_skrzyzowaniach": pinfo["junction_share"],
                             "odstep_faktyczny_m": pinfo["setback_mean"] if pinfo["setback_mean"] is not None else ""})
    summary = {"park": name, "skrzyzowania": nj, "dlugosc_sciezek_m": round(length),
               "skrzyzowania_przed_uproszczeniem": info.get("junctions_before", ""),
               "dlugosc_przed_m": info.get("length_before", ""), "polaczone_czesci": info.get("parts_before", "")}
    return rows, summary


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parks", nargs="+")
    ap.add_argument("--out", default="parki_po_poprawkach")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    rows, parks = [], []
    for path in a.parks:
        r, s = export_park(path, a.out)
        rows += r
        parks.append(s)
        print(s["park"], len(r), "wariantów", file=sys.stderr)
    ue.write(os.path.join(a.out, "warianty_nasadzen.csv"), rows)
    ue.write(os.path.join(a.out, "parki.csv"), parks)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
