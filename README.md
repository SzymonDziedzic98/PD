# PD
Proxemics Stress

[English description: README.en.md](README.en.md)

Model agentowy w GAMA (Proxemic Stress Model) z modyfikacją: sprzężenie zwrotne między stresem a wyborem trasy.

## Model

`models/Hall_AC_aversion.gaml` (autorzy: Mikołaj Szurlej, Maciej Kamiński)

- **Strefy proksemiczne Halla** (intymna, osobista, społeczna, publiczna), skalowane parametrem `hall_multiplier`.
- **Adrenalina i kortyzol**: fantom (agent badany) reaguje na obecność botów w swoich strefach; model śledzi też czujność (vigilance).
- **Awersja do tras**: na odcinkach, na których fantom odczuł strach, odkłada się „pamięć strachu”, która zwiększa wagę krawędzi w grafie. Awersja jest miękka i probabilistyczna, nie blokuje ścieżek.
  - `aversion_strength = 0.0` odtwarza model bazowy.
  - `fear_deposit`, `fear_decay`, `reweight_every` sterują odkładaniem, zanikaniem i przeliczaniem wag.

Symulacja zatrzymuje się po 10 000 cyklach; w cyklu 9999 wyniki są dopisywane do `results/summary.csv`.

## Wersja w Pythonie (`src/`) i w przeglądarce (`web/`)

- `src/psm.py` – port `models/Hall_AC_aversion.gaml` do czystego Pythona (tylko biblioteka standardowa):
  model, przegląd `aversion_strength` (batch), testy, czytnik `.shp`/GeoJSON i import parku z OpenStreetMap.
  - `python src/psm.py --test`
  - `python src/psm.py --run --roads Staszica_SHP_sciezki_01.shp --obstacles Staszica_SHP_krzaki_09.shp`
  - `python src/psm.py --batch --aversion 0,2.5,5,10 --repeat 5 --cycles 10000 --csv batch_results.csv`
  - `python src/psm.py --fetch-osm "Park Staszica" --out park_staszica.geojson` (Overpass API, wymaga internetu).
    Przeszkody z OSM: zarośla, zadrzewienia i lasy (także relacje multipolygon), żywopłoty, mury, szpalery drzew, budynki.
    Rozłączne kawałki ścieżek z OSM są łączone odcinkami do 50 m (`OSM_BRIDGE_GAP`), także we wczytanych plikach GeoJSON; pliki SHP zostają bez zmian.
    Sieć z OSM/GeoJSON jest też upraszczana (`simplify_roads`, `OSM_SIMPLIFY`): ścieżki równoległe bliżej niż 3 m łączą się w jedną,
    a skupiska skrzyżowań bliżej niż 6 m w jedno skrzyżowanie. Ślepe końce do 25 m od siebie wewnątrz parku (place, polany
    nieoznaczone w OSM) łączy `link_dead_ends`. `bush_setback_scope = all` liczy odsunięcie krzewów od każdego skrzyżowania.
    `--fetch-osm` i przycisk „Zapisz GeoJSON” zapisują sieć już po tych poprawkach (WGS84, warstwy `roads`/`obstacles`/`boundary`,
    znacznik `psm_processed` z punktem rzutu); taki plik wczytuje się bez drugiej obróbki. `--process PLIK --out WYNIK` poprawia
    wcześniej zapisany surowy plik.
  - `web/parki/` – gotowe parki Wrocławia po poprawkach (Staszica, Szczytnicki, Południowy, Grabiszyński, Zachodni; OSM, ODbL,
    pobrane 2026-09-28). W aplikacji: „Wczytaj gotowy”, bez pobierania z Overpass. Te same pliki są w repozytorium SIPD.
- `web/index.html` – uruchamia `psm.py` w przeglądarce (Pyodide): mapa parku z pamięcią strachu na ścieżkach,
  strefy Halla phantoma, wykres adrenaliny, kortyzolu i czujności, batch, testy i pobieranie CSV.
  Otwórz przez serwer HTTP uruchomiony w głównym katalogu repozytorium: `python -m http.server`, potem `http://localhost:8000/web/` (strona wczytuje `../src/psm.py`).
  Interfejs jest po polsku i po angielsku: przełącznik PL/EN w nagłówku, wybór zapamiętuje przeglądarka;
  `?lang=en` albo `?lang=pl` w adresie wymusza język. Teksty angielskie są w `web/i18n.js`.
  Workflow `.github/workflows/pages.yml` publikuje `web/` razem z `src/psm.py` na GitHub Pages
  (jednorazowo: Settings → Pages → Source: „GitHub Actions”).

### Rozszerzenia (pod artykuł do URBAN DESIGN International)

Domyślne wartości nowych parametrów dają wyniki identyczne jak w GAMA. `bot_graph` domyślnie wynosi `plain`, bo boty
nie powinny znać uczuć phantoma (decyzja autora, 28.09.2026); od 30.09.2026 GAML ma to samo ustawienie
(`bots_plain_graph = true`) i przełącznik `individual_fear` odpowiadający `fear_scope = individual`.
Dawne zachowanie GAML: `bot_graph = weighted` i `bots_plain_graph = false`.

- `bot_graph`: `plain` (domyślnie: boty wybierają trasy tylko po długości) albo `weighted` (w GAMA `bots_plain_graph = false`: boty chodzą po tym samym ważonym grafie, więc też omijają odcinki,
  na których phantom się bał).
- Sieci z OSM/GeoJSON: po połączeniu kawałków, uproszczeniu i połączeniu ślepych końców przy placach odcinane są ślepe
  odnogi dłuższe niż 15 m (`prune_dead_ends`, stała `OSM_PRUNE_DEAD_END`; 0 wyłącza). Odnoga to łańcuch od ślepego końca do
  pierwszego skrzyżowania; powtarzane do skutku, więc znikają też całe ślepe drzewka. Końce do 8 m od obrysu parku to
  wyjścia: ich odnoga zostaje, a dłuższa niż 15 m jest przycinana od strony wyjścia do 15 m (decyzja autora, 30.09.2026).
- `fear_scope`: `shared` (domyślnie, w GAMA `individual_fear = false`) albo `individual` (każdy phantom ma własną pamięć
  strachu; w GAMA `individual_fear = true`).
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
python src/psm.py --planting-experiment --distances 1,4,8,12 --shares 0,0.5,1 --repeat 10 --planting-seeds 5 \
    --cycles 10000 --csv nasadzenia.csv --summary nasadzenia_srednie.csv
python src/psm.py --planting-experiment --roads Staszica_SHP_sciezki_01.shp        # to samo na ścieżkach parku Staszica
python src/psm.py --sensitivity oat --repeat 10 --cycles 10000 --summary oat.csv
python src/psm.py --sensitivity lhs --samples 100 --cycles 10000 --summary lhs.csv
python src/psm.py --run --isovist --edges edges.csv --set planting=controlled
python src/psm.py --batch --sweep bot_graph=weighted,plain --sweep aversion_strength=0,5 --repeat 10
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

## Licencja i cytowanie

Kod jest udostępniony na licencji MIT (`LICENSE.txt`). Dane do cytowania są w `CITATION.cff`
(GitHub pokazuje je jako „Cite this repository”).
