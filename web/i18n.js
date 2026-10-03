// Przełącznik języka PL/EN.
// Teksty statyczne strony są po polsku w index.html; słownik I18N_EN (niżej) podaje ich angielskie odpowiedniki.
// Kluczem jest tekst (albo HTML elementu z mieszaną treścią) po zwinięciu białych znaków.
// Teksty ustawiane z JavaScriptu wybiera L(pl, en); po zmianie języka wołane są funkcje z I18N.onChange.
// Elementy z atrybutem data-noi18n są pomijane (ich treść ustawia kod).
"use strict";
const I18N = (() => {
  const INLINE = new Set(["CODE", "B", "I", "EM", "STRONG", "BR", "A", "SUB", "SUP", "KBD", "SPAN"]);
  const ATTRS = ["placeholder", "aria-label", "title"];
  const norm = (s) => s.replace(/\s+/g, " ").trim();
  const entries = [];
  const hooks = [];
  let dict = {};
  let titlePl = "";
  let lang = pick();

  function pick() {
    try {
      const q = new URLSearchParams(location.search).get("lang");
      if (q === "pl" || q === "en") return q;
      const s = localStorage.getItem("lang");
      if (s === "pl" || s === "en") return s;
    } catch (e) { /* brak dostępu do localStorage */ }
    return (navigator.language || "").toLowerCase().startsWith("pl") ? "pl" : "en";
  }

  function scan(el) {
    if (el.tagName === "SCRIPT" || el.tagName === "STYLE" || el.hasAttribute("data-noi18n")) return;
    for (const a of ATTRS) {
      const v = el.getAttribute(a);
      if (v && dict[norm(v)] !== undefined) entries.push({ el, attr: a, pl: v, en: dict[norm(v)] });
    }
    const kids = [...el.childNodes];
    const elKids = kids.filter((n) => n.nodeType === 1);
    const hasText = kids.some((n) => n.nodeType === 3 && norm(n.nodeValue));
    if (hasText && elKids.length && elKids.every((n) => INLINE.has(n.tagName))) {
      const k = norm(el.innerHTML);
      if (dict[k] !== undefined) { entries.push({ el, html: true, pl: el.innerHTML, en: dict[k] }); return; }
    }
    for (const n of kids) {
      if (n.nodeType === 3) {
        const k = norm(n.nodeValue);
        if (k && dict[k] !== undefined) entries.push({ node: n, pl: n.nodeValue, en: dict[k] });
      } else if (n.nodeType === 1) scan(n);
    }
  }

  function apply() {
    const en = lang === "en";
    document.documentElement.lang = lang;
    for (const e of entries) {
      const v = en ? e.en : e.pl;
      if (e.attr) e.el.setAttribute(e.attr, v);
      else if (e.html) e.el.innerHTML = v;
      else e.node.nodeValue = v;
    }
    if (dict.__title) document.title = en ? dict.__title : titlePl;
    document.querySelectorAll("[data-lang]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
    for (const f of hooks) f(lang);
  }

  return {
    get lang() { return lang; },
    init(d) {
      dict = d;
      titlePl = document.title;
      scan(document.body);
      document.querySelectorAll("[data-lang]").forEach((b) => b.addEventListener("click", () => I18N.set(b.dataset.lang)));
      apply();
    },
    set(l) {
      if (l === lang) return;
      lang = l;
      try { localStorage.setItem("lang", l); } catch (e) { /* tryb prywatny */ }
      apply();
    },
    onChange(f) { hooks.push(f); },
    // klucze słownika, których nie znaleziono na stronie (do sprawdzania słownika)
    unused() {
      const used = new Set(entries.map((e) => norm(e.pl)));
      return Object.keys(dict).filter((k) => k !== "__title" && !used.has(k));
    },
  };
})();
const L = (pl, en) => (I18N.lang === "en" ? en : pl);

// Rozwijane menu alfabetycznie, wg bieżącego języka. Opcja z pustą wartością („—”) zostaje na górze,
// „inna nazwa…” (wartość __custom) na dole; <select data-nosort> jest pomijany. Wybrana wartość się nie zmienia.
function sortSelects(root = document) {
  const coll = new Intl.Collator(I18N.lang, { numeric: true, sensitivity: "base" });
  root.querySelectorAll("select:not([data-nosort])").forEach((sel) => {
    const v = sel.value;
    const opts = [...sel.options];
    const top = opts.filter((o) => o.value === "");
    const bottom = opts.filter((o) => o.value === "__custom");
    const mid = opts.filter((o) => o.value !== "" && o.value !== "__custom")
      .sort((a, b) => coll.compare(a.text, b.text));
    sel.append(...top, ...mid, ...bottom);
    sel.value = v;
  });
}

// słownik PL → EN dla tekstów statycznych index.html (klucz: tekst po zwinięciu spacji)
const I18N_EN = {
 "Ładowanie Pythona (Pyodide)…": "Loading Python (Pyodide)…",
 "Nie udało się wczytać <code>psm.py</code> (strona otwarta jako plik?). Wskaż ręcznie plik <code>src/psm.py</code> albo uruchom <code>python -m http.server</code> w głównym katalogu repozytorium i otwórz <code>http://localhost:8000/web/</code>.": "Could not load <code>psm.py</code> (opened as a local file?). Pick <code>src/psm.py</code> by hand or run <code>python -m http.server</code> in the repository root and open <code>http://localhost:8000/web/</code>.",
 "PSM – stres proksemiczny i awersja do tras": "PSM – proxemic stress and route aversion",
 "Port modelu <code>Hall_AC_aversion.gaml</code> do Pythona, uruchamiany w przeglądarce. Parametry z oznaczeniem ↻ działają po ponownej inicjalizacji.": "Python port of the <code>Hall_AC_aversion.gaml</code> model, running in the browser. Parameters marked ↻ take effect after re-initialisation.",
 "Symulacja": "Simulation",
 "Eksperyment batch": "Batch experiments",
 "Testy": "Tests",
 "O porcie": "About the port",
 "Inicjalizuj": "Initialise",
 "Krok": "Step",
 "Cykli na klatkę": "Cycles per frame",
 "Seed (puste = losowy)": "Seed (empty = random)",
 "losowy": "random",
 "Źródło ścieżek": "Path source",
 "park generowany": "generated park",
 "własne pliki (.shp / .geojson)": "own files (.shp / .geojson)",
 "inna nazwa…": "other name…",
 "Nazwa w OSM": "Name in OSM",
 "np. Park Tołpy": "e.g. Park Tołpy",
 "Pobierz z OSM": "Fetch from OSM",
 "Zapisz GeoJSON": "Save GeoJSON",
 "Wczytaj gotowy": "Load ready",
 "Ścieżki (np. Staszica_SHP_sciezki_01.shp)": "Paths (e.g. Staszica_SHP_sciezki_01.shp)",
 "Przeszkody (np. Staszica_SHP_krzaki_09.shp)": "Obstacles (e.g. Staszica_SHP_krzaki_09.shp)",
 "Z shapefile wystarczy plik <code>.shp</code>; współrzędne powinny być w metrach (np. EPSG:2180). GeoJSON w stopniach jest rzutowany automatycznie.": "A shapefile needs only the <code>.shp</code> file; coordinates should be in metres (e.g. EPSG:2180). GeoJSON in degrees is projected automatically.",
 "Park – ścieżki, krzewy, agenci": "Park – paths, shrubs, agents",
 "ścieżki: pamięć strachu": "paths: fear memory",
 "ścieżki: średnia adrenalina phantoma": "paths: mean phantom adrenaline",
 "ścieżki: pole izowisty": "paths: isovist area",
 "Warstwa ścieżek": "Path layer",
 "Policz izowisty": "Compute isovists",
 "phantom (strefy publiczna i społeczna)": "phantom (public and social zones)",
 "boty": "bots",
 "przeszkody": "obstacles",
 "znacznik strachu": "fear marker",
 "Phantom 0 – psychofizjologia": "Phantom 0 – psychophysiology",
 "adrenalina": "adrenaline",
 "kortyzol": "cortisol",
 "czujność": "vigilance",
 "Pliki wynikowe": "Output files",
 "<code>summary.csv</code> jak w GAMA (zapis w cyklu <code>end_cycle − 1</code>), szereg czasowy phantoma 0, pamięć strachu na odcinkach oraz mapa stresu i widoczności (<code>edges.csv</code>).": "<code>summary.csv</code> as in GAMA (written at cycle <code>end_cycle − 1</code>), time series of phantom 0, fear memory per path segment, and the stress and visibility map (<code>edges.csv</code>).",
 "edges.csv (stres i izowisty)": "edges.csv (stress and isovists)",
 "Eksperymenty": "Experiments",
 "Liczone na parku i z parametrami z zakładki Symulacja. Warianty dzielą seedy powtórzeń (wspólne liczby losowe). Pełny przebieg GAMA to 10 000 cykli.": "Run on the park and with the parameters from the Simulation tab. Variants share the seeds of their repetitions (common random numbers). A full GAMA run is 10,000 cycles.",
 "Rodzaj": "Type",
 "eksperyment nasadzeń (stała powierzchnia)": "planting experiment (constant area)",
 "przegląd parametrów": "parameter sweep",
 "wrażliwość lokalna (OAT)": "local sensitivity (OAT)",
 "wrażliwość globalna (LHS)": "global sensitivity (LHS)",
 "Odstęp od skrzyżowań (m)": "Setback from junctions (m)",
 "Udział w narożnikach": "Share at junction corners",
 "Parametr 1": "Parameter 1",
 "wartości": "values",
 "Parametr 2": "Parameter 2",
 "Zmiana ±": "Change ±",
 "Każda stała z listy poniżej ±10% (dla wygaszania: szybkość 1 − c), elastyczność = względna zmiana wyniku / względna zmiana parametru.": "Each constant in the list below is changed by ±10% (for decay: the rate 1 − c); elasticity = relative change of the output / relative change of the parameter.",
 "Próbki": "Samples",
 "Hipersześcian łaciński w zakresach stałych; wynik: korelacja rang Spearmana parametr–wynik.": "Latin hypercube over the ranges of the constants; result: Spearman rank correlation between parameter and output.",
 "Powtórzenia": "Repetitions",
 "Cykle": "Cycles",
 "Pierwszy seed": "First seed",
 "Uruchom": "Run",
 "Zatrzymaj": "Stop",
 "Testy modelu": "Model tests",
 "Uruchom testy": "Run tests",
 "Co odwzorowuje ten port": "What this port reproduces",
 "Plik <code>psm.py</code> zawiera model z <code>models/Hall_AC_aversion.gaml</code>: sieć ścieżek jako graf ważony długością × (1 + aversion_strength × fear_memory), boty i phantomy idące najkrótszą ważoną trasą do losowego punktu, strefy Halla (1,8 / 4,8 / 14,4 / 40 m przy mnożniku 4) zasłaniane przez przeszkody, czujność, adrenalinę i kortyzol phantoma, próg lęku 11,5, znaczniki strachu, odkładanie i zanikanie pamięci strachu na odcinkach oraz zapis <code>summary.csv</code>.": "The file <code>psm.py</code> contains the model from <code>models/Hall_AC_aversion.gaml</code>: the path network as a graph weighted by length × (1 + aversion_strength × fear_memory), bots and phantoms walking the shortest weighted route to a random point, Hall zones (1.8 / 4.8 / 14.4 / 40 m at multiplier 4) masked by obstacles, the phantom's vigilance, adrenaline and cortisol, the fear threshold of 11.5, fear markers, deposit and decay of fear memory on path segments, and the <code>summary.csv</code> output.",
 "Różnice względem GAMA": "Differences from GAMA",
 "Inny generator liczb losowych: wyniki zgadzają się statystycznie, nie liczba w liczbę. Ten sam seed daje w tej wersji te same wyniki.": "A different random number generator: results agree statistically, not number for number. The same seed gives the same results in this version.",
 "<code>masked_by</code> jest liczone jako linia widoczności phantom → bot (GAMA buduje wielokąt widoczności z promieni).": "<code>masked_by</code> is computed as a line of sight from phantom to bot (GAMA builds a visibility polygon from rays).",
 "Strach trafia na odcinek, na którym phantom stoi (w GAMA <code>road closest_to self</code>, czyli ten sam odcinek).": "Fear is deposited on the segment the phantom stands on (in GAMA <code>road closest_to self</code>, i.e. the same segment).",
 "Przy niespójnej sieci agenci chodzą tylko po największej składowej (w GAMA agent bez trasy stałby w miejscu).": "On a disconnected network agents walk only on the largest component (in GAMA an agent without a route would stand still).",
 "GeoJSON i OSM w stopniach są rzutowane lokalnie na metry (odwzorowanie równoodległościowe).": "GeoJSON and OSM data in degrees are projected locally to metres (equidistant projection).",
 "Rozszerzenia (domyślnie wyłączone, wyniki jak w GAMA)": "Extensions (off by default, results as in GAMA)",
 "<b>Graf botów</b>: <code>plain</code> domyślnie (boty nie znają strachu phantoma, wybierają trasy po długości) albo <code>weighted</code> jak w GAMA (boty też omijają odcinki, na których phantom się bał).": "<b>Bot graph</b>: <code>plain</code> by default (bots do not know the phantom's fear and choose routes by length) or <code>weighted</code> as in GAMA (bots also avoid segments where the phantom was afraid).",
 "<b>Pamięć strachu</b>: <code>shared</code> jak w GAMA albo <code>individual</code> (każdy phantom wybiera trasę według własnej pamięci; przy jednym phantomie wyniki identyczne).": "<b>Fear memory</b>: <code>shared</code> as in GAMA or <code>individual</code> (each phantom chooses its route by its own memory; with one phantom the results are identical).",
 "<b>Nasadzenia sterowane</b>: krzewy o stałej łącznej powierzchni, część w narożnikach skrzyżowań (odstęp od węzła = zmienna projektowa), reszta wzdłuż ścieżek poza strefą skrzyżowania. Działa na każdej sieci, także OSM i SHP.": "<b>Controlled planting</b>: shrubs of constant total area, part at junction corners (setback from the node = design variable), the rest along paths outside the junction zone. Works on any network, including OSM and SHP.",
 "<b>Mapa stresu</b>: średnia adrenalina, suma czujności i epizody lęku phantoma na każdym odcinku.": "<b>Stress map</b>: mean adrenaline, summed vigilance and fear episodes of the phantom on each segment.",
 "<b>Izowisty</b>: pole widoczności (promień = strefa publiczna) co 5 m wzdłuż ścieżek i korelacja rang ze stresem na odcinkach.": "<b>Isovists</b>: visible area (radius = public zone) every 5 m along paths and its rank correlation with stress per segment.",
 "<b>Wrażliwość</b>: OAT (elastyczności przy ±10%) i LHS (korelacje Spearmana) dla stałych modelu.": "<b>Sensitivity</b>: OAT (elasticities at ±10%) and LHS (Spearman correlations) for the model constants.",
 "Park generowany to siatka alejek z łukami i pętlą obwodową, z krzewami w narożnikach skrzyżowań (ślepe narożniki) i wzdłuż alejek. Park z OpenStreetMap pobiera przeglądarka bezpośrednio z Overpass API. Oryginalne pliki <code>Staszica_SHP_*.shp</code> można wczytać jako własne pliki.": "The generated park is a grid of curved alleys with a perimeter loop, with shrubs at junction corners (blind corners) and along alleys. The browser fetches OpenStreetMap parks directly from the Overpass API. The original <code>Staszica_SHP_*.shp</code> files can be loaded as own files.",
 "Uruchamianie poza przeglądarką": "Running outside the browser",
 "__title": "PSM in the browser",
 "cykl": "cycle",
 "park": "park",
 "Park": "Park"
};

// kategorie i etykiety parametrów z psm.GUI_PARAMETERS (po polsku w psm.py)
const I18N_CAT_EN = {
  "Populacja": "Population", "Strefy Halla": "Hall zones", "Psychofizjologia": "Psychophysiology",
  "Awersja do tras": "Route aversion", "Warianty mechaniki": "Mechanism variants", "Nasadzenia": "Planting",
  "Przebieg": "Run", "Park generowany": "Generated park",
};
const I18N_PARAM_EN = {
  bot_nb: "Number of bots", phantom_nb: "Number of phantoms", phantom_speed_kmh: "Phantom speed (km/h)",
  bot_speed_kmh: "Mean bot speed (km/h)", bot_speed_sd: "SD of bot speed (m/s)",
  hall_multiplier: "Zone multiplier", intimate: "Intimate (m, empty = from multiplier)", personal: "Personal (m)",
  social: "Social (m)", public: "Public (m)",
  adrenaline_threshold: "Fear threshold (adrenaline)", adrenaline_cooldown: "Adrenaline decay",
  cortisol_cooldown: "Cortisol decay", cortisol_gain: "Cortisol gain", initial_level: "Initial level",
  fear_spacing: "Min. spacing of fear markers (m)",
  aversion_strength: "Aversion strength (0 = baseline)", fear_deposit: "Fear deposit", fear_decay: "Fear decay",
  reweight_every: "Re-weight graph every (cycles)",
  bot_graph: "Bot graph (plain = bots do not know the phantom's fear; weighted = as in GAMA)",
  fear_scope: "Fear memory (shared = as in GAMA)",
  planting: "Planting", planting_seed: "Planting seed", bush_area_total: "Total shrub area (m²)",
  bush_form: "Form (clumps / band)", bush_radius: "Clump radius (m)", bush_band_width: "Band width (m)",
  bush_band_length: "Band segment length (m)", bush_junction_share: "Share at junction corners",
  bush_junction_distance: "Setback from junction node (m)", bush_path_offset: "Offset from path axis (m)",
  bush_setback_scope: "Setback from (own = its junction / all = every junction)",
  junction_zone: "Junction zone (m)",
  end_cycle: "End (cycle)", step_min: "Step (min)",
  park_seed: "Park seed", park_width: "Width (m)", park_height: "Height (m)", park_bushes: "Number of shrubs",
};
