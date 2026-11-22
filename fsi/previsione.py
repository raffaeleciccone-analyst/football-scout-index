"""Previsione del rendimento della stagione dopo (SPEC F2-F10), con la sua prova onesta (C4-C16).

Obiettivo: gol senza rigori + xA per 90 della stagione dopo (o xG buildup per 90 per DIF e CEN, F4).
Pesi stimati dai dati (ridge), prova su giocatori mai visti nella stima. Finché c'è una sola coppia di stagioni la
prova è "a gruppi" (5 gruppi di giocatori) e tutto è un prototipo (C13).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from fsi import config as C
from fsi import db, tpi

RIVALI_TPI_PRO = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "rivali_2024-25.csv"
INGREDIENTI_MOTIVO = ["rendimento", "minuti", "eta", "tendenza", "contesti", "infortuni"]
# shortcut: niente valore di mercato, servono foto datate ad agosto; se le si salva per 2 stagioni, riprovare.


def _per90(righe, colonne):
    return righe[colonne].sum(axis=1).groupby(righe["giocatore_id"]).sum()


def _infortuni(con, ids, stagione, fino_al):
    """Giorni di infortunio nella stagione, solo per infortuni iniziati entro `fino_al` (C4); e chi non ha storia."""
    inf = pd.read_sql("SELECT giocatore_id, giorni_fuori FROM infortuni WHERE stagione = ? AND inizio <= ?", con,
                      params=[stagione, fino_al.date().isoformat()])
    scaricati = {g for (g,) in con.execute("SELECT giocatore_id FROM infortuni_scaricati")}
    giorni = inf.groupby("giocatore_id")["giorni_fuori"].sum().reindex(ids).fillna(0.0)
    return giorni.to_numpy(), (~ids.isin(scaricati)).astype(float).to_numpy()


def _ingredienti_riassunti(con, lega, stagione) -> pd.DataFrame:
    """Stessi ingredienti da una stagione riassunta (archivio): niente tendenza, TPI e contesti (servono le partite)."""
    r = pd.read_sql("SELECT * FROM stagioni_riassunte WHERE lega = ? AND stagione = ? AND minuti > 0", con,
                    params=[lega, stagione]).set_index("giocatore_id")
    t = pd.DataFrame({"minuti": r["minuti"], "partite": r["partite"]})
    t["out90"] = (r["gol_senza_rigori"] + r["xa"]) / r["minuti"] * 90
    t["xgxa90"] = (r["xg_senza_rigori"] + r["xa"]) / r["minuti"] * 90
    t["buildup90"] = r["xg_buildup"] / r["minuti"] * 90
    t["tendenza"] = 0.0
    t["ruolo"] = r["ruolo"]
    t = t[t["ruolo"].isin(C.PESO_RUOLO)]
    nascita = pd.read_sql("SELECT giocatore_id, data_nascita FROM giocatori", con).set_index("giocatore_id")
    fine = pd.Timestamp(f"{int(stagione[:4]) + 1}-05-31")
    t["eta"] = (fine - pd.to_datetime(nascita["data_nascita"].reindex(t.index), errors="coerce")).dt.days / 365.25
    t["tpi"], t["ctx_top6"], t["ctx_casa"] = np.nan, 0.0, 0.0
    t["giorni_inf"], t["inf_manca"] = _infortuni(con, t.index.to_series(), stagione, fine)
    t.insert(0, "lega", lega)
    return t.rename_axis("giocatore_id").reset_index().sort_values("giocatore_id").reset_index(drop=True)


def ingredienti(con, lega, stagione, fino_a_giornata=None) -> pd.DataFrame:
    """Gli ingredienti grezzi di ogni giocatore di movimento in una lega e stagione (fino alla giornata k)."""
    r = db.righe(con, lega, stagione, fino_a_giornata)
    if r.empty and fino_a_giornata is None:
        return _ingredienti_riassunti(con, lega, stagione)
    r = r[r["minuti"] >= 1].sort_values(["giocatore_id", "giornata", "data"], kind="mergesort")
    g = r.groupby("giocatore_id")
    t = pd.DataFrame({"minuti": g["minuti"].sum(), "partite": g.size()})
    t["out90"] = _per90(r, ["gol_senza_rigori", "xa"]) / t["minuti"] * 90
    t["xgxa90"] = _per90(r, ["xg_senza_rigori", "xa"]) / t["minuti"] * 90
    t["buildup90"] = g["xg_buildup"].sum() / t["minuti"] * 90

    def tendenza(x):   # seconda metà delle sue partite meno la prima, in xG+xA per 90
        if len(x) < 6:
            return 0.0
        a, b = x.iloc[: len(x) // 2], x.iloc[len(x) // 2:]
        per90 = lambda p: (p["xg_senza_rigori"] + p["xa"]).sum() / p["minuti"].sum() * 90
        return per90(b) - per90(a)
    t["tendenza"] = g[["xg_senza_rigori", "xa", "minuti"]].apply(tendenza)

    ruoli = pd.read_sql("SELECT giocatore_id, ruolo FROM ruoli WHERE lega = ? AND stagione = ?", con,
                        params=[lega, stagione]).set_index("giocatore_id")["ruolo"]
    t["ruolo"] = ruoli
    t = t[t["ruolo"].isin(C.PESO_RUOLO)]                       # portieri e senza ruolo fuori
    nascita = pd.read_sql("SELECT giocatore_id, data_nascita FROM giocatori", con).set_index("giocatore_id")
    fine = pd.to_datetime(r["data"]).max()
    t["eta"] = (fine - pd.to_datetime(nascita["data_nascita"].reindex(t.index), errors="coerce")).dt.days / 365.25

    classifica, ctx = tpi._calcola(con, lega, stagione, fino_a_giornata)
    t["tpi"] = classifica.set_index("giocatore_id")["tpi"]
    piv = ctx.pivot(index="giocatore_id", columns="contesto", values="tpi")
    t["ctx_top6"] = (piv["vs_top6"] - piv["totale"]).reindex(t.index).fillna(0.0)
    t["ctx_casa"] = (piv["casa"] - piv["trasferta"]).reindex(t.index).fillna(0.0)
    t["giorni_inf"], t["inf_manca"] = _infortuni(con, t.index.to_series(), stagione, fine)
    t.insert(0, "lega", lega)
    return t.rename_axis("giocatore_id").reset_index().sort_values("giocatore_id").reset_index(drop=True)


def ammessi(ingr, soglia):
    """F7: almeno `soglia` minuti; gli altri escono con il motivo scritto."""
    ok = ingr["minuti"] >= soglia
    esclusi = ingr.loc[~ok, ["giocatore_id", "lega"]].assign(motivo="storia insufficiente")
    return ingr[ok].copy(), esclusi


def _soglia(con, lega, stagione, fino_a_giornata):
    if fino_a_giornata is None:
        return C.SOGLIA_PREVISIONE
    giornate = con.execute("SELECT MAX(giornata) FROM partite WHERE lega = ? AND stagione = ?",
                           (lega, stagione)).fetchone()[0]
    return C.SOGLIA_PREVISIONE * fino_a_giornata / max(giornate, 38)


def _reale(con, stagione):
    """Rendimento reale di una stagione, sommando Serie A e Premier (la chiave è l'id Understat)."""
    r = pd.read_sql("SELECT giocatore_id, minuti, gol_senza_rigori, xa, xg_buildup FROM righe "
                    "WHERE stagione = ? AND minuti >= 1", con, params=[stagione])
    if r.empty:   # stagione presa dall'archivio (solo totali)
        r = pd.read_sql("SELECT giocatore_id, minuti, gol_senza_rigori, xa, xg_buildup FROM stagioni_riassunte "
                        "WHERE stagione = ? AND minuti >= 1", con, params=[stagione])
    g = r.groupby("giocatore_id")
    m = g["minuti"].sum()
    return pd.DataFrame({"min_dopo": m, "y_output": (g["gol_senza_rigori"].sum() + g["xa"].sum()) / m * 90,
                         "y_buildup": g["xg_buildup"].sum() / m * 90})


def tabella(con, base, dopo, fino_a_giornata=None, misura="output") -> pd.DataFrame:
    parti = []
    for lega in C.LEGHE:
        ingr = ingredienti(con, lega, base, fino_a_giornata)
        if len(ingr):   # es. Serie A 2022-23: non c'è (l'archivio ha solo mezza stagione)
            parti.append(ammessi(ingr, _soglia(con, lega, base, fino_a_giornata))[0])
    if not parti:
        return pd.DataFrame()
    t = pd.concat(parti, ignore_index=True).merge(_reale(con, dopo), left_on="giocatore_id", right_index=True,
                                                  how="left")
    t["y"] = t[f"y_{misura}"]
    if misura == "buildup":
        t = t[t["ruolo"].isin(["DIF", "CEN"])].reset_index(drop=True)
    return t


# ---------------------------------------------------------------- il modello
def _gruppi(misura, contesti, infortuni=False):
    g = {"rendimento": ["out_t", "xgxa_t"] if misura == "output" else ["build_t"],
         "minuti": ["log_minuti"], "eta": ["eta", "eta2", "eta_manca"], "tendenza": ["tendenza"],
         "contesti": ["ctx_top6", "ctx_casa"] if contesti else [],
         "infortuni": ["log_giorni_inf", "inf_manca"] if infortuni else []}
    return g, [c for cols in g.values() for c in cols] + ["ruolo_CEN", "ruolo_DIF", "premier"]


def _tirato(x, minuti, chiave, medie, k):
    m = chiave.map(medie)
    return (x * minuti + m * k) / (minuti + k)


def _matrice(mod, t):
    chiave = t["lega"] + "|" + t["ruolo"]
    X = pd.DataFrame(index=t.index)
    if mod["misura"] == "output":
        X["out_t"] = _tirato(t["out90"], t["minuti"], chiave, mod["medie"]["out90"], mod["K"])
        X["xgxa_t"] = _tirato(t["xgxa90"], t["minuti"], chiave, mod["medie"]["xgxa90"], mod["K"])
    else:
        X["build_t"] = _tirato(t["buildup90"], t["minuti"], chiave, mod["medie"]["buildup90"], mod["K"])
    X["log_minuti"] = np.log(t["minuti"])
    X["eta_manca"] = t["eta"].isna().astype(float)
    X["eta"] = t["eta"].fillna(mod["eta_media"])
    X["eta2"] = (X["eta"] - mod["eta_media"]) ** 2
    X["tendenza"] = t["tendenza"]
    X["ctx_top6"], X["ctx_casa"] = t["ctx_top6"], t["ctx_casa"]
    X["log_giorni_inf"], X["inf_manca"] = np.log1p(t["giorni_inf"]), t["inf_manca"]
    X["ruolo_CEN"] = (t["ruolo"] == "CEN").astype(float)
    X["ruolo_DIF"] = (t["ruolo"] == "DIF").astype(float)
    X["premier"] = (t["lega"] == "premier").astype(float)
    return X[mod["colonne"]], chiave


def stima(tab, misura="output", contesti=True, infortuni=False):
    """Stima i pesi su chi ha il rendimento reale misurabile (≥ 900' nella stagione dopo)."""
    tr = tab[(tab["min_dopo"] >= C.MINUTI_METRO) & tab["y"].notna()]
    base = "out90" if misura == "output" else "buildup90"
    chiave = tr["lega"] + "|" + tr["ruolo"]
    medie = {c: tr.groupby(chiave)[c].mean() for c in ("out90", "xgxa90", "buildup90")}
    # K della regressione verso la media: quello che, da solo, prevede meglio (è anche il rivale di C10)
    errori = {k: ((_tirato(tr[base], tr["minuti"], chiave, medie[base], k) - tr["y"]) ** 2).mean() for k in C.GRIGLIA_K}
    gruppi, colonne = _gruppi(misura, contesti, infortuni)
    mod = {"misura": misura, "K": min(errori, key=errori.get), "medie": medie, "eta_media": tr["eta"].mean(),
           "gruppi": gruppi, "colonne": colonne}
    X, chiave = _matrice(mod, tr)
    pipe = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 21))).fit(X, tr["y"])
    sc, rg = pipe[0], pipe[1]
    mod["pipe"] = pipe
    mod["pesi"] = dict(zip(colonne, rg.coef_ / sc.scale_))
    mod["medie_x"] = X.groupby(chiave).mean()
    # forbice: ampiezza = a + b/√minuti stimata sui residui, poi i quantili 10-90 dei residui scalati (F6)
    res = tr["y"] - pipe.predict(X)
    A = np.column_stack([np.ones(len(tr)), 1 / np.sqrt(tr["minuti"])])
    mod["scala"] = np.linalg.lstsq(A, res.abs(), rcond=None)[0]
    z = res / np.maximum(A @ mod["scala"], 1e-6)
    mod["quantili"] = (float(z.quantile(0.10)), float(z.quantile(0.90)))
    return mod


def porta_alla_media(mod, righe, ingrediente):
    """Le stesse righe, con un ingrediente riportato alla media del ruolo (serve a verificare i motivi, C15)."""
    return righe.assign(_a_media=ingrediente)


def applica(mod, t) -> pd.DataFrame:
    X, chiave = _matrice(mod, t)
    medie = mod["medie_x"].reindex(chiave).set_axis(X.index)
    if "_a_media" in t:
        for i, ing in t["_a_media"].items():
            for c in mod["gruppi"][ing]:
                X.loc[i, c] = medie.loc[i, c]
    pred = pd.Series(mod["pipe"].predict(X), index=t.index)
    scala = np.maximum(mod["scala"][0] + mod["scala"][1] / np.sqrt(t["minuti"]), 1e-6)
    out = pd.DataFrame({"pred": pred, "lo": pred + mod["quantili"][0] * scala, "hi": pred + mod["quantili"][1] * scala})
    base = "out90" if mod["misura"] == "output" else "buildup90"
    out["rm"] = _tirato(t[base], t["minuti"], chiave, mod["medie"][base], mod["K"])
    contributi = pd.DataFrame({g: sum(mod["pesi"][c] * (X[c] - medie[c]) for c in cols) if cols else 0.0
                               for g, cols in mod["gruppi"].items()}, index=t.index)
    out["motivi"] = [list(r.abs().sort_values(ascending=False, kind="mergesort").index[:3]) for _, r in contributi.iterrows()]
    return out


def fuori_campione(tab, misura="output", contesti=True) -> pd.DataFrame:
    """Previsioni di prova: ogni giocatore è previsto da un modello che non l'ha visto (5 gruppi, C5)."""
    ids = tab["giocatore_id"].unique()
    out = []
    for dentro, fuori in KFold(5, shuffle=True, random_state=0).split(ids):
        prova = tab["giocatore_id"].isin(ids[fuori])
        out.append(applica(stima(tab[~prova], misura, contesti), tab[prova]))
    return pd.concat(out).loc[tab.index]


# ---------------------------------------------------------------- la prova
def _rho_righe(a, r):
    """Spearman riga per riga (ogni riga è un campione ricampionato)."""
    ra, rr = rankdata(a, axis=1), rankdata(r, axis=1)
    ra, rr = ra - ra.mean(1, keepdims=True), rr - rr.mean(1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        return (ra * rr).sum(1) / np.sqrt((ra ** 2).sum(1) * (rr ** 2).sum(1))


def batte(pred, rivale, reale, gruppi=None, n=2000, seed=0) -> dict:
    """C8: batte se l'intervallo 5°-95° della differenza di ρ (bootstrap appaiato) sta tutto sopra zero.

    Con più stagioni di prova (`gruppi`) la ρ si misura dentro ogni stagione e si fa la media pesata: l'ordine
    dei giocatori conta dentro una stagione, non fra stagioni previste da modelli diversi.
    """
    pred, rivale, reale = map(np.asarray, (pred, rivale, reale))
    gruppi = np.zeros(len(reale)) if gruppi is None else np.asarray(gruppi)
    rng = np.random.default_rng(seed)
    pesi, d_boot, r_mod, r_riv = [], [], [], []
    for g in pd.unique(gruppi):
        m = gruppi == g
        if m.sum() < 5:   # troppo pochi per una ρ
            continue
        p, q, y = pred[m], rivale[m], reale[m]
        idx = rng.integers(0, m.sum(), size=(n, m.sum()))
        d_boot.append(_rho_righe(p[idx], y[idx]) - _rho_righe(q[idx], y[idx]))
        r_mod.append(spearmanr(p, y).statistic)
        r_riv.append(spearmanr(q, y).statistic)
        pesi.append(m.sum())
    w = np.array(pesi) / sum(pesi)
    diff = np.nansum(np.array(d_boot) * w[:, None], axis=0)
    lo, hi = np.percentile(diff, [5, 95])
    return {"n": len(reale), "rho_modello": float(np.dot(w, r_mod)), "rho_rivale": float(np.dot(w, r_riv)),
            "diff_lo": float(lo), "diff_hi": float(hi), "batte": bool(lo > 0)}


def copertura(reale, lo, hi) -> float:
    return float(np.mean((np.asarray(reale) >= lo) & (np.asarray(reale) <= hi)))


def mostra_forbice(cop) -> bool:
    return C.COPERTURA_MIN <= round(cop, 4) <= C.COPERTURA_MAX


def _tpi_pro(base):
    if base != "2024-25" or not RIVALI_TPI_PRO.exists():
        return pd.DataFrame({"lega": pd.Series(dtype=str), "giocatore_id": pd.Series(dtype="int64"),
                             "tpi_pro": pd.Series(dtype=float)})
    return pd.read_csv(RIVALI_TPI_PRO)[["lega", "giocatore_id", "tpi_pro"]]


def _valuta(tab, previsioni, base, misura, fino_a_giornata) -> dict:
    """Verdetto per lega: rivali (C8, C12), sottovalutati (C10), forbice (C11), cosa si mostra (C9)."""
    ev = (tab["min_dopo"] >= C.MINUTI_METRO) & tab["y"].notna()
    t = tab[ev].join(previsioni)
    if "tpi_pro" not in t:
        t = t.merge(_tpi_pro(base), on=["lega", "giocatore_id"], how="left")
    grezzo = "out90" if misura == "output" else "buildup90"
    rivali = {"grezzo": grezzo, "minuti": "minuti"}
    if misura == "output" and fino_a_giornata is None:
        rivali |= {"tpi": "tpi", "tpi_pro": "tpi_pro"}
    leghe = {}
    for lega, b in t.groupby("lega"):
        v = {"n": len(b), "rivali": {}}
        for nome, col in rivali.items():
            s = b[b[col].notna()]
            if len(s) >= 30:   # TPI e TPI Pro esistono solo per alcune stagioni di prova
                v["rivali"][nome] = batte(s["pred"], s[col], s["y"], s.get("prova"))
        poco = b[_poco_considerati(b)]
        v["sottovalutati"] = batte(poco["pred"], poco[grezzo], poco["y"], poco.get("prova")) | {
            "rivale": "output grezzo", "gruppo_minuti": [C.SOGLIA_PREVISIONE, C.MINUTI_POCO_CONSIDERATO],
            "eta_massima": C.ETA_MAX_SOTTOVALUTATI}
        cop = copertura(b["y"], b["lo"], b["hi"])
        v["forbice"] = {"copertura": cop, "mostra": mostra_forbice(cop)}
        v["mostra_previsione"] = v["rivali"]["grezzo"]["batte"]
        v["mostra_sottovalutati"] = v["sottovalutati"]["batte"]
        leghe[lega] = v
    return leghe


def prova(con, base, dopo, misura="output", fino_a_giornata=None) -> dict:
    """Prova a gruppi su una coppia sola: un prototipo (C13)."""
    tab = tabella(con, base, dopo, fino_a_giornata, misura)
    ev = (tab["min_dopo"] >= C.MINUTI_METRO) & tab["y"].notna()
    rho = {}
    for ctx in (True, False):   # i contesti restano solo se migliorano la prova (F1b, C3c)
        oof = fuori_campione(tab, misura, ctx)
        rho[ctx] = spearmanr(oof.loc[ev, "pred"], tab.loc[ev, "y"]).statistic
    tenuti = bool(rho[True] > rho[False])
    leghe = _valuta(tab, fuori_campione(tab, misura, tenuti), base, misura, fino_a_giornata)
    return {"base": base, "dopo": dopo, "misura": misura, "giornata": fino_a_giornata,
            "stato": "prototipo, non verificato",
            "contesti_tenuti": tenuti, "rho_con_contesti": float(rho[True]), "rho_senza_contesti": float(rho[False]),
            "leghe": leghe}


COPPIE = [("2021-22", "2022-23"), ("2022-23", "2023-24"), ("2023-24", "2024-25"), ("2024-25", "2025-26")]


def prova_vera(con, coppie, misura="output", infortuni=False) -> dict:
    """Prova a finestra mobile (C13): ogni coppia si prevede con un modello stimato solo sulle coppie prima.

    I verdetti per lega mettono insieme tutte le stagioni di prova. Contesti fuori: scartati dal prototipo,
    e le stagioni dell'archivio non li hanno.
    shortcut: chi è in due stagioni di prova conta due volte nel bootstrap (intervallo un po' ottimista);
    con più stagioni, ricampionare per giocatore.
    """
    tabelle = {c: tabella(con, *c, misura=misura) for c in coppie}
    parti, stimata_su, per_stagione = [], {}, {}
    for i, (base, dopo) in enumerate(coppie):
        prima = [c for c in coppie[:i] if len(tabelle[c])]
        tab = tabelle[(base, dopo)]
        if not prima or tab.empty:
            continue
        mod = stima(pd.concat([tabelle[c] for c in prima], ignore_index=True), misura, contesti=False,
                    infortuni=infortuni)
        nome = f"{base} -> {dopo}"
        stimata_su[nome] = [f"{a} -> {d}" for a, d in prima]
        t = tab.join(applica(mod, tab)).merge(_tpi_pro(base), on=["lega", "giocatore_id"], how="left")
        t["prova"] = f"{base} -> {dopo}"
        ev = t[(t["min_dopo"] >= C.MINUTI_METRO) & t["y"].notna()]
        grezzo = "out90" if misura == "output" else "buildup90"
        per_stagione[nome] = {l: {"n": len(b), "rho_modello": float(spearmanr(b["pred"], b["y"]).statistic),
                                  "rho_grezzo": float(spearmanr(b[grezzo], b["y"]).statistic)}
                              for l, b in ev.groupby("lega")}
        parti.append(t)
    tutte = pd.concat(parti, ignore_index=True)
    previsioni = tutte[["pred", "lo", "hi", "rm", "motivi"]]
    leghe = _valuta(tutte.drop(columns=previsioni.columns), previsioni, None, misura, None)
    return {"misura": misura, "infortuni": infortuni,
            "stato": "verificata (prova a finestra mobile su stagioni mai viste)",
            "stimata_su": stimata_su, "per_stagione": per_stagione, "leghe": leghe}


# ---------------------------------------------------------------- la previsione pubblicata
def _stagione_dopo(stagione):
    a = int(stagione[:4]) + 1
    return f"{a}-{str(a + 1)[2:]}"


def prevedi(con, mod, base):
    """Previsione per la stagione dopo `base`, per chi ha i minuti; gli altri escono con il motivo (F7)."""
    parti, esclusi = [], []
    for lega in C.LEGHE:
        ok, fuori = ammessi(ingredienti(con, lega, base), C.SOGLIA_PREVISIONE)
        parti.append(ok)
        esclusi.append(fuori)
    t = pd.concat(parti, ignore_index=True)
    p = t[["giocatore_id", "lega", "ruolo", "minuti", "eta", "out90", "xgxa90"]].join(applica(mod, t))
    p["posizione_ruolo"] = p.groupby(["lega", "ruolo"])["pred"].rank(ascending=False, method="first").astype(int)
    p = p.sort_values(["lega", "ruolo", "posizione_ruolo"]).reset_index(drop=True)
    in_base = {g for (g,) in con.execute("SELECT DISTINCT giocatore_id FROM righe WHERE stagione = ?", (base,))}
    nuovi = pd.read_sql("SELECT DISTINCT giocatore_id, lega FROM righe WHERE stagione = ?", con,
                        params=[_stagione_dopo(base)])
    nuovi = nuovi[~nuovi["giocatore_id"].isin(in_base)].assign(motivo="nessun dato nel campionato")
    return p, pd.concat(esclusi + [nuovi], ignore_index=True)


def _poco_considerati(t):
    """F3: da 450' a meno di 1500', fino a 25 anni compiuti (età sconosciuta = fuori)."""
    return ((t["minuti"] >= C.SOGLIA_PREVISIONE) & (t["minuti"] < C.MINUTI_POCO_CONSIDERATO)
            & (t["eta"] < C.ETA_MAX_SOTTOVALUTATI + 1))


def sottovalutati(prev) -> pd.DataFrame:
    """F3: forti ma poco considerati = rendimento previsto più alto fra i giovani con pochi minuti."""
    poco = prev[_poco_considerati(prev)]
    return poco.sort_values(["lega", "ruolo", "pred"], ascending=[True, True, False]).reset_index(drop=True)


def sfortunati(prev) -> pd.DataFrame:
    """F3b: più xG che gol (senza rigori), per 90. Descrizione della stagione, non una previsione."""
    s = prev.assign(sfortuna90=prev["xgxa90"] - prev["out90"], nota="descrizione, non previsione")
    return s.sort_values("sfortuna90", ascending=False, kind="mergesort").reset_index(drop=True)


def salva_agosto(prev, stagione, cartella) -> Path:
    """La previsione di agosto si scrive una volta e non si riscrive più (F10, C14)."""
    p = Path(cartella) / f"previsione_agosto_{stagione}.json"
    if not p.exists():
        p.write_text(prev.to_json(orient="records", force_ascii=False), encoding="utf-8")
    return p


def giornata_valida(prove: dict, giornata):
    """Ultimo punto di controllo raggiunto; vale solo se la sua prova è passata (C14)."""
    raggiunti = [k for k in sorted(prove) if k <= giornata]
    return raggiunti[-1] if raggiunti and prove[raggiunti[-1]] else None


def prove_aggiornata(con, base, dopo) -> dict:
    """La previsione aggiornata provata a ogni punto di controllo: {giornata: verdetto} (F10, C14)."""
    return {k: prova(con, base, dopo, fino_a_giornata=k) for k in C.CONTROLLI_AGGIORNATA}


if __name__ == "__main__":
    con = db.apri()
    cartella = C.RADICE / "prove"
    cartella.mkdir(exist_ok=True)
    esito = {m: prova(con, "2024-25", "2025-26", m) for m in ("output", "buildup")}
    esito["aggiornata"] = prove_aggiornata(con, "2024-25", "2025-26")
    (cartella / "prototipo_2024-25_2025-26.json").write_text(json.dumps(esito, indent=1, ensure_ascii=False),
                                                             encoding="utf-8")
    vera = {m: prova_vera(con, COPPIE, m) for m in ("output", "buildup")}
    (cartella / "vera_2024-25_2025-26.json").write_text(json.dumps(vera, indent=1, ensure_ascii=False), encoding="utf-8")
