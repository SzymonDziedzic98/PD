// Wspólne drobiazgi interfejsu (ten sam plik w psm-web i SIPD, web/ux.js):
// przyciski wyboru pliku w języku strony, podpowiedzi na wyszarzonych przyciskach, napisy w pustych panelach, opisy parametrów,
// zrozumiały komunikat, gdy Pyodide się nie wczyta, oraz zapamiętywanie ustawień i link z ustawieniami.
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

  return { fileInputs, disabledHint, emptyNote, ready, loadFailed, settings, copy, paramHelp, fmtValue };
})();
