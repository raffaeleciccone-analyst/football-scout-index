// Football Scout Index: lingua, schede, ricerca, classifica e scheda giocatore.
// Ogni testo viene da testi.js (SPEC F15), ogni numero da dati.js (F16).
(function () {
  "use strict";
  var D = window.DATI || {}, T = window.TESTI || {};
  var lingua = "it", ruolo = "ATT";
  try { lingua = localStorage.getItem("fsi-lingua") || "it"; } catch (e) { /* senza memoria: italiano */ }

  function num(v, dec) {
    if (v === null || v === undefined || v === "") return "–";
    if (typeof v !== "number") return String(v);
    var d = dec === undefined ? 2 : dec;
    return v.toLocaleString(lingua === "it" ? "it-IT" : "en-GB", { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  function t(chiave, valori) {
    var voce = T[chiave];
    if (!voce) return chiave;
    return voce[lingua].replace(/\{(\w+)\}/g, function (_, k) {
      if (!valori || !(k in valori)) return "{" + k + "}";
      return typeof valori[k] === "number" && Math.round(valori[k]) !== valori[k] ? num(valori[k]) : String(valori[k]);
    });
  }
  function el(tag, attr, figli) {
    var e = document.createElement(tag);
    Object.keys(attr || {}).forEach(function (k) { if (k === "testo") e.textContent = attr[k]; else e.setAttribute(k, attr[k]); });
    (figli || []).forEach(function (f) { if (f) e.appendChild(typeof f === "string" ? document.createTextNode(f) : f); });
    return e;
  }
  function metti(id, nodo) { var c = document.getElementById(id); if (c) { c.innerHTML = ""; if (nodo) c.appendChild(nodo); } return c; }
  function lista(G) { return Object.keys(G || {}).map(function (id) { var g = G[id]; g.id = g.id || id; return g; }); }
  function scheda_url(g) { return (g.lega && document.body.dataset.pagina === "home" ? "../" + g.lega + "/" : "") + "giocatore.html?id=" + g.id; }

  // ---- la forbice: banda dell'80%, tacca dell'anno scorso, punto della previsione ----
  function forbice(p, max, banda) {
    var ns = "http://www.w3.org/2000/svg", s = document.createElementNS(ns, "svg"), x = function (v) { return 6 + 248 * Math.max(0, v) / max; };
    s.setAttribute("viewBox", "0 0 260 26"); s.setAttribute("preserveAspectRatio", "none"); s.setAttribute("class", "forbice"); s.setAttribute("aria-hidden", "true");
    function f(tag, a) { var n = document.createElementNS(ns, tag); Object.keys(a).forEach(function (k) { n.setAttribute(k, a[k]); }); s.appendChild(n); }
    f("line", { x1: 6, x2: 254, y1: 13, y2: 13, "class": "linea" });
    if (banda) f("rect", { x: x(p.lo), y: 7, width: Math.max(3, x(p.hi) - x(p.lo)), height: 12, rx: 6, "class": "banda" });
    f("rect", { x: x(p.prima) - 2, y: 2, width: 4, height: 22, "class": "tacca" });
    f("circle", { cx: x(p.pred), cy: 13, r: 6.5, "class": "punto" });
    return s;
  }

  // ---- la scheda di un giocatore (dossier) ----
  function carta(g, opz) {
    var p = g.previsione, mostra = opz.mostra;
    var info = [g.squadra || g.squadra_prima, p && p.eta ? t("card_anni", { n: Math.floor(p.eta) }) : "", p ? t("card_minuti", { n: p.minuti_prima }) : ""].filter(Boolean).join(" · ");
    var figli = [el("span", { "class": "ru " + g.ruolo, testo: t("ruolo_breve_" + g.ruolo) }), el("h4", { testo: g.nome }), el("div", { "class": "info", testo: info })];
    if (mostra) {
      figli.push(el("div", { "class": "cifra" }, [el("b", { testo: num(p.pred) }), el("span", {}, [t("card_previsti"), el("br"), t("card_anno_scorso", { v: num(p.prima) })])]));
      figli.push(forbice(p, opz.max, opz.banda));
      figli.push(el("p", { "class": "perche" }, [t("perche_label") + " ", el("em", { testo: p.motivi.slice(0, 2).map(function (m) { return t("motivo_" + m); }).join(", ") })]));
    } else {
      figli.push(el("div", { "class": "cifra" }, [el("b", { testo: num(p.prima) }), el("span", { testo: t("card_per90_prima") })]));
    }
    figli.push(el("a", { "class": "apri", href: scheda_url(g), testo: t("apri") }));
    var c = el("article", { "class": "carta" + (opz.sv ? " sv" : "") }, figli);
    c.addEventListener("click", function (e) { if (!e.target.closest("a")) location.href = scheda_url(g); });
    return c;
  }
  function griglia(gioc, opz) {
    var tutte = gioc.filter(function (g) { return g.previsione; });
    opz.max = Math.max.apply(null, tutte.map(function (g) { return Math.max(g.previsione.hi, g.previsione.prima); }).concat([0.1]));
    var f = document.createDocumentFragment();
    gioc.forEach(function (g) { f.appendChild(carta(g, opz)); });
    return f;
  }

  function tabella(colonne, righe) {
    var testa = el("tr", {}, colonne.map(function (c) { return el("th", { scope: "col", "class": c.cl || "", testo: t(c.k) }); }));
    var corpo = righe.map(function (r) { return el("tr", {}, colonne.map(function (c) { var v = c.f(r); return el("td", { "class": c.cl || "" }, [v]); })); });
    return el("table", {}, [el("thead", {}, [testa]), el("tbody", {}, corpo)]);
  }
  function link(g) { return el("a", { href: scheda_url(g), testo: g.nome }); }

  // ---- le pagine ----
  function disegna() {
    var pagina = document.body.dataset.pagina, V = D.verdetto || {};
    document.querySelectorAll("[data-ruolo]").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.ruolo === ruolo); });
    if (pagina === "home") {
      var S = D.schede || {};
      ["sv", "top"].forEach(function (k) {
        var c = document.getElementById("home-" + k);
        if (c && S[k]) { c.innerHTML = ""; c.appendChild(griglia(S[k], { mostra: true, banda: true, sv: k === "sv" })); }
      });
      return;
    }
    var G = lista(D.giocatori);
    if (pagina === "index.html") {
      var conP = G.filter(function (g) { return g.previsione; });
      document.querySelectorAll("[data-conta]").forEach(function (s) { s.textContent = "(" + conP.filter(function (g) { return g.ruolo === s.dataset.conta; }).length + ")"; });
      var sv = conP.filter(function (g) { return g.previsione.sottovalutato; }).sort(function (a, b) { return b.previsione.pred - a.previsione.pred; }).slice(0, 8);
      var c = document.getElementById("sottovalutati");
      if (c) { c.innerHTML = ""; c.appendChild(griglia(sv, { mostra: true, banda: V.mostra_forbice, sv: true })); }
      var mostra = V.mostra_previsione;
      var r = conP.filter(function (g) { return g.ruolo === ruolo; })
        .sort(function (a, b) { return mostra ? b.previsione.pred - a.previsione.pred : b.previsione.prima - a.previsione.prima; }).slice(0, 12);
      c = document.getElementById("previsione");
      if (c) { c.innerHTML = ""; c.appendChild(griglia(r, { mostra: mostra, banda: V.mostra_forbice })); }
      var sf = conP.filter(function (g) { return g.previsione.sfortuna90 !== null; }).sort(function (a, b) { return b.previsione.sfortuna90 - a.previsione.sfortuna90; }).slice(0, 10);
      metti("sfortunati", tabella([{ k: "col_nome", f: link }, { k: "col_squadra", f: function (g) { return g.squadra || g.squadra_prima || ""; } },
        { k: "col_sfortuna", f: function (g) { return num(g.previsione.sfortuna90); }, cl: "n" }], sf));
    }
    if (pagina === "classifica.html") {
      var cl = G.filter(function (g) { return g.tpi !== null && g.tpi !== undefined && g.ruolo === ruolo; }).sort(function (a, b) { return b.tpi - a.tpi; });
      metti("classifica", tabella([
        { k: "col_pos", f: function (g) { return String(g.pos_ruolo); }, cl: "n" }, { k: "col_nome", f: link },
        { k: "col_squadra", f: function (g) { return g.squadra || ""; } },
        { k: "col_tpi", f: function (g) { return num(g.tpi); }, cl: "n" }, { k: "col_minuti", f: function (g) { return num(g.minuti, 0); }, cl: "n" }], cl));
    }
    if (pagina === "giocatore.html") scheda();
  }

  function andamento(punti) {
    var ns = "http://www.w3.org/2000/svg", w = 640, h = 100, s = document.createElementNS(ns, "svg");
    var mx = Math.max.apply(null, punti.map(function (p) { return p[1]; }).concat([0.5])), gmax = Math.max.apply(null, punti.map(function (p) { return p[0]; }).concat([2]));
    s.setAttribute("viewBox", "0 0 " + w + " " + h); s.setAttribute("class", "andamento"); s.setAttribute("role", "img"); s.setAttribute("aria-label", t("scheda_andamento"));
    var d = punti.map(function (p, i) { return (i ? "L" : "M") + (8 + (w - 16) * (p[0] - 1) / (gmax - 1)).toFixed(1) + " " + (h - 8 - (h - 16) * p[1] / mx).toFixed(1); }).join(" ");
    var path = document.createElementNS(ns, "path"); path.setAttribute("d", d); s.appendChild(path);
    return s;
  }
  function scheda() {
    var box = document.getElementById("scheda"); if (!box) return;
    var id = new URLSearchParams(location.search).get("id"), g = id && D.giocatori[id], V = D.verdetto;
    box.innerHTML = "";
    if (!g) { box.appendChild(el("p", { testo: t(id ? "scheda_non_trovato" : "scheda_vuota") })); return; }
    box.appendChild(el("h3", { testo: g.nome }));
    box.appendChild(el("p", { "class": "sotto", testo: [g.squadra || g.squadra_prima, g.ruolo ? t("ruolo_" + g.ruolo) : ""].filter(Boolean).join(" · ") }));
    box.appendChild(el("p", { "class": "grande", testo: g.tpi !== null && g.tpi !== undefined ? t("scheda_tpi", { tpi: num(g.tpi), pos: g.pos_ruolo }) : t("scheda_senza_tpi") }));
    if (g.previsione || g.motivo) {
      var sez = el("section", { "class": "previsto" }, [el("h3", { testo: t("scheda_previsione", { stagione: D.stagione_prevista }) })]);
      var p = g.previsione;
      if (g.motivo) sez.appendChild(el("p", { testo: t("escluso_" + g.motivo) }));
      else if (!V.mostra_previsione) sez.appendChild(el("p", { testo: t("previsione_nascosta") }));
      else {
        sez.appendChild(el("p", { testo: t("scheda_previsione_valori", { pred: num(p.pred), lo: num(p.lo), hi: num(p.hi), prima: num(p.prima) }) }));
        sez.appendChild(forbice(p, Math.max(p.hi, p.prima, 0.1) * 1.15, V.mostra_forbice));
        sez.appendChild(el("p", { "class": "perche" }, [t("scheda_motivi") + ": ", el("em", { testo: p.motivi.map(function (m) { return t("motivo_" + m); }).join(", ") })]));
        if (p.sottovalutato && V.mostra_sottovalutati) sez.appendChild(el("p", { "class": "segno", testo: t("sottovalutato_si") }));
      }
      box.appendChild(sez);
    }
    if (g.z) {
      box.appendChild(el("h3", { testo: t("scheda_dimensioni") }));
      box.appendChild(el("ul", { "class": "dimensioni" }, Object.keys(g.z).map(function (k) {
        var v = g.z[k];
        return el("li", {}, [el("span", { testo: t("dim_" + k) }), el("span", { "class": "zbar " + (v >= 0 ? "su" : "giu"), style: "--z:" + (v === null ? 0 : Math.abs(v) / 3) }), el("b", { testo: num(v) })]);
      })));
    }
    if (g.contesti && g.contesti.length) {
      box.appendChild(el("h3", { testo: t("scheda_contesti") }));
      box.appendChild(el("ul", { "class": "contesti" }, g.contesti.map(function (c) {
        return el("li", {}, [el("span", { testo: t("ctx_" + c.c) }), el("b", { testo: num(c.tpi) }),
          el("span", { "class": "sotto", testo: t("ctx_partite", { n: c.partite }) + (c.piccolo ? ", " + t("campione_piccolo") : "") })]);
      })));
    }
    if (g.andamento && g.andamento.length > 1) { box.appendChild(el("h3", { testo: t("scheda_andamento") })); box.appendChild(andamento(g.andamento)); }
  }

  // ---- ricerca: suggerisce i nomi, al "via" apre la scheda ----
  function ricerca() {
    var cerca = document.getElementById("cerca"), nomi = document.getElementById("nomi");
    if (!cerca || !nomi) return;
    var voci = D.ricerca || lista(D.giocatori).map(function (g) { return { n: g.nome, id: g.id }; }), perNome = {};
    voci.forEach(function (v) { perNome[v.n] = v; nomi.appendChild(el("option", { value: v.n })); });
    cerca.addEventListener("change", function () {
      var v = perNome[cerca.value]; if (!v) return;
      if (document.body.dataset.pagina === "giocatore.html") { history.replaceState(null, "", "?id=" + v.id); scheda(); }
      else location.href = (v.lega ? "../" + v.lega + "/" : "") + "giocatore.html?id=" + v.id;
    });
  }

  function applicaLingua() {
    document.documentElement.lang = lingua;
    document.querySelectorAll("[data-t]").forEach(function (e) { var v = {}; try { v = JSON.parse(e.dataset.v || "{}"); } catch (x) { v = {}; } e.textContent = t(e.dataset.t, v); });
    document.querySelectorAll("[data-n]").forEach(function (e) { e.textContent = num(parseFloat(e.dataset.n), parseInt(e.dataset.dec || "2", 10)); });
    document.querySelectorAll("[data-tp]").forEach(function (e) { e.placeholder = t(e.dataset.tp); });
    document.querySelectorAll("[data-lingua]").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.lingua === lingua); });
    disegna();
  }
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-lingua]");
    if (b) { lingua = b.dataset.lingua; try { localStorage.setItem("fsi-lingua", lingua); } catch (e) { /* niente memoria */ } applicaLingua(); }
    var r = ev.target.closest("[data-ruolo]");
    if (r) { ruolo = r.dataset.ruolo; disegna(); }
  });
  ricerca();
  applicaLingua();
})();
