"""Stagioni riassunte dall'Internet Archive: i totali di stagione di Understat salvati prima della manutenzione.

Riempitore PROVVISORIO (PIANO §2): serve solo alla prova del modello (stima su 2023-24 -> 2024-25). Il TPI e il sito
non leggono questa tabella. Quando Understat torna, la raccolta scarica la stagione partita per partita.
Uso: python -m fsi.archivio
"""
import codecs
import json
import re
import urllib.request

from fsi import config, db

# copie complete a stagione finita (controllate il 22/11/2026: 380 partite, ~580 giocatori)
# Serie A 2022-23: l'archivio ha solo copie fino a marzo 2023 (270 partite su 380), quindi manca.
COPIE = {("serie_a", "2021-22"): "https://web.archive.org/web/20250916043854id_/https://understat.com/league/Serie_A/2021",
         ("premier", "2021-22"): "https://web.archive.org/web/20250617130344id_/https://understat.com/league/EPL/2021",
         ("premier", "2022-23"): "https://web.archive.org/web/20250916035035id_/https://understat.com/league/EPL/2022",
         ("serie_a", "2023-24"): "https://web.archive.org/web/20250617140613id_/https://understat.com/league/Serie_A/2023",
         ("premier", "2023-24"): "https://web.archive.org/web/20250324124159id_/https://understat.com/league/EPL/2023"}
RUOLO = {"GK": "POR", "D": "DIF", "M": "CEN", "F": "ATT"}   # prima lettera della posizione Understat di stagione


def estrai(html: str, nome: str):
    """Il JSON che Understat incorpora nella pagina (`nome = JSON.parse('...')`). Solo lettura: niente si esegue."""
    m = re.search(nome + r"\s*=\s*JSON\.parse\('(.*?)'\)", html, re.S)
    if not m:
        raise ValueError(f"{nome} non trovato nella pagina")
    return json.loads(codecs.decode(m.group(1), "unicode_escape"))


def righe_stagione(html: str, lega: str, stagione: str, fonte: str) -> list[tuple]:
    giocatori = estrai(html, "playersData")
    giocate = sum(1 for p in estrai(html, "datesData") if p.get("isResult"))
    if giocate != 380:
        raise ValueError(f"{lega} {stagione}: la copia ha {giocate} partite giocate, non 380")
    out = []
    for p in giocatori:
        pos = p["position"].split()[0] if p["position"].strip() else ""
        out.append((lega, stagione, int(p["id"]), p["player_name"], p["team_title"], RUOLO.get(pos),
                    int(p["games"]), int(p["time"]), int(p["goals"]), int(p["npg"]), int(p["assists"]),
                    float(p["xG"]), float(p["npxG"]), float(p["xA"]), float(p["xGBuildup"]), float(p["xGChain"]), fonte))
    return out


def importa(con, lega, stagione, url) -> int:
    richiesta = urllib.request.Request(url, headers={"User-Agent": "football-scout-index"})
    with urllib.request.urlopen(richiesta, timeout=120) as r:
        html = r.read().decode("utf-8", errors="replace")
    righe = righe_stagione(html, lega, stagione, url)
    con.execute("DELETE FROM stagioni_riassunte WHERE lega = ? AND stagione = ?", (lega, stagione))
    con.executemany(f"INSERT INTO stagioni_riassunte VALUES ({', '.join('?' * 17)})", righe)
    con.commit()
    return len(righe)


if __name__ == "__main__":
    con = db.apri()
    for (lega, stagione), url in COPIE.items():
        print(lega, stagione, importa(con, lega, stagione, url), "giocatori")
