"""Fase 1 — TPI descrittivo: SPEC F1, F1b; criteri C1, C2, C3, C3b."""
import re
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
    assert round(spearmanr(unito["tpi"], unito["tpi_foto"]).statistic, 3) == 1.0   # "Spearman 1,000" (C1)
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
        numero = re.compile(rf"(?<![\d.]){re.escape(str(peso))}(?!\d)")
        assert not any(numero.search(t) for t in altri if f'"{nome}"' in t), f"peso di {nome} ripetuto fuori da config"
    prima = tpi.classifica(con, "serie_a", "2025-26").set_index("giocatore_id")["tpi"]
    monkeypatch.setitem(config.PESI_TPI, "output", 0.0)
    dopo = tpi.classifica(con, "serie_a", "2025-26").set_index("giocatore_id")["tpi"]
    assert not prima.equals(dopo.reindex(prima.index)), "cambiare il peso in config non cambia il TPI"


def test_c03b_contesti_uguali_al_motore_di_oggi(con, contesti_vecchi):
    """Totale, casa, trasferta, prime 6: come oggi. Le difese forti cambiano apposta (Q-C1), vedi i test sotto."""
    nuovi = tpi.contesti(con, "serie_a", "2025-26")
    confrontati = 0
    for r in nuovi[nuovi["contesto"] != "vs_forti"].itertuples(index=False):
        vecchio = contesti_vecchi.get(str(r.giocatore_id), {}).get(r.contesto)
        if vecchio is None or vecchio["tpi"] is None or (vecchio["n_app"] or 0) < 4:
            continue
        assert r.partite == vecchio["n_app"], (r.giocatore_id, r.contesto)
        assert r.tpi == pytest.approx(vecchio["tpi"], abs=0.01), (r.giocatore_id, r.contesto)
        confrontati += 1
    assert confrontati > 1300, f"confrontati solo {confrontati} valori"


def test_c03b_difese_forti_dalle_partite_understat_con_la_settima(con):
    c = tpi.classifica(con, "serie_a", "2025-26")
    forti = c.attrs["forti"]
    assert forti[:6] == ["Inter", "Juventus", "Como", "Napoli", "Roma", "AC Milan"]   # Q-C1: non più Bologna
    # un giocatore dell'Inter: la sua squadra è fra le 6, quindi entra la settima (Lazio)
    inter = c[c["squadra"] == "Inter"].iloc[0]
    righe = con.execute("SELECT avversario FROM righe WHERE lega='serie_a' AND stagione='2025-26' "
                        "AND giocatore_id=? AND minuti >= 1", (int(inter["giocatore_id"]),)).fetchall()
    attese = sum(a in forti[1:7] for (a,) in righe)
    ctx = tpi.contesti(con, "serie_a", "2025-26")
    trovate = ctx[(ctx["giocatore_id"] == inter["giocatore_id"]) & (ctx["contesto"] == "vs_forti")]["partite"].item()
    assert trovate == attese


def test_c03b_sotto_4_presenze_il_contesto_non_esiste(con):
    ctx = tpi.contesti(con, "serie_a", "2025-26")
    sotto = ctx[ctx["partite"] < 4]
    assert len(sotto) > 0 and sotto["tpi"].isna().all()   # Q-C2: niente TPI di contesto, neanche nella media
