# PSM: Proxemic Stress Model with route aversion

[Polski opis: README.md](README.md)

PSM is an agent-based model of how a lone park visitor reacts to other people nearby. A test agent (the phantom) walks the path network among other visitors (bots). Other people inside the phantom's proxemic zones (Hall's intimate, personal, social and public distances) raise its vigilance, adrenaline and cortisol, but only when no shrub or wall blocks the line of sight. Where adrenaline crosses a threshold, the phantom leaves a fear memory on the path segment, and later routes avoid that segment in proportion to the memory.

The repository holds three versions of the same model:

- `models/Hall_AC_aversion.gaml` is the reference GAMA implementation (authors: Mikołaj Szurlej, Maciej Kamiński).
- `src/psm.py` is a port to plain Python that uses only the standard library. It runs single simulations, parameter sweeps, planting experiments and sensitivity analyses, and it has its own test suite.
- `web/index.html` runs `src/psm.py` in the browser through Pyodide. Nothing has to be installed.

The intended use is to compare design variants of one park before construction, for example the same area of shrubs placed at path junctions or away from them. Results of the Python port match GAMA statistically, not number for number, because the random number generators differ. The remaining differences are listed at the top of `src/psm.py`.

## Quick start

In the browser: open the GitHub Pages site of this repository (`https://szymondziedzic98.github.io/PD/`). The switch in the header changes the interface between Polish and English, and `?lang=en` in the address forces English.

Locally, start a web server in the repository root and open the `web/` folder:

```
python -m http.server
# then open http://localhost:8000/web/
```

The page loads Pyodide (about 10 MB) from a CDN on the first run, so it needs an internet connection.

From the command line (Python 3, no packages needed):

```
python src/psm.py --test
python src/psm.py --run --cycles 10000 --roads paths.geojson --obstacles shrubs.geojson --csv summary.csv --edges edges.csv
python src/psm.py --batch --aversion 0,2.5,5,10 --repeat 5 --cycles 10000 --csv batch_results.csv
python src/psm.py --fetch-osm "Park Staszica" --out park_staszica.geojson
```

Without `--roads` the model uses a generated park (a random grid of alleys with shrubs), set by `park_seed`. `--set key=value` changes any parameter, and `--sweep key=v1,v2` runs every listed value. `python src/psm.py --help` lists all options; the help text is in Polish.

## Loading your own layout

A design variant drawn in QGIS or CAD can be loaded as GeoJSON or as ESRI Shapefile (`.shp` with its `.shx`, `.dbf`, `.prj`).

- Paths are lines (LineString or MultiLineString). Obstacles that block the view, such as shrubs, hedges, walls and buildings, are polygons. In a separate obstacles file, lines are also treated as obstacles (a hedge drawn as a line).
- In one combined GeoJSON file, the feature property `layer` may be `roads`, `obstacles` or `boundary`. Without it, lines become paths and polygons become obstacles.
- Coordinates may be in metres (any projected system, for example EPSG:2180) or in degrees (WGS 84). Degrees are detected automatically and projected locally to metres.
- Paths must meet at shared vertices to form junctions. Disconnected parts of a GeoJSON network are joined by short links up to 50 m (`OSM_BRIDGE_GAP`), and nearby parallel paths and junction clusters are merged. Shapefiles are loaded as drawn. Agents are placed on the largest connected part of the network.

In the browser the same files are chosen in the "Park" panel, and parks from OpenStreetMap can be downloaded by name.

## Planting variants

With `--set planting=controlled` the model places a fixed total area of shrubs (`bush_area_total`, m²) on any network. `bush_form` sets compact clumps (`clumps`) or bands along the path (`band`). The share `bush_junction_share` of that area stands at the corners of junctions, with its edge `bush_junction_distance` metres from the junction node. The rest stands along the paths, outside the junction zone (`junction_zone`, m).

```
python src/psm.py --planting-experiment --distances 0,5,10,15,20 --shares 1 --repeat 10 \
    --cycles 10000 --csv planting.csv --summary planting_means.csv
```

## Example of the SoftwareX paper

`python examples/example_two_variants.py` compares 1500 m² of shrub clumps at junction corners with the same clumps 20 m away (generated park, 50 bots, 10 runs each). It writes the run data and Fig. 3 of the paper to `examples/output/`. Expected totals of phantom adrenaline: 5157 ± 1696 at the junctions and 491 ± 43 at 20 m.

## Outputs

- `--csv` of a single run: the GAMA `summary.csv` with `bot_nb`, `phantom_nb`, `total_adrenaline`, `total_cortisol`, `total_vigilance`.
- `--csv` of a sweep or experiment: one row per run with its seed and changed parameters, and the outputs `total_adrenaline`, `total_cortisol`, `total_vigilance`, `fear_events`, `fear_markers`, `feared_edges`, `max_fear_memory`, `edge_stress_sd`, `n_bushes`, `bush_area`.
- `--summary`: means and standard deviations per variant, OAT elasticities or LHS rank correlations.
- `--edges` of a single run: one row per path segment with `phantom_cycles`, `mean_adrenaline`, `vigilance_sum`, `fear_events`, `fear_memory` and the edge weight. With `--isovist` it adds the visible area around the segment.

The browser app shows the same results as map layers (fear memory, mean adrenaline, isovist field) and a chart of adrenaline, cortisol and vigilance, and downloads them as CSV.

## Parameters that differ from GAMA

Default values reproduce GAMA with one exception. `bot_graph` defaults to `plain`, so bots choose routes by length only and do not know where the phantom was afraid. `bot_graph=weighted` restores the GAMA behaviour. Further options (`fear_scope`, isovists, OAT and LHS sensitivity, `--jobs N` for parallel runs) are described in the Polish README.

## Tests

`python src/psm.py --test` runs 37 tests of the port: the model equations against the GAML source, routing with fear memory, line of sight, file readers, network simplification, planting and the experiment plans. The browser app runs the same tests from its "Tests" tab.
