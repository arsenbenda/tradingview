"""Test di fedeltà al Pine.

Due categorie:

1. valori attesi calcolati a mano, per fissare le semantiche che di solito
   vengono sbagliate nel porting (innesco della RMA, true range sulla prima
   barra, verso dello shift della nuvola);
2. **assenza di lookahead**, verificata per costruzione: il valore di un
   indicatore sulla barra t calcolato sulla serie completa deve coincidere con
   quello calcolato su una serie troncata a t. Se un indicatore guarda avanti,
   questo test fallisce.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine import indicators as ind


@pytest.fixture
def small() -> pd.DataFrame:
    # true range atteso: [2, 2, 2, 4, 2] — la quarta barra rompe l'uniformita',
    # cosi' RMA e SMA divergono numericamente e il test puo' distinguerle
    return pd.DataFrame(
        {
            "open": [9.0, 10.0, 11.0, 12.0, 14.0],
            "high": [10.0, 11.0, 12.0, 15.0, 15.0],
            "low": [8.0, 9.0, 10.0, 11.0, 13.0],
            "close": [9.0, 10.0, 11.0, 14.0, 14.0],
            "volume": [1.0, 1.0, 1.0, 1.0, 1.0],
        }
    )


@pytest.fixture
def walk() -> pd.DataFrame:
    rng = np.random.default_rng(20260915)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, 300)))
    spread = np.abs(rng.normal(0, 0.01, 300)) * close
    return pd.DataFrame(
        {
            "open": close + rng.normal(0, 0.005, 300) * close,
            "high": close + spread,
            "low": close - spread,
            "close": close,
            "volume": rng.integers(1, 1000, 300).astype(float),
        },
        index=pd.date_range("2020-01-01", periods=300, freq="D"),
    ).pipe(lambda d: d.assign(
        high=d[["open", "high", "close"]].max(axis=1),
        low=d[["open", "low", "close"]].min(axis=1),
    ))


# --------------------------------------------------------------------------
# semantiche calcolate a mano
# --------------------------------------------------------------------------

def test_rma_innesca_con_la_sma_non_col_primo_valore():
    out = ind.rma(pd.Series([1.0, 2, 3, 4, 5, 6]), 3)
    assert np.isnan(out.iloc[1])
    assert out.iloc[2] == pytest.approx(2.0)            # SMA di [1,2,3]
    assert out.iloc[3] == pytest.approx(4 / 3 + 4 / 3)  # 1/3*4 + 2/3*2
    assert out.iloc[4] == pytest.approx(5 / 3 + 2 / 3 * (8 / 3))
    assert out.iloc[5] == pytest.approx(4.29629629, rel=1e-6)


def test_true_range_prima_barra(small):
    tr_handled = ind.true_range(small, handle_na=True)
    assert tr_handled.iloc[0] == pytest.approx(2.0)     # high - low
    assert np.isnan(ind.true_range(small, handle_na=False).iloc[0])
    assert tr_handled.iloc[3] == pytest.approx(4.0)


def test_atr_usa_rma_non_sma(small):
    out = ind.atr(small, 3)
    assert out.iloc[2] == pytest.approx(2.0)          # SMA dei primi 3 TR
    assert out.iloc[3] == pytest.approx(8 / 3)        # 2/3*2 + 1/3*4
    # sulla quinta barra le due formule divergono: RMA 22/9, SMA dei 3 TR 8/3
    assert out.iloc[4] == pytest.approx(22 / 9)
    sma_tr = ind.sma(ind.true_range(small), 3)
    assert out.iloc[4] != pytest.approx(sma_tr.iloc[4])


def test_donchian_include_la_barra_corrente(small):
    out = ind.donchian_mid(small, 3)
    assert out.iloc[2] == pytest.approx((12 + 8) / 2)
    assert out.iloc[3] == pytest.approx((15 + 9) / 2)


def test_crossover():
    a = pd.Series([1.0, 2.0, 3.0])
    b = pd.Series([2.0, 2.0, 2.0])
    assert ind.crossover(a, b).tolist() == [False, False, True]
    assert ind.crossunder(b, a).tolist() == [False, False, True]


# --------------------------------------------------------------------------
# la nuvola e' passata, non futura
# --------------------------------------------------------------------------

def test_nuvola_corrente_calcolata_disp_barre_fa(walk):
    disp = 26
    out = ind.ichimoku(walk, disp=disp)
    # Senkou B ha bisogno di 52 barre, poi altre 26 di proiezione: prima della
    # barra 78 il confronto sarebbe fra due NaN e non proverebbe nulla
    for t in (100, 180, 250):
        assert out["span_a_now"].iloc[t] == pytest.approx(out["senkou_a"].iloc[t - disp])
        assert out["span_b_now"].iloc[t] == pytest.approx(out["senkou_b"].iloc[t - disp])
        assert not np.isnan(out["span_b_now"].iloc[t])


def test_chikou_confronta_il_massimo_di_disp_barre_fa(walk):
    out = ind.ichimoku(walk, disp=26)
    t = 100
    atteso = walk["close"].iloc[t] > walk["high"].iloc[t - 26]
    assert bool(out["chikou_clear"].iloc[t]) == bool(atteso)


# --------------------------------------------------------------------------
# nessun lookahead
# --------------------------------------------------------------------------

@pytest.mark.parametrize("t", [150, 200, 299])
def test_nessun_indicatore_guarda_avanti(walk, t):
    """Il valore sulla barra t non deve cambiare se le barre future spariscono."""
    troncata = walk.iloc[: t + 1]

    piena_ichi, tronca_ichi = ind.ichimoku(walk), ind.ichimoku(troncata)
    for col in ("tenkan", "kijun", "senkou_a", "senkou_b", "cloud_top", "cloud_bot"):
        assert piena_ichi[col].iloc[t] == pytest.approx(tronca_ichi[col].iloc[t]), col
    for col in ("price_above", "chikou_clear", "tk_bull", "tk_cross_up"):
        assert bool(piena_ichi[col].iloc[t]) == bool(tronca_ichi[col].iloc[t]), col

    assert ind.atr(walk).iloc[t] == pytest.approx(ind.atr(troncata).iloc[t])

    piena_dmi, tronca_dmi = ind.dmi(walk), ind.dmi(troncata)
    for col in ("di_plus", "di_minus", "adx"):
        assert piena_dmi[col].iloc[t] == pytest.approx(tronca_dmi[col].iloc[t]), col


def test_adx_resta_nel_dominio(walk):
    out = ind.dmi(walk).dropna()
    assert not out.empty
    assert (out["adx"] >= 0).all() and (out["adx"] <= 100).all()
    assert (out["di_plus"] >= 0).all() and (out["di_minus"] >= 0).all()
