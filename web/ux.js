// Wspólne drobiazgi interfejsu (ten sam plik w psm-web i SIPD, web/ux.js):
// przyciski wyboru pliku w języku strony, podpowiedzi na wyszarzonych przyciskach, napisy w pustych panelach, opisy parametrów,
// zrozumiały komunikat, gdy Pyodide się nie wczyta, zapamiętywanie ustawień i link z ustawieniami, parametry podstawowe
// i zaawansowane, suwaki, porównanie dwóch przebiegów, skróty klawiszowe, karty „Co wypróbować”, wersja modelu i config.json.
// Wymaga i18n.js (L, I18N). Nie dotyka modelu: czyta i ustawia tylko pola formularza.
"use strict";
const UX = (() => {
  const style = document.createElement("style");
  style.textContent = `
.file-pick { display: flex; align-items: center; gap: 8px; min-width: 0; }
.file-pick .btn { padding: 3px 10px; font-size: 12.5px; flex: none; }
.file-pick .file-name { font-size: 12px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.file-pick .file-name.chosen { color: var(--ink); font-family: var(--font-mono); }
.empty-host { position: relative; }
.empty-note {
  position: absolute; inset: 0; display: grid; place-items: center; padding: 16px; text-align: center;
  color: var(--muted); font-size: 13px; pointer-events: none;
}
.load-error { display: grid; gap: 8px; }
.label-help { display: flex; align-items: center; gap: 5px; min-width: 0; }
.label-help label[title] { cursor: help; }
.help-btn {
  flex: none; width: 16px; height: 16px; padding: 0; border-radius: 50%; border: 1px solid var(--line);
  background: transparent; color: var(--muted); font: 600 10px/1 var(--font-body); cursor: pointer;
}
.help-btn[aria-expanded="true"] { background: var(--ink); color: var(--ground); border-color: var(--ink); }
.param-help { grid-column: 1 / -1; margin: -2px 0 4px; }
.load-error .btn { justify-self: start; }
.btn.small { padding: 3px 10px; font-size: 12.5px; }
.cat.basic > summary { color: var(--ink); }
.adv-toggle { justify-self: start; }
.field .slider { grid-column: 1 / -1; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 6px; align-items: center;
  font: 11px var(--font-mono); color: var(--muted); margin: -2px 0 2px; }
.field .slider input[type="range"] { width: 100%; margin: 0; accent-color: var(--park); }
.try-list { display: grid; gap: 10px; }
.try-card { border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; display: grid; gap: 6px; background: var(--ground); }
.try-card h3 { text-transform: none; letter-spacing: 0; font-size: 14px; color: var(--ink); }
.try-card p { margin: 0; }
.try-card .lead { font-weight: 600; }
.try-banner { border: 1px solid var(--focus); border-radius: 8px; padding: 8px 12px; background: var(--panel); display: grid; gap: 4px; }
.try-banner p { margin: 0; }
.try-banner .controls { margin-top: 2px; }
.cmp-table td, .cmp-table th { white-space: normal; }
.cite { font-family: var(--font-mono); font-size: 12px; background: var(--ground); border: 1px solid var(--line); border-radius: 6px;
  padding: 8px 10px; white-space: pre-wrap; overflow-wrap: anywhere; margin: 0; }
kbd { font-family: var(--font-mono); font-size: 11.5px; border: 1px solid var(--line); border-bottom-width: 2px; border-radius: 4px; padding: 0 4px; background: var(--panel); }
.load-error .detail { font-family: var(--font-mono); font-size: 11.5px; color: var(--muted); overflow-wrap: anywhere; }
`;
  document.head.append(style);
  const relabels = [];
  I18N.onChange(() => relabels.forEach((f) => f()));

  // ---------- A: wybór pliku ----------
  // Natywne „Choose File / No file chosen” mówi językiem przeglądarki; zamiast niego przycisk i nazwa pliku w języku strony.
  function fileInputs(root = document) {
    root.querySelectorAll('input[type="file"]:not([data-ux])').forEach((inp) => {
      inp.dataset.ux = "1";
      const wrap = document.createElement("span"); wrap.className = "file-pick";
      const btn = document.createElement("button"); btn.type = "button"; btn.className = "btn";
      const name = document.createElement("span"); name.className = "file-name";
      inp.before(wrap);
      wrap.append(btn, name, inp);
      inp.hidden = true;
      btn.addEventListener("click", () => inp.click());
      const lab = inp.id && document.querySelector(`label[for="${inp.id}"]`);
      if (lab) { btn.setAttribute("aria-describedby", inp.id + "_name"); name.id = inp.id + "_name"; }
      const render = () => {
        const f = inp.files && inp.files[0];
        btn.textContent = L("Wybierz plik…", "Choose file…");
        if (lab) btn.setAttribute("aria-label", lab.textContent + ": " + btn.textContent);
        name.textContent = f ? f.name : L("nie wybrano pliku", "no file chosen");
        name.classList.toggle("chosen", !!f);
        name.title = f ? f.name : "";
      };
      inp.addEventListener("change", render);
      relabels.push(render);
      render();
    });
  }

  // ---------- B: podpowiedzi na wyszarzonych przyciskach ----------
  // Wyszarzony przycisk dostaje title z powodem; po odblokowaniu title znika.
  const hints = [];
  const obs = new MutationObserver((recs) => recs.forEach((r) => hints.filter((h) => h.el === r.target).forEach(upd)));
  function upd(h) {
    const t = L(h.pl, h.en);
    if (h.el.disabled) { h.el.title = t; h.shown = t; }
    else if (h.shown && h.el.title === h.shown) { h.el.removeAttribute("title"); h.shown = ""; }
  }
  function disabledHint(els, pl, en) {
    for (const x of [].concat(els)) {
      const el = typeof x === "string" ? document.getElementById(x) : x;
      if (!el) continue;
      const h = { el, pl, en, shown: "" };
      hints.push(h);
      obs.observe(el, { attributes: true, attributeFilter: ["disabled"] });
      upd(h);
    }
  }
  relabels.push(() => hints.forEach((h) => { if (h.el.disabled) upd(h); }));

  // ---------- C: napisy w pustych panelach ----------
  const empties = [];
  function emptyNote(el, pl, en) {
    if (!el) return;
    let host = el;
    if (el.tagName === "CANVAS") {
      host = document.createElement("div"); host.className = "empty-host";
      el.before(host); host.append(el);
    } else host.classList.add("empty-host");
    const n = document.createElement("div"); n.className = "empty-note";
    host.append(n);
    const e = { n, pl, en };
    empties.push(e);
    n.textContent = L(pl, en);
  }
  relabels.push(() => empties.forEach((e) => { e.n.textContent = L(e.pl, e.en); }));
  function ready(on = true) { empties.forEach((e) => { e.n.hidden = on; }); }

  // ---------- opisy parametrów ----------
  // Etykieta dostaje title (najechanie), a obok przycisk „?”, który rozwija opis pod polem (dotyk, czytniki ekranu).
  // Etykieta trafia do <span class="label-help">, więc strona może dalej zmieniać jej textContent.
  const helps = [];
  function renderHelp(h) {
    const t = h.getText();
    h.lab.title = t; h.btn.title = t; h.p.textContent = t;
    h.btn.setAttribute("aria-label", L("Opis: ", "Description: ") + h.lab.textContent);
  }
  function paramHelp(lab, getText) {
    const wrap = document.createElement("span"); wrap.className = "label-help";
    lab.before(wrap); wrap.append(lab);
    const btn = document.createElement("button"); btn.type = "button"; btn.className = "help-btn"; btn.textContent = "?";
    btn.setAttribute("aria-expanded", "false");
    wrap.append(btn);
    const p = document.createElement("p"); p.className = "hint param-help"; p.hidden = true;
    p.id = (lab.htmlFor || "f" + helps.length) + "_help";
    btn.setAttribute("aria-controls", p.id);
    wrap.parentElement.append(p);
    btn.addEventListener("click", () => { p.hidden = !p.hidden; btn.setAttribute("aria-expanded", String(!p.hidden)); });
    const h = { lab, btn, p, getText };
    helps.push(h);
    renderHelp(h);
  }
  relabels.push(() => helps.forEach(renderHelp));
  // wartość do opisu: liczby z przecinkiem po polsku, puste i logiczne słownie
  function fmtValue(v) {
    if (v === null || v === undefined || v === "") return L("puste", "empty");
    if (typeof v === "boolean") return v ? L("włączone", "on") : L("wyłączone", "off");
    if (Array.isArray(v)) return v.join(", ");
    if (typeof v === "number" && I18N.lang === "pl") return String(v).replace(".", ",");
    return String(v);
  }

  // ---------- D: Pyodide się nie wczytał ----------
  function loadFailed(err) {
    const h = document.querySelector("#loading h2");
    if (h) h.textContent = L("Nie udało się wczytać Pythona", "Could not load Python");
    const bar = document.getElementById("loadBar");
    if (bar) bar.hidden = true;
    const box = document.getElementById("loadMsg");
    const wrap = document.createElement("div"); wrap.className = "load-error";
    const p = document.createElement("p"); p.className = "hint";
    p.textContent = L(
      "Nie udało się pobrać Pythona dla przeglądarki (Pyodide z cdn.jsdelivr.net). Sprawdź połączenie z internetem. " +
      "Sieć uczelniana lub firmowa albo rozszerzenie blokujące reklamy może blokować ten adres; spróbuj wtedy w innej sieci lub przeglądarce.",
      "Could not download Python for the browser (Pyodide from cdn.jsdelivr.net). Check your internet connection. " +
      "A university or company network, or an ad-blocking extension, may block this address; then try another network or browser.");
    const again = document.createElement("button"); again.type = "button"; again.className = "btn primary";
    again.textContent = L("Spróbuj ponownie", "Try again");
    again.addEventListener("click", () => location.reload());
    const d = document.createElement("p"); d.className = "detail";
    d.textContent = L("Szczegóły: ", "Details: ") + ((err && err.message) || err);
    wrap.append(p, again, d);
    box.replaceChildren(wrap);
    box.removeAttribute("class");
  }

  // ---------- F: zapamiętywanie ustawień i link ----------
  // Pola #paramForm [data-key] i podane id. Zapisywane są tylko zmiany względem stanu startowego strony.
  // Kolejność: link (?s=…) > ostatnie ustawienia z tej przeglądarki > stan startowy. linkOnly: pola tylko w linku (np. seed).
  function settings(storeKey, ids, linkOnly = []) {
    // pola ze ścieżką do pliku (np. rest_zone_file) wskazują pliki z bieżącej sesji, więc ich nie zapamiętuję
    const els = () => [...document.querySelectorAll("#paramForm [data-key]"), ...ids.map((id) => document.getElementById(id)).filter(Boolean)]
      .filter((el) => !/_file$/.test(el.dataset.key || ""));
    const keyOf = (el) => el.dataset.key || "#" + el.id;
    const get = (el) => (el.type === "checkbox" ? el.checked : el.value);
    const set = (el, v) => { if (el.type === "checkbox") el.checked = !!v; else el.value = v; };
    const base = new Map(els().map((el) => [keyOf(el), get(el)]));
    const diff = (withLinkOnly) => {
      const o = {};
      els().forEach((el) => {
        const k = keyOf(el), v = get(el);
        if (!withLinkOnly && linkOnly.includes(k)) return;
        if (v !== base.get(k)) o[k] = v;
      });
      return o;
    };
    const apply = (o) => { els().forEach((el) => { const k = keyOf(el); if (Object.prototype.hasOwnProperty.call(o, k)) set(el, o[k]); }); };
    const enc = (o) => btoa(unescape(encodeURIComponent(JSON.stringify(o)))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    const dec = (s) => JSON.parse(decodeURIComponent(escape(atob(s.replace(/-/g, "+").replace(/_/g, "/")))));
    function save() {
      try {
        const o = diff(false);
        if (Object.keys(o).length) localStorage.setItem(storeKey, JSON.stringify(o));
        else localStorage.removeItem(storeKey);
      } catch (e) { /* tryb prywatny – bez zapamiętywania */ }
    }
    let restored = null, count = 0;
    try {
      const s = new URLSearchParams(location.search).get("s");
      if (s) {
        const o = dec(s);
        if (o && typeof o === "object") { apply(o); restored = "link"; count = Object.keys(o).length; }
        // bez ?s= w pasku adresu, żeby odświeżenie nie cofało późniejszych zmian
        const u = new URL(location.href); u.searchParams.delete("s"); history.replaceState(null, "", u);
      }
    } catch (e) { restored = "badlink"; }
    if (!restored || restored === "badlink") {
      try {
        const o = JSON.parse(localStorage.getItem(storeKey) || "null");
        if (o && typeof o === "object" && Object.keys(o).length) { apply(o); restored = restored || "local"; count = Object.keys(o).length; }
      } catch (e) { /* uszkodzony zapis – pomijam */ }
    }
    document.addEventListener("change", (ev) => { if (els().includes(ev.target)) save(); });
    return {
      restored, count, save,
      reset() { apply(Object.fromEntries(base)); save(); },
      link() {
        const u = new URL(location.href);
        u.searchParams.delete("s"); u.searchParams.delete("lang");
        const o = diff(true);
        if (Object.keys(o).length) u.searchParams.set("s", enc(o));
        return u.toString();
      },
    };
  }

  async function copy(text) {
    try { await navigator.clipboard.writeText(text); return true; }
    catch (e) { window.prompt(L("Skopiuj link:", "Copy the link:"), text); return false; }
  }


  // ---------- parametry podstawowe i zaawansowane ----------
  // Najważniejsze parametry trafiają do pierwszej, otwartej kategorii; reszta jest zwinięta pod przyciskiem.
  // Przycisk podaje, ile ukrytych parametrów różni się od stanu startowego (np. po linku albo gotowym scenariuszu).
  let adv = null;
  function basicAdvanced(form, keys) {
    const rowOf = (k) => { const el = document.getElementById("p_" + k); return el && el.closest(".field"); };
    const det = document.createElement("details"); det.className = "cat basic"; det.open = true;
    const sum = document.createElement("summary"); sum.dataset.pl = "Najważniejsze parametry";
    const fields = document.createElement("div"); fields.className = "fields";
    det.append(sum, fields);
    keys.forEach((k) => { const r = rowOf(k); if (r) fields.append(r); });
    const rest = [...form.children];
    rest.forEach((d) => { if (d.matches("details") && !d.querySelector(".field")) d.hidden = true; });
    const box = document.createElement("div"); box.className = "adv"; box.style.display = "grid"; box.style.gap = "8px";
    box.append(...rest);
    const btn = document.createElement("button"); btn.type = "button"; btn.className = "btn small adv-toggle";
    form.append(det, btn, box);
    const val = (el) => (el.type === "checkbox" ? el.checked : el.value);
    const hidden = () => [...box.querySelectorAll("[data-key]")].filter((el) => el.matches("input, select"));
    const base = new Map(hidden().map((el) => [el, val(el)]));
    let open = false;
    try { open = localStorage.getItem("ux:advanced") === "1"; } catch (e) { /* bez zapamiętywania */ }
    const render = () => {
      box.hidden = !open;
      const n = hidden().filter((el) => val(el) !== base.get(el)).length;
      btn.textContent = open ? L("Ukryj pozostałe parametry", "Hide the other parameters")
        : L("Pokaż wszystkie parametry", "Show all parameters") + (n ? L(` (zmienione: ${n})`, ` (changed: ${n})`) : "");
      btn.setAttribute("aria-expanded", String(open));
      sum.textContent = L("Najważniejsze parametry", "Key parameters");
    };
    btn.addEventListener("click", () => {
      open = !open;
      try { localStorage.setItem("ux:advanced", open ? "1" : "0"); } catch (e) { /* bez zapamiętywania */ }
      render();
    });
    form.addEventListener("change", render);
    relabels.push(render);
    adv = { render, show() { open = true; render(); } };
    render();
    return adv;
  }

  // ---------- suwaki ----------
  // Suwak pod polem liczbowym; pole zostaje i pokazuje dokładną wartość. Zmiana suwaka wysyła „change” z pola,
  // więc strona reaguje tak samo jak na wpisanie liczby.
  const sliders = [];
  function slidersFor(specs) {
    for (const [key, [min, max, step]] of Object.entries(specs)) {
      const num = document.getElementById("p_" + key);
      if (!num) continue;
      const wrap = document.createElement("div"); wrap.className = "slider";
      const lo = document.createElement("span"); lo.textContent = min;
      const hi = document.createElement("span"); hi.textContent = max;
      const r = document.createElement("input"); r.type = "range"; r.min = min; r.max = max; r.step = step;
      wrap.append(lo, r, hi);
      num.closest(".field").append(wrap);
      const s = { num, r, key };
      r.addEventListener("input", () => { num.value = r.value; });
      r.addEventListener("change", () => { num.value = r.value; num.dispatchEvent(new Event("change", { bubbles: true })); });
      num.addEventListener("input", () => syncSlider(s));
      num.addEventListener("change", () => syncSlider(s));
      sliders.push(s);
      syncSlider(s);
    }
    relabels.push(() => sliders.forEach((s) => {
      const lab = document.querySelector(`label[for="${s.num.id}"]`);
      s.r.setAttribute("aria-label", (lab ? lab.textContent : s.key) + L(" (suwak)", " (slider)"));
    }));
    relabels[relabels.length - 1]();
  }
  function syncSlider(s) { if (s.num.value !== "") s.r.value = s.num.value; }
  // po zmianie pól z kodu (link, reset, scenariusz): suwaki i licznik ukrytych zmian
  function refresh() { sliders.forEach(syncSlider); if (adv) adv.render(); }

  // ---------- porównanie dwóch przebiegów ----------
  // Bieżący przebieg i zapamiętany (np. wariant bazowy) na jednym wykresie, wybrana miara, tabela końcowych wartości
  // i różnice ustawień. Strona woła start() po inicjalizacji i record() przy odświeżaniu.
  function compare(host, metrics) {
    host.innerHTML = "";
    const h = document.createElement("h2");
    const hint = document.createElement("p"); hint.className = "hint";
    const ctr = document.createElement("div"); ctr.className = "controls";
    const sel = document.createElement("select"); sel.dataset.nosort = "";
    const keep = document.createElement("button"); keep.type = "button"; keep.className = "btn";
    const clear = document.createElement("button"); clear.type = "button"; clear.className = "btn";
    ctr.append(sel, keep, clear);
    const boxc = document.createElement("div"); boxc.className = "chart-box";
    const cv = document.createElement("canvas"); boxc.append(cv);
    const diff = document.createElement("p"); diff.className = "hint";
    const tw = document.createElement("div"); tw.className = "table-wrap";
    host.append(h, hint, ctr, boxc, diff, tw);
    let cur = null, base = null, chart = null, pending = false;
    const metric = () => metrics.find((m) => m.key === sel.value) || metrics[0];
    const fmt = (v) => (v === undefined || v === null ? "–" : typeof v === "number" ? (Number.isInteger(v) ? String(v) : v.toFixed(2)) : String(v));
    function labels() {
      h.textContent = L("Porównanie dwóch przebiegów", "Compare two runs");
      hint.textContent = L("Zapamiętaj przebieg (np. wariant bazowy), zmień ustawienia, kliknij Inicjalizuj i uruchom. Zapamiętany przebieg jest linią przerywaną.",
        "Keep a run (e.g. the baseline), change the settings, click Initialise and run. The kept run is the dashed line.");
      keep.textContent = L("Zapamiętaj ten przebieg", "Keep this run");
      clear.textContent = L("Wyczyść", "Clear");
      sel.setAttribute("aria-label", L("Miara na wykresie", "Measure on the chart"));
      const v = sel.value;
      sel.replaceChildren(...metrics.map((m) => new Option(L(m.pl, m.en), m.key)));
      sel.value = v || metrics[0].key;
      keep.disabled = !(cur && cur.pts.length);
      clear.disabled = !base;
      draw(); table();
    }
    function draw() {
      if (typeof Chart === "undefined") return;
      const cs = getComputedStyle(document.documentElement);
      const c = (n) => cs.getPropertyValue(n).trim();
      const k = metric().key;
      const ds = [];
      if (base) ds.push({ label: base.label, data: base.pts.map((p) => ({ x: p.x, y: p.v[k] })), borderColor: c("--accent"), borderDash: [6, 4] });
      if (cur) ds.push({ label: cur.label, data: cur.pts.map((p) => ({ x: p.x, y: p.v[k] })), borderColor: c("--focus") });
      if (!chart) {
        chart = new Chart(cv, { type: "line", data: { datasets: ds }, options: {
          animation: false, maintainAspectRatio: false, parsing: false, normalized: true,
          plugins: { legend: { labels: { color: c("--muted"), boxWidth: 18, font: { size: 11 } } } },
          scales: { x: { type: "linear", ticks: { color: c("--muted") }, grid: { color: c("--line") }, title: { display: true, color: c("--muted") } },
                    y: { ticks: { color: c("--muted") }, grid: { color: c("--line") }, title: { display: true, color: c("--muted") } } },
          elements: { point: { radius: 0 }, line: { borderWidth: 1.6 } } } });
      } else chart.data.datasets = ds;
      chart.options.scales.x.title.text = L("cykl", "cycle");
      chart.options.scales.y.title.text = L(metric().pl, metric().en);
      chart.update("none");
    }
    function table() {
      const last = (r) => (r && r.pts.length ? r.pts[r.pts.length - 1] : null);
      const lb = last(base), lc = last(cur);
      const t = document.createElement("table"); t.className = "cmp-table";
      const head = [L("miara", "measure"), base ? base.label : L("zapamiętany", "kept"), cur ? cur.label : L("bieżący", "current")];
      t.innerHTML = "<tr>" + head.map((x, i) => `<th${i ? ' class="num"' : ""}></th>`).join("") + "</tr>";
      [...t.rows[0].cells].forEach((c, i) => { c.textContent = head[i]; });
      metrics.forEach((m) => {
        const tr = t.insertRow();
        [L(m.pl, m.en), lb ? fmt(lb.v[m.key]) : "–", lc ? fmt(lc.v[m.key]) : "–"].forEach((v, i) => {
          const td = tr.insertCell(); td.textContent = v; if (i) td.className = "num mono";
        });
      });
      const cyc = [L("cykl", "cycle"), lb ? lb.x : "–", lc ? lc.x : "–"];
      const tr = t.insertRow(); cyc.forEach((v, i) => { const td = tr.insertCell(); td.textContent = v; if (i) td.className = "num mono"; });
      tw.replaceChildren(t);
      if (base && cur) {
        const keys = [...new Set([...Object.keys(base.params), ...Object.keys(cur.params)])];
        const d = keys.filter((k) => JSON.stringify(base.params[k]) !== JSON.stringify(cur.params[k]))
          .map((k) => `${k}: ${fmtValue(base.params[k])} → ${fmtValue(cur.params[k])}`);
        diff.textContent = d.length ? L("Różnice ustawień: ", "Differences in settings: ") + d.join("; ") + "."
          : L("Ustawienia obu przebiegów są takie same (różnić się może tylko seed).", "Both runs have the same settings (only the seed may differ).");
      } else diff.textContent = "";
    }
    sel.addEventListener("change", draw);
    keep.addEventListener("click", () => api.keep());
    clear.addEventListener("click", () => { base = null; labels(); });
    relabels.push(labels);
    const api = {
      // label: [pl, en] albo tekst; params: ustawienia przebiegu (do listy różnic)
      start(label, params) { cur = { label: typeof label === "string" ? label : L(label[0], label[1]), params: params || {}, pts: [] }; labels(); },
      record(x, values) {
        if (!cur) return;
        const p = cur.pts;
        if (p.length && p[p.length - 1].x === x) p[p.length - 1].v = values; else p.push({ x, v: values });
        keep.disabled = false;
        if (!pending) { pending = true; setTimeout(() => { pending = false; draw(); table(); }, 300); }
      },
      keep() { if (cur && cur.pts.length) { base = { ...cur, label: cur.label + L(" (zapamiętany)", " (kept)") }; labels(); } },
      clear() { base = null; labels(); },
      get hasBase() { return !!base; },
      redraw() { if (chart) { chart.destroy(); chart = null; } draw(); },
    };
    labels();
    return api;
  }

  // ---------- skróty klawiszowe ----------
  // Spacja i → działają, gdy fokus nie stoi w polu formularza ani na przycisku (tam spacja ma swoje znaczenie).
  function shortcuts(map, active) {
    document.addEventListener("keydown", (ev) => {
      if (ev.ctrlKey || ev.metaKey || ev.altKey || ev.defaultPrevented) return;
      const t = ev.target;
      if (t && (t.isContentEditable || /^(INPUT|SELECT|TEXTAREA|BUTTON|SUMMARY|A)$/.test(t.tagName))) return;
      const f = map[ev.key === " " ? "Space" : ev.key];
      if (!f || (active && !active())) return;
      ev.preventDefault();
      f();
    });
  }

  // ---------- „Co wypróbować” ----------
  // Karty z eksperymentami: co sprawdzić, na co patrzeć, czego się spodziewać; przyciski wariantów uruchamia strona.
  function tryCards(host, items, run) {
    const render = () => {
      host.replaceChildren(...items.map((it) => {
        const c = document.createElement("article"); c.className = "try-card";
        const h = document.createElement("h3"); h.textContent = L(it.title[0], it.title[1]);
        const p1 = document.createElement("p"); p1.textContent = L(it.what[0], it.what[1]);
        const p2 = document.createElement("p"); p2.className = "hint"; p2.textContent = L("Na co patrzeć: ", "What to watch: ") + L(it.look[0], it.look[1]);
        const p3 = document.createElement("p"); p3.className = "hint"; p3.textContent = L("Czego się spodziewać: ", "What to expect: ") + L(it.expect[0], it.expect[1]);
        const ctr = document.createElement("div"); ctr.className = "controls";
        it.variants.forEach((v, i) => {
          const b = document.createElement("button"); b.type = "button"; b.className = "btn" + (i ? "" : " primary");
          b.textContent = (it.variants.length > 1 ? `${i + 1}. ` : "") + L(v.label[0], v.label[1]);
          b.addEventListener("click", () => run(it, i));
          ctr.append(b);
        });
        c.append(h, p1, p2, p3, ctr);
        return c;
      }));
    };
    relabels.push(render);
    render();
  }
  // pasek nad wynikami: który eksperyment i wariant trwa, na co patrzeć, przycisk następnego wariantu
  let bannerState = null;
  function tryBanner(el, it, i, onNext) {
    bannerState = it ? { el, it, i, onNext } : null;
    renderBanner(el);
  }
  function renderBanner(el) {
    const st = bannerState;
    if (!el) return;
    if (!st) { el.hidden = true; el.replaceChildren(); return; }
    const { it, i, onNext } = st, v = it.variants[i];
    el.hidden = false;
    const p1 = document.createElement("p");
    const b = document.createElement("b"); b.textContent = L(it.title[0], it.title[1]);
    p1.append(b, document.createTextNode(" · " + L("wariant", "variant") + ` ${i + 1}/${it.variants.length}: ` + L(v.label[0], v.label[1])));
    const p2 = document.createElement("p"); p2.className = "hint"; p2.textContent = L("Na co patrzeć: ", "What to watch: ") + L(it.look[0], it.look[1]);
    const extra = [];
    const ctr = document.createElement("div"); ctr.className = "controls";
    if (i + 1 < it.variants.length) {
      const n = document.createElement("button"); n.type = "button"; n.className = "btn primary small";
      n.textContent = L("Uruchom wariant ", "Run variant ") + (i + 2) + ": " + L(it.variants[i + 1].label[0], it.variants[i + 1].label[1]);
      n.addEventListener("click", () => onNext(it, i + 1));
      ctr.append(n);
    } else {
      const p3 = document.createElement("p"); p3.className = "hint";
      p3.textContent = L("Czego się spodziewać: ", "What to expect: ") + L(it.expect[0], it.expect[1]);
      extra.push(p3);
    }
    const x = document.createElement("button"); x.type = "button"; x.className = "btn small";
    x.textContent = L("Zamknij", "Close");
    x.addEventListener("click", () => tryBanner(el, null));
    ctr.append(x);
    el.replaceChildren(p1, p2, ...extra, ctr);
  }
  relabels.push(() => { if (bannerState) renderBanner(bannerState.el); });

  // ---------- wersja modelu i config.json ----------
  // skrót SHA-256 pliku modelu wczytanego przez stronę (pierwsze 12 znaków); bez crypto.subtle: FNV-1a
  async function hashText(text) {
    try {
      const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
      return "sha256:" + [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("").slice(0, 12);
    } catch (e) {
      let h = 0x811c9dc5;
      for (let i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
      return "fnv1a:" + h.toString(16).padStart(8, "0");
    }
  }
  function downloadJSON(name, obj) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(obj, null, 2) + "\n"], { type: "application/json;charset=utf-8" }));
    const a = document.createElement("a"); a.href = url; a.download = name;
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return { fileInputs, disabledHint, emptyNote, ready, loadFailed, settings, copy, paramHelp, fmtValue,
    basicAdvanced, sliders: slidersFor, refresh, compare, shortcuts, tryCards, tryBanner, hashText, downloadJSON };
})();
