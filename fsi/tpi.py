"""TPI descrittivo (SPEC F1) e i suoi 5 contesti (F1b).

Nasce da _ricostruzione/indice3/indice.py (identico al pubblicato). Il "totale" è un contesto come gli altri:
stesse formule su un sottoinsieme di partite. Le regole dei contesti sono ricavate da parte1_analisi.py del motore
vecchio (compute_dimensions, compute_all_contexts, _weighted_tpi): vedi SPEC_CONTESTI.md.
"""
import numpy as np
import pandas as pd

from fsi import config as C
from fsi import db

DIM_CONTESTO = ["output", "buildup", "centralita", "boost", "consistenza"]  # cambiano col contesto
DIM_STAGIONE = ["finishing", "form"]                                       # uguali in tutti i contesti
DIMENSIONI = DIM_CONTESTO + DIM_STAGIONE


def _dati(con, lega, stagione, fino_a_giornata):
    pg = db.righe(con, lega, stagione, fino_a_giornata)
    pg = pg[pg["minuti"] >= 1].copy()                     # presenza = almeno 1 minuto
    pg["data"] = pd.to_datetime(pg["data"])
    sql = "SELECT * FROM partite WHERE lega = ? AND stagione = ?"
    par = [lega, stagione]
    if fino_a_giornata is not None:
        sql += " AND giornata <= ?"
        par.append(fino_a_giornata)
    cal = pd.read_sql(sql, con, params=par)
    cal["data"] = pd.to_datetime(cal["data"])
    ruoli = pd.read_sql("SELECT giocatore_id, ruolo FROM ruoli WHERE lega = ? AND stagione = ?", con,
                        params=[lega, stagione])
    nomi = pd.read_sql("SELECT giocatore_id, nome FROM giocatori", con)
    return pg, cal, ruoli, nomi


def _partite_squadra(cal):
    """Una riga per squadra per partita: xG fatti e concessi (rigori compresi)."""
    lati = []
    for lato, sq, avv, fatti, concessi in (("casa", "casa", "trasferta", "xg_casa", "xg_trasferta"),
                                           ("trasferta", "trasferta", "casa", "xg_trasferta", "xg_casa")):
        lati.append(pd.DataFrame({"partita_id": cal["partita_id"], "lato": lato, "squadra": cal[sq],
                                  "avversario": cal[avv], "xg_fatti": cal[fatti], "xg_concessi": cal[concessi],
                                  "gol_fatti": cal[f"gol_{sq}"], "gol_subiti": cal[f"gol_{avv}"]}))
    return pd.concat(lati, ignore_index=True)


def _squadre_di_riferimento(ps):
    """Le prime 6 per punti (poi differenza reti, gol fatti) e le squadre in ordine di xG concessi a partita
    (sempre dalle partite Understat: decisione Q-C1 = B, una fonte sola)."""
    ps = ps.assign(punti=np.select([ps["gol_fatti"] > ps["gol_subiti"], ps["gol_fatti"] == ps["gol_subiti"]], [3, 1], 0))
    t = ps.groupby("squadra").agg(punti=("punti", "sum"), gf=("gol_fatti", "sum"), gs=("gol_subiti", "sum"),
                                  xgc=("xg_concessi", "mean"))
    t["dr"] = t["gf"] - t["gs"]
    prime = list(t.sort_values(["punti", "dr", "gf"], ascending=False).index[:C.N_SQUADRE_FORTI])
    return prime, list(t.sort_values("xgc").index)   # le difese tutte in ordine: le 6 si scelgono per giocatore


def _z(valori, riferimento):
    """z dentro il ruolo: media e deviazione dai valori di riferimento schiacciati al 5°-95° percentile (C7)."""
    rif = riferimento.dropna()
    if len(rif) < C.Z_MIN_VALORI:
        return pd.Series(np.nan, index=valori.index)
    lo, hi = np.percentile(rif, C.Z_ESTREMI)
    w = rif.clip(lo, hi)
    sd = w.std(ddof=1)
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(0.0, index=valori.index)
    return ((valori - w.mean()) / sd).clip(-C.Z_LIMITE, C.Z_LIMITE)


def _media_pesata(zeta: pd.DataFrame) -> pd.Series:
    """Media pesata delle z presenti; i pesi si riproporzionano sulle dimensioni che ci sono (C6)."""
    pesi = np.array([C.PESI_TPI[d.removeprefix("z_")] for d in zeta.columns])
    m = zeta.to_numpy(dtype=float)
    pres = ~np.isnan(m)
    somma = (pres * pesi).sum(axis=1)
    return pd.Series(np.where(somma > 0, np.nansum(m * pesi, axis=1) / np.where(somma > 0, somma, 1), np.nan),
                     index=zeta.index)


def _dimensioni(righe, senza, n_tot, k_mult, sos):
    """Le dimensioni di un giocatore in un contesto (righe = sue presenze, senza = partite della squadra senza di lui)."""
    n = len(righe)
    if n < C.CONTESTO_MIN_PRESENZE:
        return None
    minuti = righe["minuti"].sum()
    sos_ctx = righe["sos_avv"].mean()
    w_con = np.minimum(1.0 / righe["sos_avv"], C.BOOST_PESO_MAX)
    con = (w_con * righe["xg_fatti"]).sum() / w_con.sum()
    boost = np.nan
    if len(senza) >= C.BOOST_MIN_SENZA:
        w_s = np.minimum(1.0 / senza["avversario"].map(sos), C.BOOST_PESO_MAX)
        s = (w_s * senza["xg_fatti"]).sum() / w_s.sum()
        if con > 0 and s > 0:
            boost = float(np.exp(np.log(con / s) * len(senza) / (len(senza) + C.BOOST_K)))
    o = righe["out_partita"].to_numpy()
    m = o.mean()
    cons = m / (m + o.std(ddof=1)) if n >= C.CONSISTENZA_MIN_PRESENZE and m > 0 else np.nan
    return {"partite_ctx": n, "minuti_ctx": minuti,
            "output_raw": righe["xgxa"].sum() / minuti * 90 / sos_ctx,
            "buildup_raw": righe["xg_buildup"].sum() / minuti * 90 / sos_ctx,
            "xgxa_tot": righe["xgxa"].sum(), "xg_squadra": righe["xg_fatti"].sum(),
            "k_ctx": min(C.K_CENTRALITA * k_mult * n_tot / n, C.K_CENTRALITA * k_mult * C.K_CONTESTO_TETTO),
            "boost": boost, "consistenza": cons}


def _calcola(con, lega, stagione, fino_a_giornata=None):
    pg, cal, ruoli, nomi = _dati(con, lega, stagione, fino_a_giornata)
    ps = _partite_squadra(cal)
    sos = ps.groupby("squadra")["xg_concessi"].mean() / ps["xg_concessi"].mean()   # C12a
    prime6, forti = _squadre_di_riferimento(ps)
    giornate = int(cal["giornata"].max())

    pg = pg.merge(ps[["partita_id", "squadra", "xg_fatti"]], on=["partita_id", "squadra"], how="left")
    pg["sos_avv"] = pg["avversario"].map(sos)
    pg["xgxa"] = pg["xg_senza_rigori"] + pg["xa"]
    pg["out_partita"] = pg["xgxa"] / pg["minuti"] * 90.0
    pg = pg.sort_values(["giocatore_id", "giornata", "data"], kind="mergesort")

    # ---- qualificazione (C1-C3) ----
    agg = pg.groupby("giocatore_id").agg(minuti=("minuti", "sum"), partite=("minuti", "size"),
                                         prima_data=("data", "min"), prima_giornata=("giornata", "min"),
                                         squadra=("squadra", "last"))
    soglia = max(C.QUOTA_MINUTI * giornate * 90, float(np.percentile(agg["minuti"], C.PERCENTILE_MINUTI)))
    soglia_inv = float(np.floor(C.QUOTA_INVERNALI * giornate * 90))
    anno = int(cal["data"].min().year) + 1          # il gennaio della stagione
    inizio = pd.Timestamp(f"{anno}-{C.FINESTRA_INVERNALE[0]}")
    fine = pd.Timestamp(f"{anno}-{C.FINESTRA_INVERNALE[1]}") + pd.Timedelta(days=1)
    agg["invernale"] = (agg["prima_data"] >= inizio) & (agg["prima_data"] < fine)
    agg["qualificato"] = agg["minuti"] >= np.where(agg["invernale"], soglia_inv, soglia)

    ruoli = ruoli[ruoli["ruolo"].isin(C.PESO_RUOLO)]                 # portieri fuori (C4)
    q = agg[agg["qualificato"]].join(ruoli.set_index("giocatore_id")["ruolo"], how="inner")
    pq = pg[pg["giocatore_id"].isin(q.index)]
    min_medi = q["minuti"] / q["partite"]
    mult = np.maximum(np.minimum(C.MULT_K_MINUTI[0] / min_medi, C.MULT_K_MINUTI[1]),
                      np.minimum(C.MULT_K_PARTITE[0] / q["partite"], C.MULT_K_PARTITE[1]))
    q["k_output"] = C.K_OUTPUT * np.clip(mult, *C.MULT_K_LIMITI)

    # ---- finalizzazione e forma: una volta per stagione, uguali in tutti i contesti ----
    g = pq.groupby("giocatore_id")
    gol, xg = g["gol_senza_rigori"].sum(), g["xg_senza_rigori"].sum()
    q["finishing"] = np.where(xg > 0, (gol - xg) / np.sqrt(xg.where(xg > 0)), np.nan)
    forma = {}
    for gid, righe in pq.groupby("giocatore_id"):
        o = righe["out_partita"].to_numpy()
        e = o[0]
        for x in o[1:]:
            e = C.ALFA_FORMA * x + (1 - C.ALFA_FORMA) * e
        forma[gid] = e
    q["form"] = pd.Series(forma)

    # ---- dimensioni per contesto ----
    filtri = {
        "totale": lambda r, sq: pd.Series(True, index=r.index),
        "casa": lambda r, sq: r["lato"] == "casa",
        "trasferta": lambda r, sq: r["lato"] == "trasferta",
        "vs_top6": lambda r, sq: r["avversario"].isin(set(prime6) - {sq}),
        # regola del motore vecchio: se la sua squadra è fra le 6 difese più forti, entra la settima
        "vs_forti": lambda r, sq: r["avversario"].isin([s for s in forti if s != sq][:C.N_SQUADRE_FORTI]),
    }
    righe_ctx = []
    for gid, righe in pq.groupby("giocatore_id"):
        sq = q.at[gid, "squadra"]
        k_mult = C.FATTORE_K_INVERNALI if q.at[gid, "invernale"] else 1.0
        senza_tutte = ps[(ps["squadra"] == sq) & ~ps["partita_id"].isin(righe["partita_id"])]
        for ctx, f in filtri.items():
            mie, senza = righe[f(righe, sq)], senza_tutte[f(senza_tutte, sq)]
            d = _dimensioni(mie, senza, len(righe), k_mult, sos) or {}
            righe_ctx.append({"giocatore_id": gid, "contesto": ctx, "partite": len(mie), **d})
    ctx = pd.DataFrame(righe_ctx).merge(q[["ruolo", "k_output"]], left_on="giocatore_id", right_index=True)

    # shrinkage di output e buildup verso la media del ruolo nel contesto (C9, C9b)
    for dim in ("output", "buildup"):
        media = ctx.groupby(["contesto", "ruolo"])[f"{dim}_raw"].transform("mean")
        ctx[dim] = (ctx[f"{dim}_raw"] * ctx["minuti_ctx"] + media * ctx["k_output"]) / (ctx["minuti_ctx"] + ctx["k_output"])
    # centralità con il prior di ATT e CEN del contesto
    off = ctx[ctx["ruolo"].isin(["ATT", "CEN"])].groupby("contesto")[["xgxa_tot", "xg_squadra"]].sum()
    prior = ctx["contesto"].map(off["xgxa_tot"] / off["xg_squadra"])
    ctx["centralita"] = np.where(ctx["xg_squadra"] > 0,
                                 (ctx["xgxa_tot"] + prior * ctx["k_ctx"]) / (ctx["xg_squadra"] + ctx["k_ctx"]) * 100, np.nan)

    # ---- z dentro il ruolo (C7); nei contesti con meno di 6 valori nel ruolo si usa il totale (C13) ----
    tot = ctx[ctx["contesto"] == "totale"].set_index("giocatore_id")
    for dim in DIM_STAGIONE:
        q[f"z_{dim}"] = q.groupby("ruolo")[dim].transform(lambda s: _z(s, s))
    for dim in DIM_CONTESTO:
        ctx[f"z_{dim}"] = np.nan
        for (nome_ctx, ruolo), blocco in ctx.groupby(["contesto", "ruolo"]):
            rif = blocco[dim]
            if nome_ctx != "totale" and rif.notna().sum() < C.Z_MIN_RUOLO_CONTESTO:
                rif = tot.loc[tot["ruolo"] == ruolo, dim]
            ctx.loc[blocco.index, f"z_{dim}"] = _z(blocco[dim], rif)
    for dim in DIM_STAGIONE:
        ctx[f"z_{dim}"] = ctx["giocatore_id"].map(q[f"z_{dim}"])
    ctx["media_pesata"] = _media_pesata(ctx[[f"z_{d}" for d in DIMENSIONI]])
    # sotto le 4 presenze il contesto non esiste, neanche nella media del ruolo (decisione Q-C2 = B)
    ctx.loc[ctx["partite"] < C.CONTESTO_MIN_PRESENZE, "media_pesata"] = np.nan

    # ---- confidenza (C10b), dal contesto totale ----
    p95 = float(np.percentile(q["minuti"], C.CONF_PERCENTILE_MINUTI))
    f1 = np.minimum(q["minuti"] / p95, 1.0)
    f2 = np.clip(q["partite"] / C.CONF_PARTITE[0], C.CONF_PARTITE[1], 1.0)
    f3 = np.clip(min_medi / 90.0, C.CONF_MINUTI_PARTITA_MIN, 1.0)
    f4 = tot[DIM_CONTESTO].notna().sum(axis=1) / len(DIM_CONTESTO)
    q["confidenza"] = ((f1 * f2 * f3 * f4) ** 0.25).round(3)

    # ---- disponibilità (C12b) ----
    disp_partite = np.where(q["invernale"], giornate - q["prima_giornata"] + 1, giornate)
    q["disponibilita"] = q["partite"] / disp_partite
    pen = C.DISP_PENALITA + (q["disponibilita"] - C.DISP_BASSA) / (C.DISP_PIENA - C.DISP_BASSA) * (1 - C.DISP_PENALITA)
    q["penalita_disponibilita"] = np.clip(pen, C.DISP_PENALITA, 1.0)

    # ---- TPI di ogni contesto (C12c): riporto verso la media del ruolo -> peso del ruolo -> disponibilità ----
    media_r = ctx.groupby(["contesto", "ruolo"])["media_pesata"].transform("mean")
    conf = ctx["giocatore_id"].map(q["confidenza"])
    riportato = media_r + (C.CONF_MINIMO + (1 - C.CONF_MINIMO) * conf) * (ctx["media_pesata"] - media_r)
    ctx["tpi"] = riportato * ctx["ruolo"].map(C.PESO_RUOLO) * ctx["giocatore_id"].map(q["penalita_disponibilita"])

    tot = ctx[ctx["contesto"] == "totale"].set_index("giocatore_id")
    q["tpi"] = tot["tpi"]
    for dim in DIM_CONTESTO:
        q[dim], q[f"z_{dim}"] = tot[dim], tot[f"z_{dim}"]
    q = q.rename_axis("giocatore_id").reset_index().merge(nomi, on="giocatore_id", how="left")
    q.attrs.update({"soglia_minuti": soglia, "soglia_invernali": soglia_inv, "prime6": prime6, "forti": forti,
                    "esclusi_senza_ruolo": int(agg["qualificato"].sum() - len(q))})
    colonne = ["giocatore_id", "nome", "ruolo", "squadra", "tpi", "confidenza", "penalita_disponibilita",
               *[f"z_{d}" for d in DIMENSIONI], "minuti", "partite", "invernale", "disponibilita", *DIMENSIONI]
    classifica = q[colonne].sort_values("tpi", ascending=False, kind="mergesort").reset_index(drop=True)
    return classifica, ctx[["giocatore_id", "contesto", "partite", "tpi"]]


def classifica(con, lega, stagione, fino_a_giornata=None) -> pd.DataFrame:
    return _calcola(con, lega, stagione, fino_a_giornata)[0]


def contesti(con, lega, stagione, fino_a_giornata=None) -> pd.DataFrame:
    return _calcola(con, lega, stagione, fino_a_giornata)[1]
