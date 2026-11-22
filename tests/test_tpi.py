"""Fase 1 — TPI descrittivo: SPEC F1, F1b; criteri C1, C2, C3, C3b."""
from pathlib import Path

import pytest
from scipy.stats import spearmanr

from fsi import config, tpi

ZETA = ["z_output", "z_buildup", "z_centralita", "z_boost", "z_consistenza", "z_finishing", "z_form"]


def test_c01_tpi_uguale_alla_fotografia(con, fotografia):
    nuovo = tpi.classifica(con, "serie_a", "2025-26").set_index("giocatore_id")
    assert set(nuovo.index) == set(fotografia.index), "non sono gli stessi 354 giocatori"
    unito = nuovo.join(fotografia, rsuffix="_foto")
    assert (unito["tpi"] - unito["tpi_foto"]).abs().max() <= 0.01
    assert spearmanr(unito["tpi"], unito["tpi_foto"]).statistic == pytest.approx(1.0)
    assert (unito["ruolo"] == unito["ruolo_foto"]).all()
    for z in ZETA:
        assert unito[z].isna().equals(unito[f"{z}_foto"].isna()), f"{z}: assenti diversi"
        assert (unito[z] - unito[f"{z}_foto"]).abs().max() <= 0.01, z


def test_c02_stagioni_mai_mescolate(con):
    prima = tpi.classifica(con, "serie_a", "2025-26")
    migliore = int(prima.iloc[0]["giocatore_id"])
    # una partita finta della stagione dopo, con un giocatore qualsiasi a 5 xG
    con.execute("INSERT INTO partite VALUES ('serie_a', '2026-27', 999999, 1, '2026-08-23', 'A', 'B', 0, 0, 5.0, 0.1)")
    con.execute("INSERT INTO righe (lega, stagione, partita_id, giocatore_id, squadra, avversario, lato, minuti, "
                "gol, gol_senza_rigori, xg_senza_rigori, xa, xg_buildup) "
                "VALUES ('serie_a', '2026-27', 999999, ?, 'A', 'B', 'casa', 90, 3, 3, 5.0, 1.0, 1.0)", (migliore,))
    dopo = tpi.classifica(con, "serie_a", "2025-26")
    assert prima[["giocatore_id", "tpi"]].equals(dopo[["giocatore_id", "tpi"]])


def test_c03_ogni_peso_in_un_posto_solo(con, monkeypatch):
    fsi = Path(config.__file__).parent
    altri = [p.read_text(encoding="utf-8") for p in fsi.glob("*.py") if p.name != "config.py"]
    for nome, peso in config.PESI_TPI.items():
        assert not any(f"{peso}" in testo for testo in altri if f'"{nome}"' in testo), f"peso di {nome} ripetuto"
    prima = tpi.classifica(con, "serie_a", "2025-26").set_index("giocatore_id")["tpi"]
    monkeypatch.setitem(config.PESI_TPI, "output", 0.0)
    dopo = tpi.classifica(con, "serie_a", "2025-26").set_index("giocatore_id")["tpi"]
    assert not prima.equals(dopo.reindex(prima.index)), "cambiare il peso in config non cambia il TPI"


def test_c03b_contesti_uguali_al_motore_di_oggi(con, contesti_vecchi):
    nuovi = tpi.contesti(con, "serie_a", "2025-26")
    confrontati = 0
    for r in nuovi.itertuples(index=False):
        vecchio = contesti_vecchi.get(str(r.giocatore_id), {}).get(r.contesto)
        if vecchio is None or vecchio["tpi"] is None or (vecchio["n_app"] or 0) < 4:
            continue
        assert r.partite == vecchio["n_app"], (r.giocatore_id, r.contesto)
        assert r.tpi == pytest.approx(vecchio["tpi"], abs=0.01), (r.giocatore_id, r.contesto)
        confrontati += 1
    assert confrontati > 1000, f"confrontati solo {confrontati} valori"
