"""Test dell'AVWAP ancorato.

Tre proprietà, e la seconda è quella che conta: l'àncora viene ri-selezionata a
ogni barra, quindi è esattamente il tipo di costruzione in cui un lookahead si
nasconde bene. Lo script da cui viene l'ipotesi fa la stessa cosa e, per come lo
disegna, cancella dal grafico i setup falliti — sul suo grafico storico non si
vedrebbe.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.filters import _anchored_vwap, peak_avwap


@pytest.fixture
def serie() -> pd.DataFrame:
    rng = np.random.default_rng(11)
    n = 300
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.018, n)))
    spread = np.abs(rng.normal(0, 0.012, n)) * close
    df = pd.DataFrame(
        {"open": close, "high": close + spread, "low": close - spread,
         "close": close, "volume": rng.uniform(1e5, 1e7, n)},
        index=pd.date_range("2020-01-01", periods=n, freq="D"),
    )
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    return df


def _naive(df: pd.DataFrame, lookback: int) -> tuple[np.ndarray, np.ndarray]:
    """Seconda implementazione, deliberatamente stupida, per confronto."""
    tp = ((df["high"] + df["low"] + df["close"]) / 3.0).to_numpy(float)
    vol = df["volume"].to_numpy(float)
    high, low = df["high"].to_numpy(float), df["low"].to_numpy(float)
    n = len(df)
    peak, trough = np.full(n, np.nan), np.full(n, np.nan)
    for t in range(lookback, n):
        w = slice(t - lookback, t)
        for origin, out in ((t - lookback + np.argmax(high[w]), peak),
                            (t - lookback + np.argmin(low[w]), trough)):
            sl = slice(origin, t + 1)
            out[t] = float(np.sum(tp[sl] * vol[sl]) / np.sum(vol[sl]))
    return peak, trough


def test_le_somme_cumulate_danno_lo_stesso_risultato_del_calcolo_diretto(serie):
    peak, trough = _anchored_vwap(serie, 20)
    n_peak, n_trough = _naive(serie, 20)
    assert np.allclose(peak.to_numpy(), n_peak, equal_nan=True)
    assert np.allclose(trough.to_numpy(), n_trough, equal_nan=True)


@pytest.mark.parametrize("t", [120, 200, 299])
def test_l_avwap_non_cambia_se_il_futuro_sparisce(serie, t):
    """La proprietà che rende il filtro utilizzabile in un backtest.

    L'àncora è il massimo di una finestra mobile: se la si cercasse su tutta la
    serie invece che sulle barre già viste, il valore sulla barra ``t``
    cambierebbe al crescere dei dati. Non deve.
    """
    piena, _ = _anchored_vwap(serie, 20)
    tronca, _ = _anchored_vwap(serie.iloc[: t + 1], 20)
    a, b = piena.iloc[t], tronca.iloc[t]
    assert (np.isnan(a) and np.isnan(b)) or a == pytest.approx(b)


def test_l_ancora_non_puo_essere_la_barra_su_cui_si_decide(serie):
    """Finestra spostata di una barra.

    Se l'àncora potesse essere ``t``, sulla barra di massimo l'AVWAP sarebbe il
    prezzo tipico di quella sola barra e la condizione ``close > avwap``
    diventerebbe "la chiusura sta nel terzo alto della barra" — un'altra
    domanda.
    """
    lookback = 20
    high = serie["high"].to_numpy(float)
    tp = ((serie["high"] + serie["low"] + serie["close"]) / 3.0).to_numpy(float)
    peak, _ = _anchored_vwap(serie, lookback)

    nuovi_massimi = [t for t in range(lookback, len(serie))
                     if high[t] > high[t - lookback:t].max()]
    assert nuovi_massimi, "la fixture deve contenere almeno un nuovo massimo"
    for t in nuovi_massimi:
        assert peak.iloc[t] != pytest.approx(tp[t])


def test_il_filtro_rispetta_il_contratto(serie):
    allow_long, allow_short = peak_avwap(serie)
    for s in (allow_long, allow_short):
        assert list(s.index) == list(serie.index)
        assert s.dtype == bool
