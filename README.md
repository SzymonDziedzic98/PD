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
