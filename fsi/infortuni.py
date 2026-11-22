"""Storia degli infortuni da Transfermarkt (raccolta, SPEC F21; ingrediente candidato della previsione, F2).

Una pagina per giocatore (più una seconda per le carriere lunghe), con calma: una richiesta ogni 3 secondi.
Ogni pagina si salva in dati/transfermarkt/ e non si riscarica mai. Uso: python -m fsi.infortuni
"""
import datetime
import html
import re
import time
import urllib.request
from pathlib import Path

import pandas as pd

from fsi import config as C
from fsi import db

CARTELLA = C.RADICE / "dati" / "transfermarkt"
URL = "https://www.transfermarkt.it/x/verletzungen/spieler/{tm}/page/{pagina}"
PAUSA = 3.0   # secondi fra due richieste: non si disturba il sito
PRIMA_STAGIONE = "2021-22"
_ultima = [0.0]


def _pagina(tm_id, pagina) -> str:
    f = CARTELLA / f"{tm_id}_{pagina}.html"
    if f.exists():
        return f.read_text(encoding="utf-8")
    time.sleep(max(0.0, _ultima[0] + PAUSA - time.time()))
    richiesta = urllib.request.Request(URL.format(tm=tm_id, pagina=pagina), headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0.0.0 Safari/537.36", "Accept-Language": "it-IT,it;q=0.9"})
    try:
        with urllib.request.urlopen(richiesta, timeout=30) as r:
            testo = r.read().decode("utf-8", errors="replace")
    finally:
        _ultima[0] = time.time()
    CARTELLA.mkdir(parents=True, exist_ok=True)
    f.write_text(testo, encoding="utf-8")
    return testo


def leggi(testo: str) -> list[dict]:
    """Le righe della tabella infortuni: stagione '24/25' -> '2024-25', date gg/mm/aaaa, giorni."""
    i = testo.find('class="items"')
    if i < 0:
        return []
    tabella = testo[i:testo.find("</table>", i)]
    out = []
    for riga in re.findall(r"<tr[^>]*>(.*?)</tr>", tabella, re.S):
        celle = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", riga, re.S)]
        if len(celle) < 5 or not re.fullmatch(r"\d\d/\d\d", celle[0]):
            continue
        a = 2000 + int(celle[0][:2])
        data = lambda s: datetime.datetime.strptime(s, "%d/%m/%Y").date().isoformat() if re.fullmatch(r"\d\d/\d\d/\d{4}", s) else None
        giorni = re.match(r"\d+", celle[4].replace(".", ""))
        out.append({"stagione": f"{a}-{str(a + 1)[2:]}", "tipo": celle[1], "inizio": data(celle[2]),
                    "rientro": data(celle[3]), "giorni_fuori": int(giorni.group()) if giorni else None})
    return out


def storia(tm_id) -> list[dict]:
    """Tutte le pagine finché la storia non arriva prima della 2021-22 o le pagine finiscono."""
    righe, pagina = [], 1
    while True:
        testo = _pagina(tm_id, pagina)
        nuove = leggi(testo)
        righe += nuove
        if not nuove or min(r["stagione"] for r in nuove) < PRIMA_STAGIONE or f"page/{pagina + 1}" not in testo:
            return righe
        pagina += 1


def da_scaricare(con) -> pd.DataFrame:
    """Chi ha l'id Transfermarkt e almeno 450' in una stagione di partenza delle prove o della previsione."""
    return pd.read_sql(
        "SELECT DISTINCT g.giocatore_id, g.tm_id FROM giocatori g JOIN ("
        "  SELECT giocatore_id, stagione, SUM(minuti) m FROM righe GROUP BY lega, stagione, giocatore_id"
        "  UNION ALL SELECT giocatore_id, stagione, minuti FROM stagioni_riassunte) s USING (giocatore_id) "
        "WHERE g.tm_id IS NOT NULL AND s.m >= ? AND s.stagione >= ? "
        "AND g.giocatore_id NOT IN (SELECT giocatore_id FROM infortuni_scaricati)",
        con, params=[C.SOGLIA_PREVISIONE, PRIMA_STAGIONE])


def scarica(con, avanzamento=print):
    lista = da_scaricare(con)
    for n, r in enumerate(lista.itertuples(index=False), 1):
        try:
            righe = storia(int(r.tm_id))
        except Exception as e:   # una pagina che non risponde non ferma le altre: si riprova al giro dopo
            avanzamento(f"{n}/{len(lista)} tm {r.tm_id}: errore {e}")
            continue
        con.executemany("INSERT OR REPLACE INTO infortuni VALUES (?, ?, ?, ?, ?, ?)",
                        [(int(r.giocatore_id), x["stagione"], x["inizio"], x["rientro"], x["giorni_fuori"], x["tipo"])
                         for x in righe if x["inizio"]])
        con.execute("INSERT OR REPLACE INTO infortuni_scaricati VALUES (?, ?, ?)",
                    (int(r.giocatore_id), int(r.tm_id), datetime.date.today().isoformat()))
        con.commit()
        if n % 25 == 0 or n == len(lista):
            avanzamento(f"{n}/{len(lista)} giocatori scaricati")


if __name__ == "__main__":
    con = db.apri()
    print("da scaricare:", len(da_scaricare(con)), flush=True)
    scarica(con, lambda s: print(s, flush=True))
