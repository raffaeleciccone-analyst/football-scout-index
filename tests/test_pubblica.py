"""Fase 6 — pubblicazione: SPEC F21, F24; criteri C28, C29 (= regole A1-A15 di SPEC_PUBBLICAZIONE del motore vecchio)."""
import datetime as dt
import json

import pandas as pd
import pytest

from fsi import pubblica as PB

OGGI = dt.date(2026, 11, 22)


def _cal(righe):
    return pd.DataFrame(righe, columns=["giornata", "casa", "trasferta", "giocata"])


# ---- A1: una giornata conta solo quando l'hanno giocata tutte le squadre ----
def test_c29_a1_giornata_chiusa_solo_se_tutte_hanno_giocato():
    cal = _cal([(1, "A", "B", True), (1, "C", "D", True), (2, "A", "C", True), (2, "B", "D", False)])
    assert PB.giornate_chiuse(cal) == 1


# ---- A2: Understat giù per manutenzione si dice in chiaro; un errore qualsiasi non è manutenzione ----
def test_c29_a2_manutenzione_e_errore_sono_diversi():
    assert PB.stato_fonte("<title>Understat.com</title> We will come back soon") == "manutenzione"
    assert PB.stato_fonte("") == "errore"
    assert PB.stato_fonte('{"dates": []}') == "ok"


def test_c29_a2_calendario_vuoto_e_un_errore():
    with pytest.raises(ValueError):
        PB.giornate_chiuse(_cal([]))


# ---- A3: la stagione si ricava dalla data ----
@pytest.mark.parametrize("giorno,stagione", [(dt.date(2026, 11, 22), "2026-27"), (dt.date(2027, 5, 30), "2026-27"),
                                             (dt.date(2027, 7, 15), "2027-28")])
def test_c29_a3_stagione_dalla_data(giorno, stagione):
    assert PB.stagione_da_data(giorno) == stagione


# ---- A4-A6: quando si fa il giro ----
def test_c29_a4_prima_del_debutto_serve_la_giornata_3():
    assert PB.decidi({}, chiuse=2, oggi=OGGI)["azione"] == "attendi"
    assert PB.decidi({}, chiuse=3, oggi=OGGI)["azione"] == "giro"


def test_c29_a6_una_volta_per_giornata_e_si_riprova_se_fallisce():
    assert PB.decidi({"pubblicata": 9}, chiuse=9, oggi=OGGI)["azione"] == "attendi"
    assert PB.decidi({"pubblicata": 9}, chiuse=10, oggi=OGGI)["azione"] == "giro"
    fallito_ieri = {"pubblicata": 9, "fallito": {"giornata": 10, "giorno": "2026-11-21"}}
    assert PB.decidi(fallito_ieri, chiuse=10, oggi=OGGI)["azione"] == "giro"
    fallito_oggi = {"pubblicata": 9, "fallito": {"giornata": 10, "giorno": "2026-11-22"}}
    assert PB.decidi(fallito_oggi, chiuse=10, oggi=OGGI)["azione"] == "attendi"


def test_c29_a6_stato_illeggibile_non_ferma_e_leghe_separate(tmp_path):
    f = tmp_path / "stato.json"
    f.write_text("{non è json", encoding="utf-8")
    assert PB.leggi_stato(f) == {}
    PB.scrivi_stato(f, {"serie_a": {"pubblicata": 9}, "premier": {"pubblicata": 8}})
    assert PB.leggi_stato(f)["premier"]["pubblicata"] == 8


# ---- A7: --stato non manda, non segna, non pubblica ----
def test_c29_a7_solo_stato_non_fa_niente(tmp_path, monkeypatch):
    chiamate = []
    monkeypatch.setattr(PB, "manda", lambda testo: chiamate.append(testo))
    monkeypatch.setattr(PB, "giro", lambda *a, **k: chiamate.append("giro"))
    f = tmp_path / "stato.json"
    PB.sentinella(f, solo_stato=True, oggi=OGGI, fonti={"serie_a": ("ok", 12), "premier": ("ok", 11)})
    assert chiamate == [] and not f.exists()


# ---- A8: l'ordine dei passi; il passo "dati" ferma tutto ----
def test_c29_a8_ordine_dei_passi():
    assert [p for p, _ in PB.PASSI] == ["raccolta", "dati", "archivio", "calcolo", "sito", "verifica", "online"]


def test_c29_a8_un_difetto_nei_dati_ferma_prima_del_calcolo(monkeypatch):
    fatti = []
    for nome, _ in PB.PASSI:
        monkeypatch.setitem(PB.FUNZIONI, nome, (lambda n: (lambda ctx: fatti.append(n) or (n != "dati")))(nome))
    esito = PB.giro({"stagione": "2026-27"})
    assert esito == {"ok": False, "passo": "dati"} and fatti == ["raccolta", "dati"]


# ---- A9: l'archivio non cancella e non sovrascrive ----
def test_c29_a9_archivio_non_sovrascrive(tmp_path):
    (tmp_path / "uscita").mkdir()
    (tmp_path / "uscita" / "a.html").write_text("vecchia", encoding="utf-8")
    PB.archivia(tmp_path / "uscita", tmp_path / "archivio", "2025-26")
    (tmp_path / "uscita" / "a.html").write_text("nuova", encoding="utf-8")
    PB.archivia(tmp_path / "uscita", tmp_path / "archivio", "2025-26")
    assert (tmp_path / "archivio" / "2025-26" / "a.html").read_text(encoding="utf-8") == "vecchia"


# ---- A10-A11: la verifica prima di andare online ----
def test_c29_a10_a11_verifica(tmp_path):
    for lega in ("serie_a", "premier"):
        (tmp_path / lega).mkdir()
        (tmp_path / lega / "dati.js").write_text('window.DATI = {"stagione": "2026-27"};', encoding="utf-8")
        (tmp_path / lega / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    assert PB.verifica(tmp_path, "2026-27") == []
    (tmp_path / "premier" / "dati.js").write_text('window.DATI = {"stagione": "2025-26"};', encoding="utf-8")
    (tmp_path / "serie_a" / "index.html").write_text('<div id="avviso-fonte">fermo</div>', encoding="utf-8")
    problemi = PB.verifica(tmp_path, "2026-27")
    assert any("premier" in p and "2025-26" in p for p in problemi) and any("avviso" in p for p in problemi)


# ---- A12: online da sola solo dalla seconda pubblicazione; la prima si ferma prima del push ----
def test_c29_a12_la_prima_della_stagione_non_va_online():
    assert PB.puo_andare_online({"stagione": "2026-27", "pubblicazioni": 0}) is False
    assert PB.puo_andare_online({"stagione": "2026-27", "pubblicazioni": 1}) is True


# ---- A13: senza Telegram non esplode ----
def test_c29_a13_telegram_assente_o_giu_non_fa_fallire(monkeypatch):
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    assert PB.manda("prova") is False


# ---- A14-A15: un messaggio per blocco, promemoria ogni 7 giorni, avviso quando si sblocca ----
def test_c29_a15_stesso_blocco_un_messaggio_poi_promemoria_poi_sbloccato():
    stato = {}
    assert PB.messaggio_blocco(stato, "dati", OGGI) is not None          # primo blocco: si annuncia
    assert PB.messaggio_blocco(stato, "dati", OGGI + dt.timedelta(1)) is None      # stesso motivo: silenzio
    assert "promemoria" in PB.messaggio_blocco(stato, "dati", OGGI + dt.timedelta(7)).lower()
    assert PB.messaggio_blocco(stato, "verifica", OGGI + dt.timedelta(8)) is not None   # motivo diverso: subito
    assert "sbloccat" in PB.messaggio_blocco(stato, None, OGGI + dt.timedelta(9)).lower()


def test_c29_a14_dati_fermi_da_10_giorni_un_avviso_per_blocco():
    stato = {}
    assert PB.avviso_fermo(stato, giorni_fermo=9) is None
    assert PB.avviso_fermo(stato, giorni_fermo=10) is not None
    assert PB.avviso_fermo(stato, giorni_fermo=15) is None
    assert PB.avviso_fermo(stato, giorni_fermo=0) is None and "fermo_avvisato" not in stato   # si sblocca: si azzera


# ---- C28: fino al cambio mai nelle cartelle dei siti ----
def test_c28_la_destinazione_dei_siti_e_vuota_fino_al_cambio():
    from fsi import config
    assert config.DESTINAZIONE_SITI == {}   # si riempie solo al cambio, con il via libera dell'utente (F24)
