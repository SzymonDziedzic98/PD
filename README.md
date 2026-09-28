# PD
Proxemics Stress

Model agentowy w GAMA (Proxemic Stress Model) z modyfikacją: sprzężenie zwrotne między stresem a wyborem trasy.

## Model

`models/Hall_AC_aversion.gaml` (autorzy: Mikołaj Szurlej, Maciej Kamiński)

- **Strefy proksemiczne Halla** (intymna, osobista, społeczna, publiczna), skalowane parametrem `hall_multiplier`.
- **Adrenalina i kortyzol**: fantom (agent badany) reaguje na obecność botów w swoich strefach; model śledzi też czujność (vigilance).
- **Awersja do tras**: na odcinkach, na których fantom odczuł strach, odkłada się „pamięć strachu”, która zwiększa wagę krawędzi w grafie. Awersja jest miękka i probabilistyczna, nie blokuje ścieżek.
  - `aversion_strength = 0.0` odtwarza model bazowy.
  - `fear_deposit`, `fear_decay`, `reweight_every` sterują odkładaniem, zanikaniem i przeliczaniem wag.

Symulacja zatrzymuje się po 10 000 cyklach; w cyklu 9999 wyniki są dopisywane do `results/summary.csv`.

## Wersja w Pythonie / w przeglądarce (`web/`)

- `web/psm.py` – port `models/Hall_AC_aversion.gaml` do czystego Pythona (tylko biblioteka standardowa):
  model, przegląd `aversion_strength` (batch), testy, czytnik `.shp`/GeoJSON i import parku z OpenStreetMap.
  - `python web/psm.py --test`
  - `python web/psm.py --run --roads Staszica_SHP_sciezki_01.shp --obstacles Staszica_SHP_krzaki_09.shp`
  - `python web/psm.py --batch --aversion 0,2.5,5,10 --repeat 5 --cycles 10000 --csv batch_results.csv`
  - `python web/psm.py --fetch-osm "Park Staszica" --out park_staszica.geojson` (Overpass API, wymaga internetu)
- `web/index.html` – uruchamia `psm.py` w przeglądarce (Pyodide): mapa parku z pamięcią strachu na ścieżkach,
  strefy Halla phantoma, wykres adrenaliny, kortyzolu i czujności, batch, testy i pobieranie CSV.
  Otwórz przez serwer HTTP, np. `cd web && python -m http.server`, potem `http://localhost:8000`.
  Workflow `.github/workflows/pages.yml` publikuje `web/` na GitHub Pages
  (jednorazowo: Settings → Pages → Source: „GitHub Actions”).

### Rozszerzenia (pod artykuł do URBAN DESIGN International)

Domyślne wartości nowych parametrów dają wyniki identyczne jak wcześniej (jak w GAMA).

- `bot_graph`: `weighted` (jak w GAMA: boty chodzą po tym samym ważonym grafie, więc też omijają odcinki,
  na których phantom się bał) albo `plain` (boty wybierają trasy tylko po długości).
- `fear_scope`: `shared` (jak w GAMA) albo `individual` (każdy phantom ma własną pamięć strachu).
- `planting = controlled`: sterowane nasadzenia przy stałej łącznej powierzchni krzewów (`bush_area_total`),
  w formie zwartych kęp (`bush_form = clumps`) albo pasów wzdłuż ścieżki (`band`).
  Część `bush_junction_share` stoi w narożnikach skrzyżowań, z krawędzią `bush_junction_distance` od węzła,
  reszta wzdłuż ścieżek poza strefą skrzyżowania (`junction_zone`). Działa na każdej sieci (generowanej, OSM, SHP).
- Mapa stresu na odcinkach (`edges.csv`): cykle phantoma, średnia adrenalina, suma czujności, epizody lęku.
- Izowisty co `isovist_spacing` m wzdłuż ścieżek (promień = strefa publiczna) i korelacja rang Spearmana
  widoczność–stres na odcinkach.
- Analiza wrażliwości stałych: OAT (elastyczności przy ±10%) i LHS (korelacje Spearmana);
  wzmocnienie kortyzolu (0,2 w GAML) jest teraz parametrem `cortisol_gain`.
- `--jobs N`: eksperymenty w N procesach (tylko CPython).

```
python web/psm.py --planting-experiment --distances 1,4,8,12 --shares 0,0.5,1 --repeat 10 --planting-seeds 5 \
    --cycles 10000 --csv nasadzenia.csv --summary nasadzenia_srednie.csv
python web/psm.py --planting-experiment --roads Staszica_SHP_sciezki_01.shp        # to samo na ścieżkach parku Staszica
python web/psm.py --sensitivity oat --repeat 10 --cycles 10000 --summary oat.csv
python web/psm.py --sensitivity lhs --samples 100 --cycles 10000 --summary lhs.csv
python web/psm.py --run --isovist --edges edges.csv --set planting=controlled
python web/psm.py --batch --sweep bot_graph=weighted,plain --sweep aversion_strength=0,5 --repeat 10
```

Eksperymenty E1–E3 do artykułu (UDI) są zdefiniowane w `web/udi_experiments.py`, a wykresy tworzy
`web/udi_figures.py` (wymaga matplotlib):

```
python web/udi_experiments.py e1 e1b e2 e3 --jobs 4 --out wyniki_PSM_UDI
python web/udi_figures.py wyniki_PSM_UDI
```

- E1: odsunięcie krzewów od skrzyżowań 0/5/10/15/20 m × forma (kępy, pas) × 20/50/80 odwiedzających
  × 50 powtórzeń; 1500 m² krzewów; kontrola = ta sama powierzchnia poza strefą skrzyżowań.
- E1b: to samo na 10 innych sieciach ścieżek (50 odwiedzających, 5 powtórzeń).
- E2: izowisty co 2 m wzdłuż ścieżek vs stres (warianty E1 przy 20 i 80 odwiedzających).
- E3: OAT ±20% (próg adrenaliny, wygaszanie adrenaliny i kortyzolu, wzmocnienie kortyzolu 0,2, skala stref)
  przy 20 i 80 odwiedzających; czy ranking „krzewy 20 m od skrzyżowań < krzewy przy skrzyżowaniach” się utrzymuje.

W przeglądarce: zakładka „Eksperymenty” (nasadzenia, przegląd parametrów, OAT, LHS) oraz warstwy mapy
„średnia adrenalina phantoma” i „pole izowisty”.

Źródła parku: park generowany (losowa siatka alejek z łukami, krzewy w narożnikach skrzyżowań i wzdłuż alejek),
park z OpenStreetMap pobierany przez przeglądarkę (Park Staszica, Szczytnicki, Południowy, Grabiszyński, Zachodni
albo dowolna nazwa we Wrocławiu) albo własne pliki `.shp`/`.geojson`.

Wyniki zgadzają się z GAMA statystycznie, nie liczba w liczbę (inny generator liczb losowych).
Pozostałe różnice (linia widoczności zamiast `masked_by`, osadzanie agentów na największej składowej sieci)
są opisane na początku `psm.py`.

## Dane wejściowe

Model wczytuje dwa shapefile, podane ścieżką względną do pliku `.gaml`, więc muszą leżeć w `models/` obok modelu:

- `Staszica_SHP_sciezki_01.shp` (sieć ścieżek)
- `Staszica_SHP_krzaki_09.shp` (przeszkody / krzaki)

Każdy shapefile to komplet plików (`.shp`, `.shx`, `.dbf`, `.prj`, ...). **Nie są jeszcze w repozytorium.**
