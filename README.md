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

## Dane wejściowe

Model wczytuje dwa shapefile, podane ścieżką względną do pliku `.gaml`, więc muszą leżeć w `models/` obok modelu:

- `Staszica_SHP_sciezki_01.shp` (sieć ścieżek)
- `Staszica_SHP_krzaki_09.shp` (przeszkody / krzaki)

Każdy shapefile to komplet plików (`.shp`, `.shx`, `.dbf`, `.prj`, ...). **Nie są jeszcze w repozytorium.**
