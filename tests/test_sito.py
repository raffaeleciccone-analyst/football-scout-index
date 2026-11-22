"""Fase 3 — sito: SPEC F11-F16, F3, F3b, F9; criteri C3c, C9, C10, C17-C20, C28."""
import json
import re
from pathlib import Path

import pandas as pd
import pytest

from fsi import sito

TESTI = json.loads((Path(sito.__file__).parent.parent / "sito" / "testi.json").read_text(encoding="utf-8"))


def _verdetto(rho=0.812, batte=True, sottovalutati=True):
    riv = lambda m, r, b: {"n": 200, "rho_modello": m, "rho_rivale": r, "diff_lo": 0.01 if b else -0.01,
                           "diff_hi": 0.05, "batte": b}
    lega = {"n": 200, "rivali": {"grezzo": riv(rho, 0.701, batte), "minuti": riv(rho, 0.02, True),
                                 "tpi": riv(rho, 0.46, True), "tpi_pro": riv(rho, 0.53, True)},
            "sottovalutati": riv(0.7, 0.6, sottovalutati) | {"gruppo_minuti": [450, 1500], "eta_massima": 25},
            "forbice": {"copertura": 0.78, "mostra": True}, "mostra_previsione": batte,
            "mostra_sottovalutati": sottovalutati}
    return {"stato": "verificata (prova a finestra mobile su stagioni mai viste)", "infortuni": False,
            "per_stagione": {"2024-25 -> 2025-26": {"serie_a": {"n": 200, "rho_modello": rho, "rho_grezzo": 0.701}}},
            "stimata_su": {"2024-25 -> 2025-26": ["2023-24 -> 2024-25"]}, "leghe": {"serie_a": lega, "premier": lega}}


def _previsione(con):
    ids = [r[0] for r in con.execute("SELECT giocatore_id FROM righe GROUP BY giocatore_id "
                                     "HAVING SUM(minuti) >= 450 LIMIT 40")]
    p = pd.DataFrame({"giocatore_id": ids, "lega": "serie_a", "ruolo": "ATT", "minuti": 1000, "eta": 22.0,
                      "out90": 0.3, "xgxa90": 0.35, "pred": 0.33, "lo": 0.2, "hi": 0.45, "rm": 0.31,
                      "motivi": [["rendimento", "eta", "minuti"]] * len(ids)})
    p["posizione_ruolo"] = range(1, len(p) + 1)
    esclusi = pd.DataFrame({"giocatore_id": [999999], "lega": ["serie_a"], "motivo": ["storia insufficiente"]})
    return p, esclusi


@pytest.fixture
def costruito(con, tmp_path):
    prev, esclusi = _previsione(con)
    sito.genera(con, tmp_path, {"serie_a": "2025-26"}, prev, esclusi, _verdetto(), stagione_prevista="2026-27")
    return tmp_path


def _dati(cartella):
    testo = (cartella / "serie_a" / "dati.js").read_text(encoding="utf-8")
    return json.loads(testo.removeprefix("window.DATI = ").rstrip().rstrip(";"))


# ---- C17: due lingue, nessun testo in una lingua sola ----
def test_c17_ogni_testo_ha_italiano_e_inglese():
    for chiave, t in TESTI.items():
        assert t.get("it", "").strip() and t.get("en", "").strip(), chiave
        assert set(re.findall(r"\{(\w+)\}", t["it"])) == set(re.findall(r"\{(\w+)\}", t["en"])), chiave


def test_c17_le_pagine_non_hanno_testo_fuori_da_testi_json(costruito):
    for pagina in costruito.rglob("*.html"):
        h = re.sub(r"<(script|style)\b.*?</\1>", "", pagina.read_text(encoding="utf-8"), flags=re.S)
        h = re.sub(r"<(\w+)[^>]*\bdata-t=\"[^\"]+\"[^>]*>.*?</\1>", "", h, flags=re.S)   # testi tradotti
        h = re.sub(r"<[^>]+>", " ", h)
        resto = [w for w in h.split() if re.search(r"[A-Za-zÀ-ÿ]{3,}", w)]
        assert not resto, f"{pagina.name}: testo non tradotto {resto[:5]}"
    usate = set()
    for f in (Path(sito.__file__).parent.parent / "sito").glob("*"):
        usate |= set(re.findall(r"""(?:data-t=["']|\bt\(["'])(\w+)""", f.read_text(encoding="utf-8")))
    prefissi = {k for k in usate if k.endswith("_")}
    assert usate - prefissi <= set(TESTI), f"chiavi mancanti in testi.json: {usate - prefissi - set(TESTI)}"
    # le chiavi composte nello script (prefisso + nome): tutte le varianti devono esistere
    from fsi import config, previsione, tpi
    varianti = {"dim_": tpi.DIMENSIONI, "ruolo_": list(config.PESO_RUOLO), "ctx_": config.CONTESTI,
                "motivo_": previsione.INGREDIENTI_MOTIVO, "rivale_": ["grezzo", "minuti", "tpi", "tpi_pro"],
                "ruolo_breve_": list(config.PESO_RUOLO), "sez_": [f"{s}_{x}" for s in ("previsione", "classifica", "cerca", "metodo") for x in "ts"],
                "lega_": list(config.LEGHE), "escluso_": ["storia insufficiente", "nessun dato nel campionato"],
                "card_liv_": ["oro", "argento", "bronzo"]}
    assert prefissi <= set(varianti), prefissi - set(varianti)
    mancanti = [p + v for p in prefissi for v in varianti[p] if p + v not in TESTI]
    assert not mancanti, f"varianti mancanti in testi.json: {mancanti}"


# ---- C18: nessun numero scritto a mano ----
def test_c18_cambio_un_dato_cambia_la_frase(con, tmp_path):
    prev, esclusi = _previsione(con)
    for rho, atteso in ((0.812, "0,81"), (0.733, "0,73")):
        sito.genera(con, tmp_path / str(rho), {"serie_a": "2025-26"}, prev, esclusi, _verdetto(rho),
                    stagione_prevista="2026-27")
        assert atteso in (tmp_path / str(rho) / "serie_a" / "metodo.html").read_text(encoding="utf-8")


# ---- C19 e C3c: la pagina giocatore ----
def test_c19_e_c03c_dati_della_pagina_giocatore(costruito, con):
    d = _dati(costruito)
    lautaro = next(g for g in d["giocatori"].values() if "Lautaro" in g["nome"])
    assert lautaro["tpi"] is not None and lautaro["contesti"] and lautaro["andamento"]
    for c in lautaro["contesti"]:
        assert c["piccolo"] == (c["partite"] < 8)   # C3c: "campione piccolo" sotto le 8 partite
    assert d["giocatori"]["999999"]["motivo"] == "storia insufficiente"
    h = (costruito / "serie_a" / "giocatore.html").read_text(encoding="utf-8")
    assert 'id="cerca"' in h and "dati.js" in h


# ---- C20: home e sezioni ----
def test_c20_home_porta_ai_due_siti_e_ogni_sito_ha_le_sezioni(costruito):
    home = (costruito / "home" / "index.html").read_text(encoding="utf-8")
    assert "serie_a/index.html" in home
    for pagina in ("index.html", "classifica.html", "giocatore.html", "metodo.html"):
        assert (costruito / "serie_a" / pagina).exists(), pagina
    metodo = (costruito / "serie_a" / "metodo.html").read_text(encoding="utf-8")
    assert 'data-t="non_misurato_difesa"' in metodo and 'data-t="non_misurato_possesso"' in metodo


# ---- C9, C10: la regola dura decide cosa si vede ----
def test_c09_c10_se_non_batte_la_pagina_lo_dice(con, tmp_path):
    prev, esclusi = _previsione(con)
    sito.genera(con, tmp_path, {"serie_a": "2025-26"}, prev, esclusi, _verdetto(batte=False, sottovalutati=False),
                stagione_prevista="2026-27")
    d = _dati(tmp_path)
    assert d["verdetto"]["mostra_previsione"] is False and d["verdetto"]["mostra_sottovalutati"] is False
    h = (tmp_path / "serie_a" / "index.html").read_text(encoding="utf-8")
    assert 'data-t="stato_prev_no"' in h and 'data-t="stato_sv_no"' in h and 'id="sottovalutati"' not in h


# ---- C28: fino al cambio, mai nelle cartelle dei siti ----
def test_c28_non_scrive_nelle_cartelle_dei_siti(con):
    prev, esclusi = _previsione(con)
    for vietata in (Path(r"C:\dev\serie-a-index"), Path(r"C:\dev\premier-league-index") / "sotto"):
        with pytest.raises(ValueError, match="cartella di un sito"):
            sito.genera(con, vietata, {"serie_a": "2025-26"}, prev, esclusi, _verdetto(), stagione_prevista="2026-27")


def test_c14_nel_sito_aggiornata_solo_se_provata_e_previsto_contro_reale(con, tmp_path):
    prev, esclusi = _previsione(con)
    agg = prev[["giocatore_id", "pred", "lo", "hi"]].assign(pred=0.5)
    sito.genera(con, tmp_path / "si", {"serie_a": "2025-26"}, prev, esclusi, _verdetto(), stagione_prevista="2026-27",
                aggiornate={"serie_a": {"giornata": 9, "valida": 5, "stagione": "2027-28", "prev": agg}})
    d = _dati(tmp_path / "si")
    g = d["giocatori"][str(int(agg.iloc[0]["giocatore_id"]))]
    assert d["aggiornata"]["valida"] == 5 and g["aggiornata"]["pred"] == 0.5
    sito.genera(con, tmp_path / "no", {"serie_a": "2025-26"}, prev, esclusi, _verdetto(), stagione_prevista="2026-27",
                aggiornate={"serie_a": {"giornata": 4, "valida": None, "stagione": "2027-28", "prev": None}})
    d = _dati(tmp_path / "no")
    assert d["aggiornata"]["valida"] is None and not any("aggiornata" in g for g in d["giocatori"].values())
