"""Il database nuovo: la porta d'ingresso (PIANO §2). Tutto il calcolo legge da qui."""
import sqlite3

import pandas as pd

from fsi import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS partite (
    lega TEXT NOT NULL, stagione TEXT NOT NULL, partita_id INTEGER NOT NULL,
    giornata INTEGER NOT NULL, data TEXT NOT NULL,
    casa TEXT NOT NULL, trasferta TEXT NOT NULL,
    gol_casa INTEGER, gol_trasferta INTEGER, xg_casa REAL, xg_trasferta REAL,
    PRIMARY KEY (lega, partita_id));
CREATE TABLE IF NOT EXISTS righe (
    lega TEXT NOT NULL, stagione TEXT NOT NULL, partita_id INTEGER NOT NULL,
    giocatore_id INTEGER NOT NULL, squadra TEXT NOT NULL, avversario TEXT NOT NULL,
    lato TEXT NOT NULL CHECK (lato IN ('casa', 'trasferta')),
    minuti INTEGER NOT NULL, gol INTEGER, gol_senza_rigori INTEGER, assist INTEGER, tiri INTEGER,
    xg REAL, xg_senza_rigori REAL, xa REAL, xg_buildup REAL, xg_chain REAL,
    PRIMARY KEY (lega, partita_id, giocatore_id));
CREATE TABLE IF NOT EXISTS giocatori (
    giocatore_id INTEGER PRIMARY KEY, nome TEXT NOT NULL, data_nascita TEXT, tm_id INTEGER);
CREATE TABLE IF NOT EXISTS ruoli (
    lega TEXT NOT NULL, stagione TEXT NOT NULL, giocatore_id INTEGER NOT NULL,
    ruolo TEXT NOT NULL CHECK (ruolo IN ('POR', 'DIF', 'CEN', 'ATT')), fonte TEXT NOT NULL,
    PRIMARY KEY (lega, stagione, giocatore_id));
CREATE TABLE IF NOT EXISTS stagioni_riassunte (
    lega TEXT NOT NULL, stagione TEXT NOT NULL, giocatore_id INTEGER NOT NULL, nome TEXT, squadra TEXT, ruolo TEXT,
    partite INTEGER, minuti INTEGER, gol INTEGER, gol_senza_rigori INTEGER, assist INTEGER,
    xg REAL, xg_senza_rigori REAL, xa REAL, xg_buildup REAL, xg_chain REAL, fonte TEXT NOT NULL,
    PRIMARY KEY (lega, stagione, giocatore_id));
CREATE TABLE IF NOT EXISTS infortuni (
    giocatore_id INTEGER NOT NULL, stagione TEXT NOT NULL, inizio TEXT NOT NULL,
    rientro TEXT, giorni_fuori INTEGER, tipo TEXT,
    PRIMARY KEY (giocatore_id, inizio));
CREATE TABLE IF NOT EXISTS infortuni_scaricati (
    giocatore_id INTEGER PRIMARY KEY, tm_id INTEGER NOT NULL, scaricato_il TEXT NOT NULL);
"""


def apri(percorso=None) -> sqlite3.Connection:
    con = sqlite3.connect(percorso or config.DB)
    con.executescript(SCHEMA)
    return con


def righe(con, lega: str, stagione: str, fino_a_giornata: int | None = None) -> pd.DataFrame:
    """L'unica lettura delle righe partita per partita: sempre UNA lega e UNA stagione (SPEC C2, C4)."""
    sql = ("SELECT r.*, p.giornata, p.data FROM righe r JOIN partite p USING (lega, partita_id) "
           "WHERE r.lega = ? AND r.stagione = ? AND p.stagione = ?")
    parametri = [lega, stagione, stagione]
    if fino_a_giornata is not None:
        sql += " AND p.giornata <= ?"
        parametri.append(fino_a_giornata)
    return pd.read_sql(sql, con, params=parametri)

