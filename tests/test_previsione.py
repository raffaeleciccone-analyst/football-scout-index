"""Fase 2 — previsione: SPEC F2-F10; criteri C4-C16."""
import numpy as np
import pandas as pd
import pytest

from fsi import config, db, previsione as P

BASE, DOPO = "2024-25", "2025-26"


@pytest.fixture(scope="module")
def vero():
    if not config.DB.exists():
        pytest.skip("database vero assente (python -m fsi.ponte)")
    c = db.apri()
    yield c
    c.close()


@pytest.fixture(scope="module")
def tab(vero):
    return P.tabella(vero, BASE, DOPO)


@pytest.fixture(scope="module")
def verdetto(vero):
    return P.prova(vero, BASE, DOPO)


@pytest.fixture(scope="module")
def modello(tab):
    return P.stima(tab)


# ---- C4: niente sbirciate nel futuro ----
def test_c04_la_previsione_non_vede_la_stagione_da_prevedere(vero, modello):
    prima, _ = P.prevedi(vero, modello, DOPO)
    vero.execute("SAVEPOINT s")
    vero.execute("UPDATE righe SET xg_senza_rigori = xg_senza_rigori + 1, xa = xa + 1 WHERE stagione = '2026-27'")
    dopo, _ = P.prevedi(vero, modello, DOPO)
    vero.execute("ROLLBACK TO s")
    pd.testing.assert_frame_equal(prima, dopo)


def test_c04_la_previsione_aggiornata_non_vede_le_giornate_dopo(vero):
    prima = P.ingredienti(vero, "serie_a", "2026-27", fino_a_giornata=5)
    vero.execute("SAVEPOINT s")
    vero.execute("UPDATE righe SET xa = xa + 1 WHERE stagione = '2026-27' AND partita_id IN "
                 "(SELECT partita_id FROM partite WHERE stagione = '2026-27' AND giornata > 5)")
    dopo = P.ingredienti(vero, "serie_a", "2026-27", fino_a_giornata=5)
    vero.execute("ROLLBACK TO s")
    pd.testing.assert_frame_equal(prima, dopo)


def test_c04_gli_infortuni_dopo_la_giornata_non_contano(vero):
    prima = P.ingredienti(vero, "serie_a", "2026-27", fino_a_giornata=5)
    gid = int(prima.iloc[0]["giocatore_id"])
    vero.execute("SAVEPOINT s")
    vero.execute("INSERT OR REPLACE INTO infortuni VALUES (?, '2026-27', '2027-03-01', '2027-05-01', 61, 'prova')", (gid,))
    dopo = P.ingredienti(vero, "serie_a", "2026-27", fino_a_giornata=5)
    vero.execute("ROLLBACK TO s")
    pd.testing.assert_frame_equal(prima, dopo)


# ---- C5: pesi stimati, prova su giocatori mai visti ----
def test_c05_la_previsione_di_prova_non_usa_il_risultato_del_giocatore(tab):
    oof = P.fuori_campione(tab)
    i = tab.index[(tab["min_dopo"] >= config.MINUTI_METRO).to_numpy()][0]   # uno che entra nella stima
    falsa = tab.copy()
    falsa.loc[i, "y"] = 99.0
    assert P.fuori_campione(falsa).loc[i, "pred"] == pytest.approx(oof.loc[i, "pred"])


def test_c05_nessun_peso_scritto_a_mano(modello):
    assert set(modello["pesi"]) >= {"out_t", "xgxa_t", "log_minuti", "eta"}
    assert len(set(np.round(list(modello["pesi"].values()), 6))) > 3   # numeri stimati, non tutti uguali o tondi


# ---- C6: chi entra ----
def test_c06_soglia_450_minuti():
    ingr = pd.DataFrame({"giocatore_id": [1, 2], "lega": "serie_a", "ruolo": "ATT", "minuti": [449, 450]})
    ammessi, esclusi = P.ammessi(ingr, 450)
    assert list(ammessi["giocatore_id"]) == [2]
    assert esclusi.set_index("giocatore_id").loc[1, "motivo"] == "storia insufficiente"


def test_c06_senza_dati_nel_campionato(vero, modello):
    _, esclusi = P.prevedi(vero, modello, DOPO)
    nuovi = esclusi[esclusi["motivo"] == "nessun dato nel campionato"]
    in_base = {g for (g,) in vero.execute("SELECT DISTINCT giocatore_id FROM righe WHERE stagione = ?", (DOPO,))}
    assert len(nuovi) > 0 and not set(nuovi["giocatore_id"]) & in_base


# ---- C7: chi gioca poco: forbice larga e più vicino alla media del ruolo ----
def test_c07_pochi_minuti_forbice_larga_e_vicino_alla_media(tab, modello):
    tipo = tab[tab["ruolo"] == "ATT"].iloc[[0, 0]].copy()
    tipo["out90"] = tipo["xgxa90"] = tab.loc[tab["ruolo"] == "ATT", "out90"].quantile(0.95)
    tipo["minuti"] = [500, 2500]
    tipo.index = [0, 1]
    p = P.applica(modello, tipo)
    assert (p.loc[0, "hi"] - p.loc[0, "lo"]) > (p.loc[1, "hi"] - p.loc[1, "lo"])
    assert p.loc[0, "pred"] < p.loc[1, "pred"]   # sopra la media: con meno minuti si avvicina alla media


# ---- C8-C10: battere i rivali ----
def test_c08_batte_vuol_dire_intervallo_tutto_sopra_zero():
    rng = np.random.default_rng(1)
    reale = rng.normal(size=300)
    assert P.batte(reale + rng.normal(scale=0.3, size=300), reale + rng.normal(scale=1.5, size=300), reale)["batte"]
    stessa = reale + rng.normal(scale=1.0, size=300)
    assert not P.batte(stessa, stessa, reale)["batte"]          # C9: un modello che copia il rivale non batte


def test_c08_con_piu_stagioni_l_ordine_si_misura_dentro_ogni_stagione():
    rng = np.random.default_rng(2)
    reale = rng.normal(size=400)
    stagione = np.repeat(["a", "b"], 200)
    spostata = reale + np.where(stagione == "a", 5.0, 0.0)          # stesso ordine, livello diverso fra stagioni
    rivale = reale + rng.normal(scale=0.5, size=400)
    assert P.batte(spostata, rivale, reale, stagione)["batte"]
    assert P.batte(spostata, rivale, reale, stagione)["rho_modello"] == pytest.approx(1.0)


def test_c09_la_regola_dura_decide_cosa_si_mostra(verdetto):
    for lega, v in verdetto["leghe"].items():
        assert v["mostra_previsione"] == v["rivali"]["grezzo"]["batte"], lega


def test_c10_sottovalutati_provati_solo_su_chi_gioca_poco(verdetto):
    for v in verdetto["leghe"].values():
        s = v["sottovalutati"]
        assert s["gruppo_minuti"] == [config.SOGLIA_PREVISIONE, config.MINUTI_POCO_CONSIDERATO]
        assert s["eta_massima"] == config.ETA_MAX_SOTTOVALUTATI
        assert v["mostra_sottovalutati"] == s["batte"] and s["rivale"] == "output grezzo"
        assert 0 < s["n"] < v["n"]


def test_c10_con_1500_minuti_o_26_anni_non_e_mai_sottovalutato():
    prev = pd.DataFrame({"giocatore_id": [1, 2, 3, 4, 5], "lega": "serie_a", "ruolo": "ATT",
                         "minuti": [1499, 1500, 600, 800, 800], "eta": [25.9, 21.0, 19.0, 26.0, np.nan],
                         "pred": [0.5, 0.9, 0.4, 0.8, 0.8]})
    assert list(P.sottovalutati(prev)["giocatore_id"]) == [1, 3]


def test_c10b_sfortunati_ordinati_per_xg_meno_gol_e_dichiarati_descrizione():
    prev = pd.DataFrame({"giocatore_id": [1, 2], "lega": "serie_a", "ruolo": "ATT", "minuti": [900, 900],
                         "out90": [0.30, 0.20], "xgxa90": [0.35, 0.45]})
    s = P.sfortunati(prev)
    assert list(s["giocatore_id"]) == [2, 1]
    assert s["sfortuna90"].tolist() == pytest.approx([0.25, 0.05])
    assert (s["nota"] == "descrizione, non previsione").all()


# ---- C11: forbice all'80% ----
def test_c11_forbice_si_mostra_solo_se_cattura_fra_70_e_90():
    assert P.copertura(np.array([1, 2, 3, 4]), np.zeros(4), np.array([5, 5, 5, 0])) == 0.75
    for cop, mostra in ((0.69, False), (0.70, True), (0.90, True), (0.91, False)):
        assert P.mostra_forbice(cop) is mostra


def test_c11_la_prova_riporta_la_copertura(verdetto):
    for v in verdetto["leghe"].values():
        assert v["forbice"]["mostra"] == P.mostra_forbice(v["forbice"]["copertura"])


# ---- C12-C13: rivali e stato ----
def test_c12_tutti_i_rivali_sugli_stessi_giocatori(verdetto):
    for v in verdetto["leghe"].values():
        assert set(v["rivali"]) == {"grezzo", "minuti", "tpi", "tpi_pro"}
        for r in v["rivali"].values():
            assert r["n"] >= 100 and {"rho_modello", "rho_rivale", "diff_lo", "diff_hi", "batte"} <= set(r)


def test_c13_con_una_coppia_sola_e_un_prototipo(verdetto):
    assert verdetto["stato"] == "prototipo, non verificato"


# ---- C14: agosto fermo, aggiornata solo se provata ----
def test_c14_la_previsione_di_agosto_non_si_riscrive(tmp_path):
    prima = pd.DataFrame({"giocatore_id": [1], "pred": [0.4]})
    p = P.salva_agosto(prima, "2026-27", tmp_path)
    P.salva_agosto(pd.DataFrame({"giocatore_id": [1], "pred": [9.9]}), "2026-27", tmp_path)
    assert pd.read_json(p)["pred"].tolist() == [0.4]


def test_c14_aggiornata_solo_dalle_giornate_provate():
    prove = {5: False, 10: True, 15: False, 19: True}
    assert P.giornata_valida(prove, 4) is None
    assert P.giornata_valida(prove, 12) == 10
    assert P.giornata_valida(prove, 17) is None       # la prova del punto prima (15) non è passata
    assert P.giornata_valida(prove, 30) == 19


# ---- C15: motivi ----
def test_c15_il_primo_motivo_e_quello_che_sposta_di_piu(tab, modello):
    p = P.applica(modello, tab.head(20))
    for i, r in p.iterrows():
        primo = r["motivi"][0]
        spostamenti = {ing: abs(P.applica(modello, P.porta_alla_media(modello, tab.loc[[i]], ing)).loc[i, "pred"] - r["pred"])
                       for ing in P.INGREDIENTI_MOTIVO}
        assert spostamenti[primo] == pytest.approx(max(spostamenti.values()))


# ---- C16: classifiche per ruolo ----
def test_c16_classifiche_dentro_il_ruolo(vero, modello):
    prev, _ = P.prevedi(vero, modello, DOPO)
    for (lega, ruolo), b in prev.groupby(["lega", "ruolo"]):
        assert sorted(b["posizione_ruolo"]) == list(range(1, len(b) + 1)), (lega, ruolo)


# ---- prova vera: stima su 2023-24 -> 2024-25 (stagione riassunta dall'archivio), prova su 2024-25 -> 2025-26 ----
@pytest.fixture(scope="module")
def riassunta(vero):
    if not vero.execute("SELECT COUNT(*) FROM stagioni_riassunte WHERE stagione = '2023-24'").fetchone()[0]:
        pytest.skip("2023-24 non importata (python -m fsi.archivio)")
    return vero


def test_c05_tolgo_la_stagione_di_prova_i_pesi_non_cambiano(riassunta):
    stimata = P.tabella(riassunta, "2023-24", "2024-25")
    prima = P.stima(stimata, contesti=False)["pesi"]
    riassunta.execute("SAVEPOINT s")
    riassunta.execute("DELETE FROM righe WHERE stagione = '2025-26'")
    dopo = P.stima(P.tabella(riassunta, "2023-24", "2024-25"), contesti=False)["pesi"]
    riassunta.execute("ROLLBACK TO s")
    assert prima == pytest.approx(dopo)


def test_c13_la_prova_vera_e_a_finestra_mobile(riassunta):
    v = P.prova_vera(riassunta, P.COPPIE)
    assert v["stato"].startswith("verificata") and set(v["leghe"]) == {"serie_a", "premier"}
    # ogni stagione di prova usa solo le coppie che vengono prima
    for prova, stimata_su in v["stimata_su"].items():
        assert stimata_su and all(c.split(" -> ")[1] <= prova.split(" -> ")[0] for c in stimata_su), prova
    assert set(v["per_stagione"]) >= {"2023-24 -> 2024-25", "2024-25 -> 2025-26"}
    for x in v["leghe"].values():
        assert x["mostra_previsione"] == x["rivali"]["grezzo"]["batte"]
