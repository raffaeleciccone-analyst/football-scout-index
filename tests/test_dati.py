"""Fase 5 — dati: controlli (C25), raccolta (C26), il nuovo non scrive mai nei database vecchi (C27)."""
import re
from pathlib import Path

import pandas as pd
import pytest

from fsi import config, controlli, db, raccolta

CACHE = Path(__file__).parent / "fixtures" / "understat"
# difetti noti nei dati veri: quando spariscono (partita reimportata), il test diventa rosso e chiede di toglierli
DIFETTI_NOTI = {("D10", "serie_a", "2026-27", "Juventus")}


def _difetti(con, **kw):
    return {(d["regola"], d["lega"], d["stagione"], d.get("squadra")) for d in controlli.controlla(con, **kw) if d["grave"]}


# ---- C25: le regole dei dati puliti ----
def test_c25_i_grezzi_puliti_non_hanno_difetti(con):
    assert _difetti(con) == set()


def test_c25_squadra_tutta_a_xg_zero_ferma_la_pubblicazione(con):
    pid, sq = con.execute("SELECT partita_id, casa FROM partite WHERE xg_casa > 0.3 LIMIT 1").fetchone()
    con.execute("UPDATE righe SET xg = 0, xg_senza_rigori = 0, xa = 0 WHERE partita_id = ? AND squadra = ?", (pid, sq))
    assert ("D10", "serie_a", "2025-26", sq) in _difetti(con)


def test_c25_valori_impossibili(con):
    con.execute("UPDATE righe SET minuti = 140 WHERE rowid = (SELECT MIN(rowid) FROM righe)")
    con.execute("UPDATE righe SET gol_senza_rigori = gol + 1 WHERE rowid = (SELECT MAX(rowid) FROM righe)")
    regole = {r for r, *_ in _difetti(con)}
    assert "D4" in regole


def test_c25_partita_con_una_squadra_sola(con):
    pid, sq = con.execute("SELECT partita_id, trasferta FROM partite LIMIT 1").fetchone()
    con.execute("DELETE FROM righe WHERE partita_id = ? AND squadra = ?", (pid, sq))
    assert "D6" in {r for r, *_ in _difetti(con)}


def test_c25_infortunio_aperto_ma_ha_giocato_dopo(con):
    gid = con.execute("SELECT giocatore_id FROM righe r JOIN partite p USING (lega, partita_id) "
                      "WHERE p.data > '2026-03-01' LIMIT 1").fetchone()[0]
    con.execute("INSERT INTO infortuni VALUES (?, '2025-26', '2026-03-01', NULL, NULL, 'prova')", (gid,))
    assert "D13" in {r for r, *_ in _difetti(con, stagione_in_corso="2026-27")}


def test_c25_infortunio_ancora_in_corso_non_e_un_difetto(con):
    con.execute("INSERT INTO infortuni VALUES (1, '2025-26', '2026-03-01', NULL, NULL, 'ancora fuori')")
    assert "D13" not in {r for r, *_ in _difetti(con, stagione_in_corso="2026-27")}


def test_c25_i_database_veri_hanno_solo_i_difetti_noti():
    if not config.DB.exists():
        pytest.skip("database vero assente")
    con = db.apri()
    assert _difetti(con, stagione_in_corso="2026-27") == DIFETTI_NOTI


# ---- C26: la raccolta ridà le righe del database di oggi ----
def test_c26_la_raccolta_ridà_le_righe_di_oggi(tmp_path):
    if not config.DB.exists():
        pytest.skip("database vero assente (serve il confronto)")
    nuovo = db.apri(tmp_path / "raccolta.sqlite")
    n = sum(raccolta.importa_cartella(nuovo, CACHE, lega, "2026-27") for lega in config.LEGHE)
    assert n == 170
    cols = ["minuti", "gol", "gol_senza_rigori", "assist", "tiri", "xg", "xg_senza_rigori", "xa", "xg_buildup", "xg_chain"]
    chiave = ["lega", "partita_id", "giocatore_id"]
    a = pd.read_sql("SELECT * FROM righe", nuovo).set_index(chiave)[cols]
    b = pd.read_sql("SELECT * FROM righe WHERE stagione = '2026-27'", db.apri()).set_index(chiave)[cols]
    comuni = a.index.intersection(b.index)
    assert len(comuni) >= 0.95 * len(a), f"solo {len(comuni)} righe su {len(a)} trovate nel database di oggi"
    # il motore vecchio arrotondava gli xG a 2 decimali (SPEC_DATI P2): ±0,005; l'xG senza rigori era la differenza
    # di due valori arrotondati: ±0,01
    scarto = (a.loc[comuni] - b.loc[comuni]).abs().max()
    tolleranza = pd.Series(0.0055, index=cols)
    tolleranza["xg_senza_rigori"] = 0.0105
    assert (scarto <= tolleranza).all(), scarto[scarto > tolleranza]


def test_c26_rigori_tolti_dai_tiri():
    righe = raccolta.leggi_partita(CACHE / "match_31180.json", {"h": "Arsenal", "a": "Coventry"}, "premier", "2026-27")
    for r in righe:
        assert r["gol_senza_rigori"] <= r["gol"] and r["xg_senza_rigori"] <= r["xg"] + 1e-9


# ---- C27: mai scrivere nei database vecchi ----
def test_c27_il_ponte_legge_soltanto():
    sorgente = (Path(raccolta.__file__).parent / "ponte.py").read_text(encoding="utf-8")
    query = re.findall(r'_leggi\(vecchio,\s*"([^"]+)"', sorgente)
    assert query and all(q.strip().upper().startswith("SELECT") for q in query)
    assert "vecchio.commit" not in sorgente and "vecchio.cursor" not in sorgente
