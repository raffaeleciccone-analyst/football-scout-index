"""Raccolta da Understat (SPEC F21, C26): dai file JSON delle partite al database nuovo.

soccerdata scarica e salva una pagina JSON per partita (cartella ~/soccerdata/data/Understat): qui si leggono quei
file e si riempiono `partite` e `righe` nello stesso formato del ponte. I rigori non sono nelle righe dei giocatori:
si tolgono guardando i tiri (situation = "Penalty"), come faceva il motore vecchio.
Uso: python -m fsi.raccolta lega stagione   (es. serie_a 2026-27; scarica con soccerdata, poi importa)
"""
import json
import sys
from pathlib import Path

from fsi import db

CODICE = {"serie_a": ("2", "ITA-Serie A"), "premier": ("1", "ENG-Premier League")}   # numero del campionato su Understat
CACHE = Path.home() / "soccerdata" / "data" / "Understat"


def _anno(stagione):
    return stagione[:4]


def leggi_lega(cartella, lega, stagione) -> dict:
    """Le partite giocate della stagione: id -> squadre, data, gol, xG (dal file della stagione)."""
    d = json.loads((Path(cartella) / f"league_{CODICE[lega][0]}_season_{_anno(stagione)}.json").read_text(encoding="utf-8"))
    return {int(p["id"]): {"h": p["h"]["title"], "a": p["a"]["title"], "data": p["datetime"],
                           "gol_h": int(p["goals"]["h"]), "gol_a": int(p["goals"]["a"]),
                           "xg_h": float(p["xG"]["h"]), "xg_a": float(p["xG"]["a"])}
            for p in d["dates"] if p.get("isResult")}


def leggi_partita(percorso, info, lega, stagione) -> list[dict]:
    d = json.loads(Path(percorso).read_text(encoding="utf-8"))
    rigori = {}
    for lato in ("h", "a"):
        for s in d["shots"][lato]:
            if s.get("situation") == "Penalty":
                g = rigori.setdefault(s["player_id"], [0, 0.0])
                g[0] += s["result"] == "Goal"
                g[1] += float(s["xG"])
    righe = []
    for lato in ("h", "a"):
        for p in d["rosters"][lato].values():
            gol_r, xg_r = rigori.get(p["player_id"], [0, 0.0])
            xg = float(p["xG"])
            righe.append({"lega": lega, "stagione": stagione, "partita_id": int(Path(percorso).stem.split("_")[1]),
                          "giocatore_id": int(p["player_id"]), "squadra": info[lato], "avversario": info["a" if lato == "h" else "h"],
                          "lato": "casa" if lato == "h" else "trasferta", "minuti": int(p["time"]),
                          "gol": int(p["goals"]), "gol_senza_rigori": int(p["goals"]) - gol_r, "assist": int(p["assists"]),
                          "tiri": int(p["shots"]), "xg": round(xg, 3), "xg_senza_rigori": round(max(0.0, xg - xg_r), 3),
                          "xa": round(float(p["xA"]), 3), "xg_buildup": round(float(p["xGBuildup"]), 3),
                          "xg_chain": round(float(p["xGChain"]), 3), "nome": p["player"]})
    return righe


def importa_cartella(con, cartella, lega, stagione) -> int:
    """Importa ogni partita giocata che ha il suo file nella cartella. Rilanciarla riscrive le stesse partite."""
    partite = leggi_lega(cartella, lega, stagione)
    n = 0
    for pid, info in sorted(partite.items()):
        f = Path(cartella) / f"match_{pid}.json"
        if not f.exists():
            continue
        righe = leggi_partita(f, info, lega, stagione)
        # shortcut: la giornata è l'ordine della partita per la squadra di casa; il motore vecchio la ricavava
        # dal calendario ufficiale (deriva_giornata.py). Con i rinvii può sbagliare di una: da rifare quando torna Understat.
        giornata = 1 + sum(1 for q, i in partite.items() if i["data"] < info["data"] and info["h"] in (i["h"], i["a"]))
        con.execute("DELETE FROM righe WHERE lega = ? AND partita_id = ?", (lega, pid))
        con.execute("INSERT OR REPLACE INTO partite VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (lega, stagione, pid, giornata, info["data"], info["h"], info["a"], info["gol_h"], info["gol_a"],
                     info["xg_h"], info["xg_a"]))
        con.executemany("INSERT INTO righe (lega, stagione, partita_id, giocatore_id, squadra, avversario, lato, minuti, gol, "
                        "gol_senza_rigori, assist, tiri, xg, xg_senza_rigori, xa, xg_buildup, xg_chain) "
                        "VALUES (:lega, :stagione, :partita_id, :giocatore_id, :squadra, :avversario, :lato, :minuti, :gol, "
                        ":gol_senza_rigori, :assist, :tiri, :xg, :xg_senza_rigori, :xa, :xg_buildup, :xg_chain)", righe)
        con.executemany("INSERT OR IGNORE INTO giocatori (giocatore_id, nome) VALUES (?, ?)",
                        [(r["giocatore_id"], r["nome"]) for r in righe])
        n += 1
    con.commit()
    return n


def scarica(lega, stagione):
    """Scarica la stagione con soccerdata (salva i JSON in ~/soccerdata), poi si importa la cartella."""
    import soccerdata
    soccerdata.Understat(leagues=CODICE[lega][1], seasons=_anno(stagione)).read_player_match_stats()


if __name__ == "__main__":
    lega, stagione = sys.argv[1], sys.argv[2]
    scarica(lega, stagione)
    print(importa_cartella(db.apri(), CACHE, lega, stagione), "partite importate")
