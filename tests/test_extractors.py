"""Test del normalizzatore dei risultati MCP.

La deduplicazione è l'unico punto in cui lo script decide di **buttare via**
una riga di dati. Una deduplicazione troppo permissiva sceglie a caso fra due
prezzi che non concordano; una troppo rigida blocca un file che andava bene.
Entrambi gli errori sono silenziosi a valle, quindi stanno qui.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

_spec = importlib.util.spec_from_file_location(
    "extract_av_result",
    pathlib.Path(__file__).resolve().parent.parent / "scripts" / "extract_av_result.py")
extract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extract)


def riga(data: str, o=10.0, h=11.0, l=9.0, c=10.5, v=1000.0):
    return (data, o, h, l, c, v)


def test_senza_ripetizioni_non_tocca_niente():
    righe = [riga("2020-01-01"), riga("2020-01-02"), riga("2020-01-03")]
    out, collassate = extract.dedupe(righe)
    assert out == righe and collassate == 0


def test_due_righe_identiche_diventano_una():
    righe = [riga("2020-01-01"), riga("2020-01-01")]
    out, collassate = extract.dedupe(righe)
    assert len(out) == 1 and collassate == 1


def test_differenze_di_arrotondamento_vengono_collassate():
    """Il caso EEM: la stessa barra arriva due volte, con l'ultima cifra diversa."""
    righe = [riga("2020-01-01", c=36.0050011), riga("2020-01-01", c=36.0099983)]
    out, collassate = extract.dedupe(righe)
    assert len(out) == 1 and collassate == 1


def test_il_volume_puo_differire_senza_bloccare():
    """Venue diversi riportano volumi diversi: non è un prezzo, e il motore non lo guarda."""
    righe = [riga("2020-01-01", v=44046752.0), riga("2020-01-01", v=10.0)]
    out, collassate = extract.dedupe(righe)
    assert len(out) == 1 and collassate == 1


def test_due_aperture_davvero_diverse_fermano_lo_script():
    """L'open è il prezzo con cui il motore riempie: sceglierne una a caso non si fa."""
    righe = [riga("2020-01-01", o=43.35), riga("2020-01-01", o=43.75)]
    with pytest.raises(SystemExit):
        extract.dedupe(righe)


def test_la_soglia_separa_arrotondamento_e_divergenza():
    sotto = 1 + extract.DUP_TOLERANCE / 2
    sopra = 1 + extract.DUP_TOLERANCE * 2
    out, collassate = extract.dedupe([riga("2020-01-01"), riga("2020-01-01", o=10.0 * sotto)])
    assert len(out) == 1 and collassate == 1
    with pytest.raises(SystemExit):
        extract.dedupe([riga("2020-01-01"), riga("2020-01-01", o=10.0 * sopra)])


def test_le_date_sopravvissute_restano_tutte():
    righe = [riga("2020-01-01"), riga("2020-01-01"), riga("2020-01-02"), riga("2020-01-03")]
    out, _ = extract.dedupe(righe)
    assert [r[0] for r in out] == ["2020-01-01", "2020-01-02", "2020-01-03"]


def test_funziona_anche_sul_formato_solo_close():
    """La modalità --close produce righe di due campi, non sei."""
    righe = [("2020-01-01", 10.0), ("2020-01-01", 10.0), ("2020-01-02", 11.0)]
    out, collassate = extract.dedupe(righe)
    assert len(out) == 2 and collassate == 1
