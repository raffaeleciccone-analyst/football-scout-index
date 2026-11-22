"""Il sito: home comune + un sito per lega, pagine statiche nelle due lingue (SPEC F11-F16, F19).

I numeri arrivano tutti dai dati (F16): le frasi sono modelli in sito/testi.json, riempiti qui (italiano) e
riscritti dallo script quando si sceglie l'inglese. Fino al cambio si scrive solo in una cartella propria (V8, C28).
Uso: python -m fsi.sito  (scrive in uscita/)
"""
import json
import math
import shutil
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape

from fsi import config as C
from fsi import db, previsione as P, tpi

SORGENTE = C.RADICE / "sito"
VIETATE = [Path(r"C:\dev\serie-a-index"), Path(r"C:\dev\premier-league-index")]
PAGINE = ["index.html", "classifica.html", "giocatore.html", "metodo.html"]
NOMI = {"serie_a": "Serie A", "premier": "Premier League"}
FISSI = ["stile.css", "sito.js"]


def _pulito(x):
    """Numeri pronti per JSON: NaN -> null, 3 decimali."""
    if isinstance(x, float):
        return None if math.isnan(x) else round(x, 3)
    if isinstance(x, dict):
        return {k: _pulito(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_pulito(v) for v in x]
    return x.item() if hasattr(x, "item") else x


def _numero_it(v):
    return f"{v:.2f}".replace(".", ",") if isinstance(v, float) else str(v)


def _ambiente(testi):
    env = Environment(loader=FileSystemLoader(SORGENTE), autoescape=True)

    def t(chiave, tag="span", cls=None, **valori):
        testo = testi[chiave]["it"].format(**{k: _numero_it(v) for k, v in valori.items()})
        dati = escape(json.dumps(_pulito(valori), ensure_ascii=False))
        classe = f' class="{cls}"' if cls else ""
        return Markup(f'<{tag}{classe} data-t="{chiave}" data-v="{dati}">{escape(testo)}</{tag}>')
    env.globals["t"] = t
    # numero scritto in pagina: in italiano 0,82; lo script lo riscrive 0.82 in inglese
    env.filters["n"] = lambda v, dec=2: Markup(f'<span data-n="{v}" data-dec="{dec}">{f"{v:.{dec}f}".replace(".", ",")}</span>')
    return env


def _dati_lega(con, lega, stagione, prev, esclusi, verdetto, verdetto_costruzione, stagione_prevista):
    classifica, ctx = tpi._calcola(con, lega, stagione)
    nomi = dict(con.execute("SELECT giocatore_id, nome FROM giocatori"))
    righe = db.righe(con, lega, stagione)
    righe = righe[righe["minuti"] >= 1].sort_values(["giornata", "data"])
    righe["per90"] = (righe["xg_senza_rigori"] + righe["xa"]) / righe["minuti"] * 90
    andamento = {g: b[["giornata", "per90"]].values.tolist() for g, b in righe.groupby("giocatore_id")}
    # sotto le 4 presenze anche il totale non ha TPI (Q-C2 = B): restano fuori dalla classifica
    classifica = classifica[classifica["tpi"].notna()].copy()
    classifica["pos_ruolo"] = classifica.groupby("ruolo")["tpi"].rank(ascending=False, method="first")
    giocatori = {}
    for r in classifica.itertuples(index=False):
        mie = ctx[(ctx["giocatore_id"] == r.giocatore_id) & ctx["tpi"].notna()]
        giocatori[int(r.giocatore_id)] = {
            "nome": r.nome, "squadra": r.squadra, "ruolo": r.ruolo, "tpi": r.tpi, "pos_ruolo": int(r.pos_ruolo),
            "minuti": int(r.minuti), "z": {d: getattr(r, f"z_{d}") for d in tpi.DIMENSIONI},
            "contesti": [{"c": c.contesto, "tpi": c.tpi, "partite": int(c.partite), "piccolo": bool(c.partite < C.CONTESTO_PICCOLO)}
                         for c in mie.itertuples(index=False)],
            "andamento": andamento.get(r.giocatore_id, [])}
    p = prev[prev["lega"] == lega]
    # la squadra della stagione di partenza (l'ultima con cui ha giocato), anche per chi non è nella classifica TPI
    a = int(stagione_prevista[:4]) - 1
    base = db.righe(con, lega, f"{a}-{str(a + 1)[2:]}").sort_values(["giornata", "data"])
    squadra_base = base.groupby("giocatore_id")["squadra"].last()
    sotto = set(P.sottovalutati(p)["giocatore_id"])
    sfortuna = P.sfortunati(p).set_index("giocatore_id")["sfortuna90"]
    for r in p.itertuples(index=False):
        g = giocatori.setdefault(int(r.giocatore_id), {"nome": nomi.get(r.giocatore_id, "?"), "ruolo": r.ruolo, "tpi": None})
        g["squadra_prima"] = squadra_base.get(r.giocatore_id)
        g["previsione"] = {"pred": r.pred, "lo": r.lo, "hi": r.hi, "prima": r.out90, "minuti_prima": int(r.minuti),
                           "eta": r.eta, "motivi": list(r.motivi), "sottovalutato": r.giocatore_id in sotto,
                           "sfortuna90": sfortuna.get(r.giocatore_id), "pos_ruolo": int(r.posizione_ruolo)}
    for r in esclusi[esclusi["lega"] == lega].itertuples(index=False):
        giocatori.setdefault(int(r.giocatore_id), {"nome": nomi.get(r.giocatore_id, "?"), "tpi": None})["motivo"] = r.motivo
    v = verdetto["leghe"][lega]
    pesi = {d: C.PESI_TPI[d] / sum(C.PESI_TPI.values()) for d in C.PESI_TPI}   # pesi effettivi (sommano a 1)
    return _pulito({
        "lega": lega, "stagione": stagione, "stagione_prevista": stagione_prevista, "giocatori": giocatori,
        "verdetto": {"stato": verdetto["stato"], "verificata": verdetto["stato"].startswith("verificata"),
                     "mostra_previsione": v["mostra_previsione"], "mostra_sottovalutati": v["mostra_sottovalutati"],
                     "mostra_forbice": v["forbice"]["mostra"], "copertura": v["forbice"]["copertura"],
                     "rivali": v["rivali"], "sottovalutati": v["sottovalutati"],
                     "per_stagione": {k: x[lega] for k, x in verdetto["per_stagione"].items() if lega in x},
                     "infortuni": verdetto.get("infortuni", False),
                     # la frase sugli infortuni esce solo se la prova con e senza infortuni è stata fatta davvero
                     "infortuni_provati": verdetto.get("infortuni_provati", False),
                     "costruzione": verdetto_costruzione["leghe"][lega]["mostra_previsione"] if verdetto_costruzione else None},
        "metodo": {"pesi_tpi": pesi, "soglia": C.SOGLIA_PREVISIONE, "metro": C.MINUTI_METRO,
                   "poco": C.MINUTI_POCO_CONSIDERATO, "eta_max": C.ETA_MAX_SOTTOVALUTATI}})


def _scrivi_js(percorso, nome, dati):
    percorso.write_text(f"window.{nome} = {json.dumps(dati, ensure_ascii=False)};\n", encoding="utf-8")


def genera(con, cartella, stagioni_tpi, prev, esclusi, verdetto, verdetto_costruzione=None,
           stagione_prevista=None):
    cartella = Path(cartella).resolve()
    if any(cartella == v or cartella.is_relative_to(v) for v in VIETATE):
        raise ValueError(f"{cartella} è la cartella di un sito: fino al cambio si scrive solo altrove (V8)")
    testi = json.loads((SORGENTE / "testi.json").read_text(encoding="utf-8"))
    env = _ambiente(testi)
    riassunto, tutti = {}, {}
    for lega, stagione in stagioni_tpi.items():
        uscita = cartella / lega
        uscita.mkdir(parents=True, exist_ok=True)
        dati = _dati_lega(con, lega, stagione, prev, esclusi, verdetto, verdetto_costruzione, stagione_prevista)
        riassunto[lega] = dati["verdetto"]
        tutti[lega] = dati["giocatori"]
        _scrivi_js(uscita / "dati.js", "DATI", dati)
        _scrivi_js(uscita / "testi.js", "TESTI", testi)
        for f in FISSI:
            shutil.copy(SORGENTE / f, uscita / f)
        for pagina in PAGINE:
            html = env.get_template(pagina).render(d=dati, v=dati["verdetto"], m=dati["metodo"], pagina=pagina)
            (uscita / pagina).write_text(html, encoding="utf-8")
    home = cartella / "home"
    home.mkdir(parents=True, exist_ok=True)
    _scrivi_js(home / "testi.js", "TESTI", testi)
    # in vetrina: i giovani della prima lega dove la lista ha passato la prova, le previsioni della prima dove passa
    vetrina = {"sv": next((l for l, v in riassunto.items() if v["mostra_sottovalutati"]), None),
               "top": next((l for l, v in riassunto.items() if v["mostra_previsione"]), None)}
    schede = {}
    if vetrina["sv"]:
        G = tutti[vetrina["sv"]]
        schede["sv"] = sorted([dict(g, id=i, lega=vetrina["sv"]) for i, g in G.items() if g.get("previsione", {}).get("sottovalutato")],
                              key=lambda g: -g["previsione"]["pred"])[:3]
    if vetrina["top"]:
        G = tutti[vetrina["top"]]
        schede["top"] = sorted([dict(g, id=i, lega=vetrina["top"]) for i, g in G.items() if g.get("previsione")],
                               key=lambda g: -g["previsione"]["pred"])[:3]
    ricerca = [{"n": g["nome"], "id": i, "lega": l} for l, G in tutti.items() for i, g in G.items()]
    _scrivi_js(home / "dati.js", "DATI", {"leghe": riassunto, "schede": schede, "ricerca": ricerca})
    for f in FISSI:
        shutil.copy(SORGENTE / f, home / f)
    (home / "index.html").write_text(env.get_template("home.html").render(
        leghe=riassunto, vetrina=vetrina, nomi=NOMI, eta_max=C.ETA_MAX_SOTTOVALUTATI,
        stagione_prevista=stagione_prevista, pagina="home"), encoding="utf-8")
    return cartella


if __name__ == "__main__":
    import sys
    con = db.apri()
    verdetto = json.loads((C.RADICE / "prove" / "vera_2024-25_2025-26.json").read_text(encoding="utf-8"))
    mod = P.stima(pd.concat([P.tabella(con, *c) for c in P.COPPIE], ignore_index=True), contesti=False)
    prev, esclusi = P.prevedi(con, mod, "2025-26")
    print(genera(con, C.USCITA, {"serie_a": "2026-27", "premier": "2026-27"}, prev, esclusi, verdetto["output"],
                 verdetto.get("buildup"), stagione_prevista="2026-27"), file=sys.stderr)
