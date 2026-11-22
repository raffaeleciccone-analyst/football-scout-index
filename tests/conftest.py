"""Database di prova costruito dai grezzi Serie A 2025-26 (gli stessi della ricostruzione alla cieca)."""
import json
from pathlib import Path

import pandas as pd
import pytest

from fsi import db

FIXTURES = Path(__file__).parent / "fixtures"
GREZZI = FIXTURES / "grezzi_serie_a_2025-26"


def riempi_da_grezzi(con, lega="serie_a", stagione="2025-26"):
    cal = pd.read_csv(GREZZI / "calendario.csv")
    pg = pd.read_csv(GREZZI / "partite_giocatori.csv")
    squadre = pd.read_csv(GREZZI / "squadre.csv")
    nomi = dict(zip(squadre.iloc[:, 0], squadre.iloc[:, 1].astype(str)))
    pd.DataFrame({
        "lega": lega, "stagione": stagione, "partita_id": cal["calendario_id"], "giornata": cal["giornata"],
        "data": cal["data"], "casa": cal["squadra_casa_id"].map(nomi), "trasferta": cal["squadra_trasferta_id"].map(nomi),
        "gol_casa": cal["goal_casa"], "gol_trasferta": cal["goal_trasferta"],
        "xg_casa": cal["xg_casa"], "xg_trasferta": cal["xg_trasferta"],
    }).to_sql("partite", con, if_exists="append", index=False)
    pd.DataFrame({
        "lega": lega, "stagione": stagione, "partita_id": pg["calendario_id"], "giocatore_id": pg["giocatore_id"],
        "squadra": pg["squadra_id"].map(nomi), "avversario": pg["avversario_id"].map(nomi),
        "lato": pg["casa_o_trasferta"], "minuti": pg["minuti"], "gol": pg["goal"],
        "gol_senza_rigori": pg["gol_senza_rigori"], "xg_senza_rigori": pg["xg_senza_rigori"],
        "xa": pg["xa"], "xg_buildup": pg["xg_buildup"],
    }).to_sql("righe", con, if_exists="append", index=False)
    ruoli = pd.read_csv(GREZZI / "ruoli.csv")
    con.executemany("INSERT INTO ruoli VALUES (?, ?, ?, ?, 'fotografia')",
                    [(lega, stagione, int(g), r) for g, r in zip(ruoli["giocatore_id"], ruoli["ruolo"])])
    gioc = pd.read_csv(GREZZI / "giocatori.csv")
    con.executemany("INSERT INTO giocatori (giocatore_id, nome) VALUES (?, ?)",
                    [(int(g), str(n)) for g, n in zip(gioc["giocatore_id"], gioc["nome"])])
    con.commit()


@pytest.fixture
def con(tmp_path):
    c = db.apri(tmp_path / "prova.sqlite")
    riempi_da_grezzi(c)
    yield c
    c.close()


@pytest.fixture(scope="session")
def fotografia():
    d = json.loads((FIXTURES / "fotografia_serie_a_2025-26.json").read_text(encoding="utf-8"))
    foto = pd.DataFrame(d["giocatori"]).set_index("id")
    foto["tpi"] = foto["tpi"].map(lambda t: t["totale"])
    return foto


@pytest.fixture(scope="session")
def contesti_vecchi():
    return json.loads((FIXTURES / "contesti_serie_a_2025-26.json").read_text(encoding="utf-8"))["giocatori"]
