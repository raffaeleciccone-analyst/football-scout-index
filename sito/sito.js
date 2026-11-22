// Football Scout Index: lingua, tabelle e scheda giocatore. Tutti i testi vengono da testi.js (SPEC F15),
// tutti i numeri da dati.js (F16).
(function () {
  "use strict";
  var D = window.DATI || {}, T = window.TESTI || {};
  var lingua = "it";
  try { lingua = localStorage.getItem("fsi-lingua") || "it"; } catch (e) { /* senza memoria: italiano */ }

  function num(v, dec) {
    if (v === null || v === undefined || v === "") return "–";
    if (typeof v !== "number") return String(v);
    return v.toLocaleString(lingua === "it" ? "it-IT" : "en-GB",
      { minimumFractionDigits: dec === undefined ? 2 : dec, maximumFractionDigits: dec === undefined ? 2 : dec });
  }
  function t(chiave, valori) {
    var voce = T[chiave];
    if (!voce) return chiave;
    return voce[lingua].replace(/\{(\w+)\}/g, function (_, k) { return valori && k in valori ? num(valori[k]) : "{" + k + "}"; });
  }
  function el(tag, attr, figli) {
    var e = document.createElement(tag);
    Object.keys(attr || {}).forEach(function (k) {
      if (k === "testo") e.textContent = attr[k]; else e.setAttribute(k, attr[k]);
    });
    (figli || []).forEach(function (f) { if (f) e.appendChild(f); });
    return e;
  }
  function giocatori() {
    var G = D.giocatori || {};
    return Object.keys(G).map(function (id) { var g = G[id]; g.id = id; return g; });
  }
  function link(g) { return el("a", { href: "giocatore.html?id=" + g.id, testo: g.nome }); }

  // ---- la forbice: intervallo, punto della previsione, tacca della stagione prima ----
  function forbice(p, max) {
    var ns = "http://www.w3.org/2000/svg", w = 220, h = 18, x = function (v) { return 4 + (w - 8) * Math.max(0, v) / max; };
    var s = document.createElementNS(ns, "svg");
    s.setAttribute("viewBox", "0 0 " + w + " " + h); s.setAttribute("class", "forbice"); s.setAttribute("aria-hidden", "true");
    function f(tag, a) { var n = document.createElementNS(ns, tag); Object.keys(a).forEach(function (k) { n.setAttribute(k, a[k]); }); s.appendChild(n); }
    if (D.verdetto.mostra_forbice) f("rect", { x: x(p.lo), y: 5, width: Math.max(2, x(p.hi) - x(p.lo)), height: 8, rx: 4, "class": "banda" });
    f("line", { x1: x(p.prima), x2: x(p.prima), y1: 2, y2: 16, "class": "tacca" });
    f("circle", { cx: x(p.pred), cy: 9, r: 4.5, "class": "punto" });
    return s;
  }

  function tabella(colonne, righe) {
    var testa = el("tr", {}, colonne.map(function (c) { return el("th", { scope: "col", testo: t(c.k) }); }));
    var corpo = righe.map(function (r) { return el("tr", {}, colonne.map(function (c) { var v = c.f(r); return el("td", { "class": c.cl || "" }, [typeof v === "object" ? v : document.createTextNode(v)]); })); });
    return el("table", {}, [el("thead", {}, [testa]), el("tbody", {}, corpo)]);
  }
  function metti(id, nodo) { var c = document.getElementById(id); if (c) { c.innerHTML = ""; c.appendChild(nodo); } }

  var ruolo = "ATT";
  function disegna() {
    var tutti = giocatori();
    document.querySelectorAll("[data-ruolo]").forEach(function (b) { b.setAttribute("aria-selected", b.dataset.ruolo === ruolo); });
    var pagina = document.body.dataset.pagina;
    if (pagina === "index.html") {
      var r = tutti.filter(function (g) { return g.tpi !== null && g.ruolo === ruolo; }).sort(function (a, b) { return b.tpi - a.tpi; });
      metti("classifica", tabella([
        { k: "col_pos", f: function (g) { return String(g.pos_ruolo); }, cl: "n" },
        { k: "col_nome", f: link }, { k: "col_squadra", f: function (g) { return g.squadra || ""; } },
        { k: "col_tpi", f: function (g) { return num(g.tpi); }, cl: "n" },
        { k: "col_minuti", f: function (g) { return num(g.minuti, 0); }, cl: "n" }], r));
    }
    if (pagina === "previsione.html") {
      var conP = tutti.filter(function (g) { return g.previsione; });
      var max = Math.max.apply(null, conP.map(function (g) { return Math.max(g.previsione.hi, g.previsione.prima); }).concat([0.1]));
      var mostra = D.verdetto.mostra_previsione;
      var lista = conP.filter(function (g) { return g.ruolo === ruolo; })
        .sort(function (a, b) { return mostra ? b.previsione.pred - a.previsione.pred : b.previsione.prima - a.previsione.prima; });
      var col = [{ k: "col_nome", f: link }, { k: "col_eta", f: function (g) { return num(g.previsione.eta, 0); }, cl: "n" },
                 { k: "col_prima", f: function (g) { return num(g.previsione.prima); }, cl: "n" }];
      if (mostra) col.push({ k: "col_previsione", f: function (g) { return num(g.previsione.pred); }, cl: "n forte" },
                           { k: "col_forbice", f: function (g) { return forbice(g.previsione, max); } });
      metti("previsione", tabella(col, lista));
      var sotto = conP.filter(function (g) { return g.previsione.sottovalutato; }).sort(function (a, b) { return b.previsione.pred - a.previsione.pred; }).slice(0, 15);
      metti("sottovalutati", tabella([{ k: "col_nome", f: link }, { k: "col_eta", f: function (g) { return num(g.previsione.eta, 0); }, cl: "n" },
        { k: "col_minuti", f: function (g) { return num(g.previsione.minuti_prima, 0); }, cl: "n" },
        { k: "col_previsione", f: function (g) { return num(g.previsione.pred); }, cl: "n forte" }], sotto));
      var sf = conP.filter(function (g) { return g.previsione.sfortuna90 !== null; }).sort(function (a, b) { return b.previsione.sfortuna90 - a.previsione.sfortuna90; }).slice(0, 15);
      metti("sfortunati", tabella([{ k: "col_nome", f: link }, { k: "col_sfortuna", f: function (g) { return num(g.previsione.sfortuna90); }, cl: "n" }], sf));
    }
    if (pagina === "giocatore.html") scheda();
  }

  function andamento(punti) {
    var ns = "http://www.w3.org/2000/svg", w = 560, h = 90, mx = Math.max.apply(null, punti.map(function (p) { return p[1]; }).concat([0.5]));
    var s = document.createElementNS(ns, "svg");
    s.setAttribute("viewBox", "0 0 " + w + " " + h); s.setAttribute("class", "andamento"); s.setAttribute("role", "img");
    s.setAttribute("aria-label", t("scheda_andamento"));
    var gmax = Math.max.apply(null, punti.map(function (p) { return p[0]; }).concat([1]));
    var d = punti.map(function (p, i) { return (i ? "L" : "M") + (6 + (w - 12) * (p[0] - 1) / Math.max(1, gmax - 1)).toFixed(1) + " " + (h - 6 - (h - 12) * p[1] / mx).toFixed(1); }).join(" ");
    var path = document.createElementNS(ns, "path"); path.setAttribute("d", d); s.appendChild(path);
    return s;
  }

  function scheda() {
    var box = document.getElementById("scheda"); if (!box) return;
    var id = new URLSearchParams(location.search).get("id");
    var g = id && D.giocatori[id];
    box.innerHTML = "";
    if (!g) { box.appendChild(el("p", { testo: t(id ? "scheda_non_trovato" : "scheda_vuota") })); return; }
    g.id = id;
    box.appendChild(el("h2", { testo: g.nome }));
    if (g.squadra || g.ruolo) box.appendChild(el("p", { "class": "sotto", testo: [g.squadra, g.ruolo ? t("ruolo_" + g.ruolo) : ""].filter(Boolean).join(", ") }));
    box.appendChild(el("p", { "class": "grande", testo: g.tpi !== null ? t("scheda_tpi", { tpi: g.tpi, pos: g.pos_ruolo }) : t("scheda_senza_tpi") }));
    if (g.previsione || g.motivo) {
      var sez = el("section", { "class": "riquadro previsto" }, [el("h3", { testo: t("scheda_previsione", { stagione: D.stagione_prevista }) })]);
      if (g.motivo) sez.appendChild(el("p", { testo: t("escluso_" + g.motivo) }));
      else if (!D.verdetto.mostra_previsione) sez.appendChild(el("p", { testo: t("previsione_nascosta") }));
      else {
        var p = g.previsione;
        sez.appendChild(el("p", { testo: t("scheda_previsione_valori", { pred: p.pred, lo: p.lo, hi: p.hi, prima: p.prima }) }));
        sez.appendChild(forbice(p, Math.max(p.hi, p.prima, 0.1) * 1.15));
        sez.appendChild(el("h4", { testo: t("scheda_motivi") }));
        sez.appendChild(el("ul", {}, p.motivi.map(function (m) { return el("li", { testo: t("motivo_" + m) }); })));
        if (p.sottovalutato && D.verdetto.mostra_sottovalutati) sez.appendChild(el("p", { "class": "segno", testo: t("sottovalutato_si") }));
      }
      box.appendChild(sez);
    }
    if (g.z) {
      box.appendChild(el("h3", { testo: t("scheda_dimensioni") }));
      box.appendChild(el("ul", { "class": "dimensioni" }, Object.keys(g.z).map(function (k) {
        var v = g.z[k];
        var barra = el("span", { "class": "zbar " + (v >= 0 ? "su" : "giu"), style: "--z:" + (v === null ? 0 : Math.abs(v) / 3) });
        return el("li", {}, [el("span", { testo: t("dim_" + k) }), barra, el("b", { testo: num(v) })]);
      })));
    }
    if (g.contesti && g.contesti.length) {
      box.appendChild(el("h3", { testo: t("scheda_contesti") }));
      box.appendChild(el("ul", { "class": "contesti" }, g.contesti.map(function (c) {
        return el("li", {}, [el("span", { testo: t("ctx_" + c.c) }), el("b", { testo: num(c.tpi) }),
          el("span", { "class": "sotto", testo: t("ctx_partite", { n: c.partite }) + (c.piccolo ? ", " + t("campione_piccolo") : "") })]);
      })));
    }
    if (g.andamento && g.andamento.length) {
      box.appendChild(el("h3", { testo: t("scheda_andamento") }));
      box.appendChild(andamento(g.andamento));
    }
  }

  function applicaLingua() {
    document.documentElement.lang = lingua;
    document.querySelectorAll("[data-t]").forEach(function (e) {
      var v = {}; try { v = JSON.parse(e.dataset.v || "{}"); } catch (x) { v = {}; }
      e.textContent = t(e.dataset.t, v);
    });
    document.querySelectorAll("[data-tp]").forEach(function (e) { e.placeholder = t(e.dataset.tp); });
    document.querySelectorAll("[data-lingua]").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.lingua === lingua); });
    if (D.giocatori) disegna();
  }

  document.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-lingua]");
    if (b) { lingua = b.dataset.lingua; try { localStorage.setItem("fsi-lingua", lingua); } catch (e) { /* niente memoria */ } applicaLingua(); }
    var r = ev.target.closest("[data-ruolo]");
    if (r) { ruolo = r.dataset.ruolo; disegna(); }
  });
  var cerca = document.getElementById("cerca");
  if (cerca) {
    var nomi = document.getElementById("nomi"), perNome = {};
    giocatori().forEach(function (g) { perNome[g.nome] = g.id; nomi.appendChild(el("option", { value: g.nome })); });
    cerca.addEventListener("change", function () {
      var id = perNome[cerca.value];
      history.replaceState(null, "", "?id=" + (id || ""));
      scheda();
    });
  }
  applicaLingua();
})();
