"""Ponte: copia dal MySQL del motore vecchio al database nuovo, in sola lettura (PIANO §2, SPEC F22-F23).

Si cancella al cambio (SPEC F24), quando la raccolta riempie il database da sola.
Uso: python -m fsi.ponte
"""
import json
import os
from pathlib import Path

import pandas as pd
import pymysql
from dotenv import load_dotenv

from fsi import config, db

MOTORE = Path(r"C:\dev\football-index-engine")
# cartella dei payload del motore vecchio per lega (servono solo per i ruoli, vedi _ruoli_pubblicati)
PAYLOAD = {"serie_a": MOTORE / "dashboard_output", "premier": MOTORE / "dashboard_output_eng"}


def _mysql(nome_db):
    load_dotenv(MOTORE / ".env")
    return pymysql.connect(host=os.environ.get("DB_HOST", "localhost"), user=os.environ["DB_USER"],
                           password=os.environ["DB_PASSWORD"], database=nome_db)


def _leggi(con, sql):
    with con.cursor() as cur:
        cur.execute(sql)
        nomi = [c[0] for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=nomi)


def _ruoli_pubblicati(lega) -> dict[tuple[str, int], str]:
    """(stagione, id vecchio) -> ruolo, dal payload più completo di ogni stagione.

    shortcut: il ruolo vero viene dalle posizioni Understat partita per partita, che il MySQL non ha
    (stavano solo nella cache di soccerdata, ripulita a ogni giro). Fino alla raccolta nuova si usa il
    ruolo pubblicato dal motore vecchio, e per chi non era in classifica quello dell'anagrafica.
    """
    migliore: dict[str, list] = {}
    for f in PAYLOAD[lega].glob("payload*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(d, dict) or not d.get("stagione") or not isinstance(d.get("players"), list):
            continue
        if len(d["players"]) > len(migliore.get(d["stagione"], [])):
            migliore[d["stagione"]] = d["players"]
    return {(st, int(p["id"])): p["ruolo"] for st, ps in migliore.items() for p in ps if p.get("ruolo")}


def copia(lega: str, con_nuovo) -> dict[str, int]:
    vecchio = _mysql(config.LEGHE[lega])
    try:
        squadre = _leggi(vecchio, "SELECT id, nome FROM squadre").set_index("id")["nome"]
        cal = _leggi(vecchio, "SELECT * FROM calendario")
        gp = _leggi(vecchio, "SELECT * FROM giocatore_partita")
        gioc = _leggi(vecchio, "SELECT id, nome, cognome, ruolo, data_nascita, understat_id FROM giocatori")
        inf = _leggi(vecchio, "SELECT * FROM t_infortuni")
    finally:
        vecchio.close()

    uid = gioc.set_index("id")["understat_id"]
    if gp["giocatore_id"].map(uid).isna().any():
        raise ValueError(f"{lega}: righe di giocatori senza id Understat, il ponte non può continuare")

    partite = pd.DataFrame({
        "lega": lega, "stagione": cal["season"], "partita_id": cal["game_id_understat"].astype(int),
        "giornata": cal["giornata"], "data": cal["data"].astype(str),
        "casa": cal["squadra_casa_id"].map(squadre), "trasferta": cal["squadra_trasferta_id"].map(squadre),
        "gol_casa": cal["goal_casa"], "gol_trasferta": cal["goal_trasferta"],
        "xg_casa": cal["xg_casa"], "xg_trasferta": cal["xg_trasferta"]})
    c = cal.set_index("id")
    in_casa = gp["ruolo"] == "casa"
    casa = gp["calendario_id"].map(c["squadra_casa_id"]).map(squadre)
    trasf = gp["calendario_id"].map(c["squadra_trasferta_id"]).map(squadre)
    righe = pd.DataFrame({
        "lega": lega, "stagione": gp["season"], "partita_id": gp["calendario_id"].map(c["game_id_understat"]).astype(int),
        "giocatore_id": gp["giocatore_id"].map(uid).astype(int),
        "squadra": casa.where(in_casa, trasf), "avversario": trasf.where(in_casa, casa),
        "lato": gp["ruolo"], "minuti": gp["minuti"], "gol": gp["goal"], "gol_senza_rigori": gp["npg"],
        "assist": gp["assist"], "tiri": gp["tiri"], "xg": gp["xg"], "xg_senza_rigori": gp["npxg"],
        "xa": gp["xa"], "xg_buildup": gp["xg_buildup"], "xg_chain": gp["xg_chain"]})

    usati = gioc[gioc["id"].isin(gp["giocatore_id"])]
    giocatori = pd.DataFrame({
        "giocatore_id": usati["understat_id"].astype(int),
        "nome": (usati["nome"].fillna("") + " " + usati["cognome"].fillna("")).str.strip(),
        "data_nascita": usati["data_nascita"].astype("string")})

    pubblicati = _ruoli_pubblicati(lega)
    anagrafica = gioc.set_index("id")["ruolo"]
    ruoli = []
    for (stagione, gid_vecchio) in gp[["season", "giocatore_id"]].drop_duplicates().itertuples(index=False):
        ruolo, fonte = pubblicati.get((stagione, int(gid_vecchio))), "motore vecchio"
        if ruolo is None:
            ruolo, fonte = anagrafica.get(gid_vecchio), "anagrafica"
        if ruolo in ("POR", "DIF", "CEN", "ATT"):
            ruoli.append((lega, stagione, int(uid[gid_vecchio]), ruolo, fonte))

    infortuni = pd.DataFrame({
        "giocatore_id": inf["giocatore_id"].map(uid), "stagione": inf["stagione"],
        "inizio": inf["data_inizio"].astype(str), "rientro": inf["data_rientro"].astype("string"),
        "giorni_fuori": inf["giorni_out"], "tipo": inf["tipo"]}).dropna(subset=["giocatore_id"])
    infortuni["giocatore_id"] = infortuni["giocatore_id"].astype(int)

    con_nuovo.execute("DELETE FROM partite WHERE lega = ?", (lega,))
    con_nuovo.execute("DELETE FROM righe WHERE lega = ?", (lega,))
    con_nuovo.execute("DELETE FROM ruoli WHERE lega = ?", (lega,))
    partite.to_sql("partite", con_nuovo, if_exists="append", index=False)
    righe.to_sql("righe", con_nuovo, if_exists="append", index=False)
    con_nuovo.executemany("INSERT OR REPLACE INTO ruoli VALUES (?, ?, ?, ?, ?)", ruoli)
    # un giocatore può stare in tutte e due le leghe: si tiene una riga sola, la data di nascita nota vince
    for r in giocatori.itertuples(index=False):
        con_nuovo.execute("INSERT INTO giocatori VALUES (?, ?, ?) ON CONFLICT(giocatore_id) DO UPDATE SET "
                          "data_nascita = COALESCE(giocatori.data_nascita, excluded.data_nascita)",
                          (r.giocatore_id, r.nome, None if pd.isna(r.data_nascita) else r.data_nascita))
    con_nuovo.executemany("INSERT OR REPLACE INTO infortuni VALUES (?, ?, ?, ?, ?, ?)",
                          [tuple(None if pd.isna(v) else v for v in r) for r in infortuni.itertuples(index=False)])
    con_nuovo.execute("CREATE TABLE IF NOT EXISTS id_vecchi (lega TEXT, id_vecchio INTEGER, giocatore_id INTEGER, "
                      "PRIMARY KEY (lega, id_vecchio))")
    con_nuovo.executemany("INSERT OR REPLACE INTO id_vecchi VALUES (?, ?, ?)",
                          [(lega, int(i), int(u)) for i, u in uid.dropna().items()])
    con_nuovo.commit()
    return {"partite": len(partite), "righe": len(righe), "giocatori": len(giocatori),
            "ruoli": len(ruoli), "infortuni": len(infortuni)}


if __name__ == "__main__":
    config.DB.parent.mkdir(exist_ok=True)
    con = db.apri()
    for lega in config.LEGHE:
        print(lega, copia(lega, con))
