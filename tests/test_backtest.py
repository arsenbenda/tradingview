"""Test del motore di backtest.

Verificano le quattro proprietà da cui dipende ogni numero prodotto dopo:
esecuzione ritardata di una barra, size derivata dal prezzo di fill, costi
applicati su entrambi i lati, fill pessimistici sugli stop.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.backtest import Costs, run


def frame(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    """rows = [(open, high, low, close), ...] su barre giornaliere."""
    return pd.DataFrame(
        rows,
        columns=["open", "high", "low", "close"],
        index=pd.date_range("2024-01-01", periods=len(rows), freq="D"),
    ).assign(volume=1.0)


def flags(df: pd.DataFrame, true_at: list[int]) -> pd.Series:
    s = pd.Series(False, index=df.index)
    for i in true_at:
        s.iloc[i] = True
    return s


NO_COST = Costs(commission=0.0, slippage=0.0)


def test_il_segnale_su_t_viene_eseguito_all_apertura_di_t_piu_uno():
    df = frame([(100, 101, 99, 100), (110, 111, 109, 110), (112, 113, 111, 112)])
    res = run(
        df,
        entry_long=flags(df, [0]),           # segnale alla chiusura della barra 0
        exit_long=flags(df, [2]),
        stop_distance=pd.Series(10.0, index=df.index),
        costs=NO_COST,
    )
    trade = res.trades[0]
    assert trade.entry_date == df.index[1]   # non la barra 0
    assert trade.entry_price == pytest.approx(110.0)   # apertura di t+1, non close di t


def test_la_size_deriva_dal_prezzo_di_fill_non_dal_close_di_segnale():
    """Il close di segnale è 100, l'apertura di esecuzione 110.

    Con rischio 1% di 100.000 = 1.000 e stop a 10, la quantità corretta è 100
    unità: dipende solo dalla distanza dello stop, e lo stop viene ancorato al
    prezzo di ingresso reale (110 - 10 = 100), non a 100 - 10 = 90.
    """
    df = frame([(100, 101, 99, 100), (110, 115, 109, 112), (112, 113, 111, 112)])
    res = run(
        df,
        entry_long=flags(df, [0]),
        exit_long=flags(df, [2]),
        stop_distance=pd.Series(10.0, index=df.index),
        costs=NO_COST,
        risk_pct=0.01,
        initial_capital=100_000.0,
    )
    trade = res.trades[0]
    assert trade.qty == pytest.approx(100.0)
    assert trade.risk_amount == pytest.approx(1000.0)
    # perdita massima teorica = rischio dichiarato
    assert (trade.entry_price - 100.0) * trade.qty == pytest.approx(1000.0)


def test_costi_applicati_su_entrambi_i_lati():
    df = frame([(100, 101, 99, 100), (100, 101, 99, 100), (100, 101, 99, 100)])
    costs = Costs(commission=0.001, slippage=0.0)
    res = run(
        df,
        entry_long=flags(df, [0]),
        exit_long=flags(df, [2]),
        stop_distance=pd.Series(50.0, index=df.index),
        costs=costs,
    )
    trade = res.trades[0]
    assert trade.entry_price == pytest.approx(100 * 1.001)   # compra più caro
    assert trade.exit_price == pytest.approx(100 * 0.999)    # vende più basso
    assert trade.pnl < 0                                      # entrare e uscire allo stesso prezzo costa


def test_stop_colpito_intrabar_esce_allo_stop():
    # ingresso a 100 con stop a 10 -> livello 90; la barra 2 scende a 85 ma apre a 99
    df = frame([(100, 101, 99, 100), (100, 102, 98, 100), (99, 100, 85, 88)])
    res = run(
        df,
        entry_long=flags(df, [0]),
        exit_long=pd.Series(False, index=df.index),
        stop_distance=pd.Series(10.0, index=df.index),
        costs=NO_COST,
    )
    trade = res.trades[0]
    assert trade.exit_reason == "stop"
    assert trade.exit_price == pytest.approx(90.0)


def test_gap_oltre_lo_stop_esce_all_apertura_non_allo_stop():
    """La proprietà che separa un backtest onesto da uno ottimista.

    Se la barra apre a 80 con lo stop a 90, nessuno è stato eseguito a 90.
    """
    df = frame([(100, 101, 99, 100), (100, 102, 98, 100), (80, 82, 78, 79)])
    res = run(
        df,
        entry_long=flags(df, [0]),
        exit_long=pd.Series(False, index=df.index),
        stop_distance=pd.Series(10.0, index=df.index),
        costs=NO_COST,
    )
    trade = res.trades[0]
    assert trade.exit_reason == "gap"
    assert trade.exit_price == pytest.approx(80.0)
    assert trade.pnl < -trade.risk_amount          # si perde più del rischio nominale


def test_trail_muove_lo_stop_solo_a_favore():
    # prezzo che sale e poi ricade sotto il livello trascinato, cosi' lo stop
    # viene davvero colpito e il test misura a che livello
    df = frame(
        [(100, 101, 99, 100), (101, 103, 99, 101), (102, 104, 100, 102),
         (103, 105, 101, 103), (104, 106, 102, 104), (105, 107, 95, 96)]
    )
    trail = pd.Series([np.nan, 95.0, 97.0, 93.0, 99.0, 99.0], index=df.index)
    res = run(
        df,
        entry_long=flags(df, [0]),
        exit_long=pd.Series(False, index=df.index),
        stop_distance=pd.Series(10.0, index=df.index),
        trail_stop=trail,
        costs=NO_COST,
    )
    # il trail scende a 93 sulla barra 3 ma lo stop resta a 97; esce a 99
    trade = res.trades[0]
    assert trade.exit_price == pytest.approx(99.0)
    assert trade.exit_reason == "stop"


def test_nessuna_posizione_se_lo_stop_non_e_definito():
    df = frame([(100, 101, 99, 100), (100, 101, 99, 100)])
    res = run(
        df,
        entry_long=flags(df, [0]),
        exit_long=pd.Series(False, index=df.index),
        stop_distance=pd.Series(np.nan, index=df.index),
        costs=NO_COST,
    )
    assert res.trades == []


def test_lo_short_guadagna_quando_il_prezzo_scende():
    df = frame([(100, 101, 99, 100), (100, 101, 99, 100), (90, 91, 89, 90)])
    res = run(
        df,
        entry_long=pd.Series(False, index=df.index),
        exit_long=pd.Series(False, index=df.index),
        entry_short=flags(df, [0]),
        exit_short=flags(df, [2]),
        stop_distance=pd.Series(30.0, index=df.index),
        costs=NO_COST,
    )
    trade = res.trades[0]
    assert trade.direction == -1
    assert trade.pnl > 0
