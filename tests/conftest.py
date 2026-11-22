"""Database di prova costruito dai grezzi Serie A 2025-26 (gli stessi della ricostruzione alla cieca)."""
import datetime
import json
import re
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


# ---- rapporto in italiano: alla fine dei test si scrive uscita/rapporto_test.txt (test.bat lo apre) ----
RADICE = Path(__file__).parent.parent
SPEC = RADICE / "SPEC.md"
VERDETTO = RADICE / "prove" / "vera_2024-25_2025-26.json"
RAPPORTO = RADICE / "uscita" / "rapporto_test.txt"
NOMI_LEGHE = {"serie_a": "Serie A", "premier": "Premier League"}
SEGNO = {"passed": "✔ superato", "failed": "✘ SBAGLIATO", "skipped": "– saltato (manca il database)"}
_esiti = []


def _criteri():
    testo = SPEC.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"^- (C\d+[a-z]?)\. (.+?)(?=\n- |\n\n|\n\*\*)", testo, re.S | re.M):
        out[m.group(1)] = re.sub(r"\s+", " ", re.sub(r"[*✱]", "", m.group(2))).strip()
    return out


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        _esiti.append((report.nodeid.split("::")[-1], report.outcome))


def _n(x):
    return f"{x:.2f}".replace(".", ",")


def _testo_rapporto():
    criteri = _criteri()
    conta = {k: sum(e == k for _, e in _esiti) for k in SEGNO}
    righe = [f"RAPPORTO DEI TEST — Football Scout Index — {datetime.datetime.now():%d/%m/%Y %H:%M}", "",
             f"Controlli fatti: {len(_esiti)}.  Superati: {conta['passed']}.  Sbagliati: {conta['failed']}.  "
             f"Saltati: {conta['skipped']}.",
             "Ogni regola della SPEC (C1, C2, ...) ha uno o più controlli automatici: se il programma rompe la regola,",
             "il controllo diventa \"SBAGLIATO\".", "", "=" * 100, "LE REGOLE CONTROLLATE", "=" * 100]
    gruppi = {}
    for nome, esito in _esiti:
        m = re.match(r"test_c0*(\d+[a-z]?)_(.*)", nome)
        codice = "C" + m.group(1) if m else "Altro"
        cosa = (m.group(2) if m else nome.removeprefix("test_")).replace("_", " ")
        gruppi.setdefault(codice, []).append((cosa, esito))
    ordine = lambda c: (c == "Altro", int(re.sub(r"\D", "", c) or 0), c)
    for codice, prove in sorted(gruppi.items(), key=lambda kv: ordine(kv[0])):
        righe += ["", f"{codice} — {criteri.get(codice, 'controlli di supporto (lettura delle copie di Understat)')}"]
        righe += [f"     {SEGNO[esito]}:  {cosa}" for cosa, esito in prove]
    if VERDETTO.exists():
        v = json.loads(VERDETTO.read_text(encoding="utf-8"))["output"]
        righe += ["", "=" * 100, "IL VERDETTO: LA PREVISIONE BATTE LA STATISTICA SEMPLICE?", "=" * 100, "",
                  "Come si legge: un numero da 0 a 1 dice quanto bene si indovina l'ordine dei giocatori nella stagione",
                  "dopo (1 = ordine perfetto, 0 = a caso). \"Statistica semplice\" = gol senza rigori + xA per 90 della",
                  "stagione prima. Ogni stagione è prevista con un modello che ha visto solo le stagioni prima.", ""]
        for prova, st in v.get("per_stagione", {}).items():
            righe.append(f"  Stagione {prova.split(' -> ')[1]}:   " + "   ".join(
                f"{NOMI_LEGHE[l]} {_n(x['rho_modello'])} contro {_n(x['rho_grezzo'])}" for l, x in st.items()))
        righe.append("")
        for lega, x in v["leghe"].items():
            g, s = x["rivali"]["grezzo"], x["sottovalutati"]
            righe += [f"  {NOMI_LEGHE[lega]} (tutte le stagioni di prova insieme, {g['n']} giocatori):",
                      f"     previsione {_n(g['rho_modello'])} contro statistica semplice {_n(g['rho_rivale'])}"
                      + (" → BATTE: la previsione si mostra" if g["batte"] else " → non batte abbastanza: non si mostra"),
                      f"     sottovalutati (giovani fino a 25 anni con pochi minuti, {s['n']} giocatori): "
                      f"{_n(s['rho_modello'])} contro {_n(s['rho_rivale'])}"
                      + (" → BATTE: la lista si mostra" if s["batte"] else " → non batte: la lista non si mostra"),
                      f"     forbice: promette l'80%, ci finiscono dentro {x['forbice']['copertura']:.0%} dei giocatori", ""]
    return "\n".join(righe) + "\n"


def pytest_sessionfinish(session):
    RAPPORTO.parent.mkdir(exist_ok=True)
    RAPPORTO.write_text(_testo_rapporto(), encoding="utf-8")
