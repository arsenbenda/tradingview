"""Il gate di qualita' deve bloccare, non solo segnalare.

Il difetto del 2026-09-16 (`results/futures_50y_2.md`) era esattamente questo:
il conteggio delle barre ripetute esisteva gia' e veniva stampato, ma niente
impediva a una serie con il 58% di quotazioni ferme di entrare in un backtest.
"""

from __future__ import annotations

import csv
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import validate_series as v


def scrivi(path, righe):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "open", "high", "low", "close", "volume"])
        w.writerows(righe)
    return str(path)


def serie(n, ripetute_da=None):
    """``n`` barre; da ``ripetute_da`` in poi la barra e' identica alla precedente."""
    out, prezzo = [], 100.0
    for i in range(n):
        giorno = f"2020-{1 + i // 28:02d}-{1 + i % 28:02d}"
        if ripetute_da is not None and i >= ripetute_da:
            o, h, l, c = out[-1][1:5]
        else:
            prezzo += 0.5
            o, h, l, c = prezzo, prezzo + 1, prezzo - 1, prezzo
        out.append([giorno, o, h, l, c, 1000])
    return out


def test_una_serie_pulita_e_utilizzabile(tmp_path):
    p = scrivi(tmp_path / "pulita.csv", serie(200))
    ok, perche = v.utilizzabile(p)
    assert ok, perche


def test_le_quotazioni_ferme_bloccano_la_serie(tmp_path):
    """Sopra la soglia non e' un avviso: la serie non entra in un backtest.

    E' il caso MILKWET — 58% di barre copiate, ATR collassato, stop minuscolo,
    sizing gonfiato e R-multiple fra 15 e 40 che sembravano un vantaggio.
    """
    # 60% di barre ripetute, ben oltre il 5%
    p = scrivi(tmp_path / "ferma.csv", serie(200, ripetute_da=80))
    ok, perche = v.utilizzabile(p)
    assert not ok
    assert "barre ripetute" in perche

    _, _, bloccanti = v.check(p)
    assert bloccanti


def test_i_festivi_non_omessi_restano_sotto_soglia(tmp_path):
    """Poche barre ripetute sono i festivi dei futures FMP, non illiquidita'.

    Devono comparire come avviso e **non** bloccare: e' il difetto per cui il
    controllo era stato scritto in origine, ed e' di un altro ordine di
    grandezza rispetto a una serie che non viene aggiornata.
    """
    p = scrivi(tmp_path / "festivi.csv", serie(200, ripetute_da=196))  # 2%
    ok, _ = v.utilizzabile(p)
    assert ok

    _, n_avvisi, bloccanti = v.check(p)
    assert not bloccanti
    assert n_avvisi >= 1          # segnalato comunque


def test_i_prezzi_non_positivi_bloccano(tmp_path):
    """Back-adjustment per differenza che attraversa lo zero: 19 mercati su 49
    nel primo test sui futures."""
    righe = serie(50)
    righe[30][4] = -5.0
    p = scrivi(tmp_path / "negativa.csv", righe)
    ok, perche = v.utilizzabile(p)
    assert not ok
    assert "non positivi" in perche


def test_i_quindici_strumenti_del_progetto_passano():
    """La soglia non deve invalidare retroattivamente i risultati pubblicati."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from engine import data

    for nome in data.EXTENDED:
        f = f"data/raw/{data.FILES[nome]}"
        ok, perche = v.utilizzabile(f)
        assert ok, f"{nome}: {perche}"
