"""Test delle strategie portate dal Pine.

Il rischio maggiore di un porting è che il regime di timeframe superiore usi la
settimana in corso invece dell'ultima chiusa. È informazione che alla data del
segnale non esiste, e regala alla strategia una capacità predittiva finta.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.strategies.sanyaku import SanyakuV55, htf_weekly


@pytest.fixture
def daily() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    n = 400
    close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, n)))
    spread = np.abs(rng.normal(0, 0.01, n)) * close
    df = pd.DataFrame(
        {"open": close, "high": close + spread, "low": close - spread,
         "close": close, "volume": 1.0},
        index=pd.date_range("2022-01-03", periods=n, freq="D"),
    )
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    return df


def test_htf_usa_la_settimana_chiusa_non_quella_in_corso(daily):
    htf = htf_weekly(daily)
    weekly = daily.resample("W").agg({"open": "first", "high": "max", "low": "min",
                                      "close": "last", "volume": "sum"}).dropna()
    # un giorno a metà della terza settimana deve vedere la chiusura della seconda
    giorno = weekly.index[2] - pd.Timedelta(days=3)
    atteso = weekly["close"].iloc[1]
    assert htf.loc[giorno, "htf_close"] == pytest.approx(atteso)
    # e non la chiusura della settimana in cui si trova
    assert htf.loc[giorno, "htf_close"] != pytest.approx(weekly["close"].iloc[2])


@pytest.mark.parametrize("t", [200, 300, 399])
def test_htf_non_cambia_se_il_futuro_sparisce(daily, t):
    piena = htf_weekly(daily)
    tronca = htf_weekly(daily.iloc[: t + 1])
    for col in ("htf_close", "htf_kijun"):
        a, b = piena[col].iloc[t], tronca[col].iloc[t]
        assert (np.isnan(a) and np.isnan(b)) or a == pytest.approx(b), col


def test_sanyaku_non_apre_senza_indicatori_pronti(daily):
    strat = SanyakuV55()
    strat.prepare(daily)
    from engine.backtest import State

    # nelle prime 78 barre Senkou B e la sua proiezione non esistono ancora
    for i in range(0, 70):
        assert strat.entry(State(i=i, cash=100_000.0, equity=100_000.0)) is None


def test_il_cooldown_blocca_e1_ma_non_e4(daily):
    """Entry 4 aggira cooldown e zone lock: e' il default del Pine.

    Il test fissa il comportamento perche' e' rischioso, non perche' sia giusto:
    e' l'unico ingresso che puo' scattare subito dopo un'uscita, ed e' il
    meccanismo con cui in un regime di whipsaw si concatenano le perdite.
    """
    from engine.backtest import State

    idx_kwargs = dict(cash=100_000.0, equity=100_000.0)

    solo_e1 = SanyakuV55(enabled_entries=(1,))
    solo_e1.prepare(daily)
    idx = int(np.flatnonzero(solo_e1.d["e1"] & solo_e1.d["htf_ok"])[0])
    assert solo_e1.entry(State(i=idx, closed_trades=0, **idx_kwargs)) is not None

    solo_e1.prepare(daily)
    bloccato = State(i=idx, closed_trades=1, last_exit_index=idx - 2, **idx_kwargs)
    assert solo_e1.entry(bloccato) is None          # cooldown rispettato

    tutte = SanyakuV55()
    tutte.prepare(daily)
    passa = tutte.entry(State(i=idx, closed_trades=1, last_exit_index=idx - 2, **idx_kwargs))
    assert passa is not None and passa.tag == "E4"   # E4 entra comunque


def test_i_filtri_rispettano_il_contratto(daily):
    """Ogni filtro deve restituire due serie booleane allineate all'indice."""
    from engine import filters

    for nome, fn in filters.CATALOGUE.items():
        allow_long, allow_short = fn(daily)
        assert list(allow_long.index) == list(daily.index), nome
        assert list(allow_short.index) == list(daily.index), nome
        assert allow_long.dtype == bool and allow_short.dtype == bool, nome


def test_la_pendenza_gann_1x1_non_e_raggiungibile(daily):
    """Il prezzo diffonde come radice del tempo, la retta 1x1 cresce come il tempo.

    Normalizzata in ATR per barra, la 1x1 non viene mai attraversata: e' una
    proprieta' della scala, non del mercato. Il test fissa il fatto che rende
    l'angolo inutilizzabile come soglia.
    """
    from engine import filters, indicators as ind

    atr = ind.atr(daily, 14)
    slope = ((daily["close"] - daily["close"].shift(26)) / (26 * atr)).dropna()
    assert slope.abs().max() < 1.0

    allow_long, allow_short = filters.gann_1x1(daily)
    assert not (allow_long | allow_short).any()
