"""Le regole dei dati puliti (SPEC C25, dalle D1-D13 di SPEC_DATI del motore vecchio, sullo schema nuovo).

Un difetto grave ferma la pubblicazione (uscita 1); gli avvisi si elencano e basta.
Uso: python -m fsi.controlli [stagione_in_corso]
"""
import sys

from fsi import db

# (regola, grave, cosa controlla, query: righe = un difetto ciascuna, con colonne lega, stagione, squadra, n)
REGOLE = [
    ("D1", True, "un giocatore in tutte e due le squadre della stessa partita",
     "SELECT lega, stagione, NULL squadra, COUNT(*) n FROM (SELECT lega, stagione, partita_id, giocatore_id FROM righe "
     "GROUP BY 1, 2, 3, 4 HAVING COUNT(DISTINCT squadra) > 1) GROUP BY 1, 2"),
    ("D2", True, "righe che puntano a una partita che non esiste",
     "SELECT r.lega, r.stagione, NULL, COUNT(*) FROM righe r LEFT JOIN partite p USING (lega, partita_id) "
     "WHERE p.partita_id IS NULL GROUP BY 1, 2"),
    ("D4", True, "valori impossibili (minuti fuori 0-130, xG negativi, senza rigori più del totale, numeri a 0 minuti)",
     "SELECT lega, stagione, NULL, COUNT(*) FROM righe WHERE minuti < 0 OR minuti > 130 "
     "OR COALESCE(xg, 0) < 0 OR COALESCE(xa, 0) < 0 OR COALESCE(xg_senza_rigori, 0) < 0 "
     "OR xg_senza_rigori > xg + 1e-6 OR gol_senza_rigori > gol "
     "OR (minuti = 0 AND (COALESCE(gol, 0) > 0 OR COALESCE(xg, 0) > 0 OR COALESCE(xa, 0) > 0)) GROUP BY 1, 2"),
    ("D5", True, "riga con una stagione diversa da quella della partita",
     "SELECT r.lega, r.stagione, NULL, COUNT(*) FROM righe r JOIN partite p USING (lega, partita_id) "
     "WHERE r.stagione <> p.stagione GROUP BY 1, 2"),
    ("D6", True, "partita giocata con i minuti di una squadra sola",
     "SELECT lega, stagione, NULL, COUNT(*) FROM (SELECT p.lega, p.stagione, p.partita_id FROM partite p "
     "JOIN righe r USING (lega, partita_id) WHERE r.minuti > 0 GROUP BY 1, 2, 3 HAVING COUNT(DISTINCT r.squadra) < 2) GROUP BY 1, 2"),
    ("D7", True, "squadra con meno di 11 o più di 18 giocatori in campo",
     "SELECT lega, stagione, squadra, COUNT(*) FROM (SELECT lega, stagione, partita_id, squadra FROM righe WHERE minuti > 0 "
     "GROUP BY 1, 2, 3, 4 HAVING COUNT(*) < 11 OR COUNT(*) > 18) GROUP BY 1, 2, 3"),
    ("D9", True, "i gol dei giocatori superano quelli della squadra",
     "SELECT r.lega, r.stagione, r.squadra, COUNT(*) FROM (SELECT lega, stagione, partita_id, squadra, lato, SUM(gol) g "
     "FROM righe GROUP BY 1, 2, 3, 4, 5) r JOIN partite p USING (lega, partita_id) "
     "WHERE r.g > CASE r.lato WHEN 'casa' THEN p.gol_casa ELSE p.gol_trasferta END GROUP BY 1, 2, 3"),
    ("D10", True, "squadra con più di 0,3 xG ma tutti i giocatori a xG zero",
     "SELECT r.lega, r.stagione, r.squadra, COUNT(*) FROM (SELECT lega, stagione, partita_id, squadra, lato, "
     "SUM(COALESCE(xg, xg_senza_rigori)) x FROM righe GROUP BY 1, 2, 3, 4, 5) r JOIN partite p USING (lega, partita_id) "
     "WHERE r.x = 0 AND CASE r.lato WHEN 'casa' THEN p.xg_casa ELSE p.xg_trasferta END > 0.3 GROUP BY 1, 2, 3"),
    ("D11", False, "somma degli xG dei giocatori lontana più di 0,3 da quella della squadra (avviso)",
     "SELECT r.lega, r.stagione, NULL, COUNT(*) FROM (SELECT lega, stagione, partita_id, lato, SUM(xg) x FROM righe "
     "WHERE xg IS NOT NULL GROUP BY 1, 2, 3, 4) r JOIN partite p USING (lega, partita_id) "
     "WHERE ABS(r.x - CASE r.lato WHEN 'casa' THEN p.xg_casa ELSE p.xg_trasferta END) > 0.3 GROUP BY 1, 2"),
]
# D3 (una riga per giocatore e partita) e D12 (un infortunio per giocatore e data) li garantisce lo schema (chiavi).
# D8 del vecchio (righe in squadra_calendario) non esiste più: lo schema nuovo non ha quella tabella.


def controlla(con, stagione_in_corso=None) -> list[dict]:
    esiti = []
    for regola, grave, cosa, sql in REGOLE:
        for lega, stagione, squadra, n in con.execute(sql).fetchall():
            esiti.append({"regola": regola, "grave": grave, "cosa": cosa, "lega": lega, "stagione": stagione,
                          "squadra": squadra, "n": n})
    if stagione_in_corso:
        # D13 (precisata il 22/11): con la storia di Transfermarkt un infortunio della stagione scorsa può essere ancora
        # in corso (es. Fabianski, 430 giorni). È un difetto solo se il giocatore ha giocato dopo l'inizio: è rientrato
        # e manca la data.
        sql = ("SELECT i.stagione, COUNT(DISTINCT i.giocatore_id || i.inizio) FROM infortuni i "
               "JOIN righe r USING (giocatore_id) JOIN partite p ON p.lega = r.lega AND p.partita_id = r.partita_id "
               "WHERE i.rientro IS NULL AND i.stagione < ? AND r.minuti > 0 AND p.data > i.inizio GROUP BY 1")
        for stagione, n in con.execute(sql, (stagione_in_corso,)):
            esiti.append({"regola": "D13", "grave": True, "cosa": "infortunio senza rientro ma il giocatore ha giocato dopo",
                          "lega": None, "stagione": stagione, "squadra": None, "n": n})
    return esiti


if __name__ == "__main__":
    esiti = controlla(db.apri(), sys.argv[1] if len(sys.argv) > 1 else None)
    for e in esiti:
        print(("DIFETTO" if e["grave"] else "avviso "), e["regola"], e["lega"], e["stagione"], e["squadra"] or "", e["n"], "-", e["cosa"])
    sys.exit(1 if any(e["grave"] for e in esiti) else 0)
