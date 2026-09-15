"""Test dell'aggregazione di portafoglio.

Il portafoglio è l'unica leva che questo progetto ha mostrato funzionare — il
drawdown scende da 38.7% del peggior asset singolo a 8.9% aggregato — quindi è
anche il punto in cui un difetto silenzioso costerebbe di più. Questi test
fissano la distinzione fra i due modi in cui un rendimento può mancare.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine import backtest, metrics


def _serie(start: str, periods: int, rate: float, freq: str = "D") -> pd.Series:
    idx = pd.date_range(start, periods=periods, freq=freq)
    return pd.Series(rate, index=idx)


def test_asset_con_la_stessa_storia_danno_la_media_semplice():
    a = _serie("2020-01-01", 100, 0.010)
    b = _serie("2020-01-01", 100, 0.002)
    out = metrics.equal_weight_returns({"A": a, "B": b})
    assert out.to_numpy() == pytest.approx(0.006)


def test_mercato_chiuso_vale_zero_e_resta_nel_denominatore():
    """Un ETF nel weekend: il capitale è allocato, quel giorno la quota rende zero."""
    a = _serie("2020-01-01", 10, 0.010)                       # scambia ogni giorno
    b = _serie("2020-01-01", 10, 0.010)[::2]                  # un giorno su due
    out = metrics.equal_weight_returns({"A": a, "B": b})
    giorno_aperto = out.loc["2020-01-01"]
    giorno_chiuso = out.loc["2020-01-02"]
    assert giorno_aperto == pytest.approx(0.010)              # (0.01 + 0.01) / 2
    assert giorno_chiuso == pytest.approx(0.005)              # (0.01 + 0.00) / 2


def test_uno_strumento_non_ancora_quotato_non_diluisce():
    """Il difetto vero: dividere per strumenti che non esistono ancora."""
    a = _serie("2020-01-01", 1000, 0.010)
    b = _serie("2022-01-01", 300, 0.010)
    out = metrics.equal_weight_returns({"A": a, "B": b})
    assert out.loc["2021-06-01"] == pytest.approx(0.010)      # esiste solo A
    assert out.loc["2022-06-01"] == pytest.approx(0.010)      # esistono entrambi


def test_uno_strumento_uscito_non_diluisce():
    a = _serie("2020-01-01", 1000, 0.010)
    b = _serie("2020-01-01", 100, 0.010)                      # finisce presto
    out = metrics.equal_weight_returns({"A": a, "B": b})
    assert out.loc["2020-02-01"] == pytest.approx(0.010)      # entrambi vivi
    assert out.loc["2021-06-01"] == pytest.approx(0.010)      # solo A, non 0.005


def test_la_quota_di_uno_strumento_fermo_ma_quotato_resta_contata():
    """Vivo ma senza rendimento non è come non esistere: pesa, e pesa zero."""
    a = _serie("2020-01-01", 100, 0.010)
    b = _serie("2020-01-01", 100, 0.000)
    out = metrics.equal_weight_returns({"A": a, "B": b})
    assert out.to_numpy() == pytest.approx(0.005)


def test_portfolio_equity_compone_i_rendimenti_aggregati():
    idx = pd.date_range("2020-01-01", periods=50, freq="D")
    eq = pd.Series(100_000 * 1.01 ** np.arange(len(idx)), index=idx)
    res = backtest.Result(equity=eq, trades=[], exposure=1.0)
    out = metrics.portfolio_equity({"A": res, "B": res}, 100_000.0)
    # due asset identici: il portafoglio è l'asset. La prima barra non ha
    # rendimento, quindi la curva ha un passo in meno di quella di partenza
    assert out.iloc[-1] == pytest.approx(eq.iloc[-1], rel=1e-9)


def test_il_portafoglio_di_un_solo_asset_e_quell_asset():
    idx = pd.date_range("2020-01-01", periods=50, freq="D")
    eq = pd.Series(100_000 * 1.01 ** np.arange(len(idx)), index=idx)
    res = backtest.Result(equity=eq, trades=[], exposure=1.0)
    out = metrics.portfolio_equity({"SOLO": res}, 100_000.0)
    assert out.to_numpy() == pytest.approx(eq.to_numpy(), rel=1e-9)
