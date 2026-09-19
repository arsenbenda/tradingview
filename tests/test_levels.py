"""Test del motore dei livelli.

Il test che conta è il secondo: `recent_range` cerca gli estremi di pivot, e un
pivot è confermato *guardando avanti* di k barre. È la costruzione in cui il
lookahead si nasconde meglio di qualunque altra, perché sul grafico storico non si
vede: il livello sembra semplicemente sempre al posto giusto.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine import indicators as ind, levels as L


@pytest.fixture
def serie() -> pd.DataFrame:
    rng = np.random.default_rng(3)
    n = 400
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.02, n)))
    spread = np.abs(rng.normal(0, 0.012, n)) * close
    df = pd.DataFrame(
        {"open": close, "high": close + spread, "low": close - spread,
         "close": close, "volume": 1.0},
        index=pd.date_range("2021-01-01", periods=n, freq="D"),
    )
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    return df


def test_un_pivot_frattale_e_il_massimo_della_sua_finestra(serie):
    top, bot = L.fractal_pivots(serie, 10)
    h, l = serie["high"].to_numpy(float), serie["low"].to_numpy(float)
    assert len(top) and len(bot)
    for i in top:
        assert h[i] == h[i - 10:i + 11].max()
    for i in bot:
        assert l[i] == l[i - 10:i + 11].min()


@pytest.mark.parametrize("t", [150, 250, 399])
def test_il_range_non_cambia_se_il_futuro_sparisce(serie, t):
    """La proprietà senza la quale tutto il test sarebbe finto."""
    hi_p, lo_p = L.recent_range(serie, 20)
    hi_t, lo_t = L.recent_range(serie.iloc[: t + 1], 20)
    for piena, tronca in ((hi_p, hi_t), (lo_p, lo_t)):
        a, b = piena.iloc[t], tronca.iloc[t]
        assert (np.isnan(a) and np.isnan(b)) or a == pytest.approx(b)


def test_il_range_usa_solo_pivot_gia_confermati(serie):
    """Il pivot sulla barra i non può comparire prima della barra i+k."""
    k = 20
    top, _ = L.fractal_pivots(serie, k)
    hi, _ = L.recent_range(serie, k)
    h = serie["high"].to_numpy(float)
    for i in top:
        if i + k - 1 < len(serie):
            precedenti = hi.iloc[: i + k]          # fino alla barra prima
            assert not (precedenti == h[i]).any() or (h[:i] == h[i]).any()


def test_le_famiglie_di_ottavi_sono_ordinate(serie):
    fam = L.level_families(serie, 20)
    ok = fam["gann_1_8"].notna()
    for n in range(1, 7):
        a, b = fam[f"gann_{n}_8"][ok], fam[f"gann_{n+1}_8"][ok]
        assert (a <= b + 1e-9).all(), f"{n}/8 deve stare sotto {n+1}/8"


def test_gli_eventi_di_tocco_rispettano_la_pausa_minima(serie):
    fam = L.level_families(serie, 20)
    ev, d = L.touch_events(serie, fam["kijun"], min_gap=5)
    assert len(ev) > 10
    assert (np.diff(ev) > 5).all()
    assert set(np.unique(d)) <= {-1, 1}


def test_la_direzione_e_quella_della_barra_precedente(serie):
    fam = L.level_families(serie, 20)
    lv = fam["kijun"].to_numpy(float)
    close = serie["close"].to_numpy(float)
    ev, d = L.touch_events(serie, fam["kijun"])
    for t, direz in zip(ev, d):
        atteso = 1 if close[t - 1] < lv[t] else -1
        assert direz == atteso


def test_la_corsa_riconosce_rifiuto_rottura_e_censura():
    """Tre casi costruiti a mano, con il livello a 100 e barriere a 1.

    Resistenza (si arriva da sotto): scendere a 99 è un rifiuto, salire a 101 una
    rottura, restare fra i due è una censura.
    """
    def caso(percorso):
        n = len(percorso) + 2
        idx = pd.date_range("2024-01-01", periods=n, freq="D")
        close = np.r_[99.5, 100.0, percorso]
        df = pd.DataFrame({"open": close, "high": close + 0.01,
                           "low": close - 0.01, "close": close,
                           "volume": 1.0}, index=idx)
        livello = pd.Series(100.0, index=idx)
        atr = pd.Series(1.0, index=idx)
        return L.race(df, livello, np.array([1]), np.array([1]), atr,
                      barrier_atr=1.0, horizon=10)[0]

    assert caso([99.9, 98.8, 100.2]) == L.REJECT     # scende a 98.8 prima
    assert caso([100.1, 101.5, 98.0]) == L.BREAK     # sale a 101.5 prima
    assert caso([100.1, 99.9, 100.2]) == L.CENSORED  # non esce dalla banda


def test_il_placebo_resta_nei_limiti_dichiarati(serie):
    fam = L.level_families(serie, 20)
    atr = ind.atr(serie, L.ATR_LEN)
    lv = fam["cloud_top"]
    for p in L.placebo_levels(lv, atr, n=5, seed=1):
        scarto = ((p - lv) / atr).dropna()
        assert scarto.std() < 1e-9, "lo scostamento deve essere costante"
        assert L.SHIFT_MIN - 1e-9 <= abs(scarto.iloc[0]) <= L.SHIFT_MAX + 1e-9
