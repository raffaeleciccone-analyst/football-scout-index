"""Lettore delle copie di Understat dall'Internet Archive (riempitore provvisorio, PIANO §2)."""
import pytest

from fsi import archivio


def test_legge_il_json_incorporato_nella_pagina():
    html = r"var playersData = JSON.parse('[{\x22id\x22:\x2242\x22,\x22player_name\x22:\x22Lautaro Mart\u00ednez\x22}]');"
    assert archivio.estrai(html, "playersData") == [{"id": "42", "player_name": "Lautaro Martínez"}]


def test_una_copia_a_meta_stagione_viene_rifiutata():
    html = (r"playersData = JSON.parse('[]'); datesData = JSON.parse('[{\x22isResult\x22:true}]');")
    with pytest.raises(ValueError, match="1 partite"):
        archivio.righe_stagione(html, "serie_a", "2023-24", "prova")
