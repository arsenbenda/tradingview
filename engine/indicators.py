"""Indicatori con semantica Pine Script, replicata esattamente.

Il porting fedele conta più dell'eleganza: se questo modulo e il Pine divergono,
ogni numero prodotto dal backtest descrive una strategia diversa da quella che
verrà deployata. Ogni funzione documenta la primitiva Pine di cui è la
traduzione, e le differenze che di solito vengono sbagliate sono annotate.

Trappole note, tutte gestite qui:

* ``ta.atr`` usa RMA (smoothing di Wilder, alpha = 1/len), non una media
  semplice. Usare una SMA produce un ATR sistematicamente diverso, quindi stop
  e sizing diversi.
* ``ta.rma`` non parte dal primo valore: viene innescata con la SMA dei primi
  ``length`` valori e da lì ricorre.
* ``ta.tr(true)`` sulla prima barra vale ``high - low``; ``ta.tr`` senza
  argomento vale NaN, perché ``close[1]`` non esiste.
* ``ta.highest(src, len)`` include la barra corrente.
* La nuvola disegnata sulla barra corrente è calcolata ``disp`` barre fa:
  ``senkouA[disp]``. Sbagliare il verso dello shift introduce lookahead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "sma", "ema", "rma", "true_range", "atr", "donchian_mid",
    "ichimoku", "crossover", "crossunder", "change", "dmi", "rolling_sum",
]


# --------------------------------------------------------------------------
# medie
# --------------------------------------------------------------------------

def sma(src: pd.Series, length: int) -> pd.Series:
    """``ta.sma``: media mobile semplice."""
    return src.rolling(length).mean()


def rma(src: pd.Series, length: int) -> pd.Series:
    """``ta.rma``: smoothing di Wilder, alpha = 1/length.

    Pine innesca la ricorsione con la SMA dei primi ``length`` valori validi,
    non con il primo valore. La differenza non sparisce con le barre: sposta
    tutta la serie.
    """
    values = src.to_numpy(dtype=float)
    out = np.full(values.shape, np.nan)

    valid = ~np.isnan(values)
    if valid.sum() < length:
        return pd.Series(out, index=src.index)

    # prima posizione con `length` valori validi consecutivi disponibili
    first = np.flatnonzero(np.cumsum(valid) >= length)[0]
    out[first] = np.nanmean(values[: first + 1][-length:])

    alpha = 1.0 / length
    for i in range(first + 1, len(values)):
        if np.isnan(values[i]):
            out[i] = out[i - 1]
        else:
            out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return pd.Series(out, index=src.index)


def ema(src: pd.Series, length: int) -> pd.Series:
    """``ta.ema``: alpha = 2/(length+1), innescata con la SMA."""
    values = src.to_numpy(dtype=float)
    out = np.full(values.shape, np.nan)
    if len(values) < length:
        return pd.Series(out, index=src.index)

    out[length - 1] = values[:length].mean()
    alpha = 2.0 / (length + 1)
    for i in range(length, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return pd.Series(out, index=src.index)


# --------------------------------------------------------------------------
# volatilita'
# --------------------------------------------------------------------------

def true_range(df: pd.DataFrame, handle_na: bool = True) -> pd.Series:
    """``ta.tr(handle_na)``.

    Con ``handle_na=True`` la prima barra vale ``high - low``; con ``False``
    vale NaN, perche' ``close[1]`` non esiste.
    """
    prev_close = df["close"].shift(1)
    hl = df["high"] - df["low"]
    tr = pd.concat(
        [hl, (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    if handle_na:
        tr = tr.where(prev_close.notna(), hl)
    else:
        tr = tr.where(prev_close.notna(), np.nan)
    return tr


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """``ta.atr(length)`` = ``ta.rma(ta.tr(true), length)``."""
    return rma(true_range(df, handle_na=True), length)


# --------------------------------------------------------------------------
# Ichimoku
# --------------------------------------------------------------------------

def donchian_mid(df: pd.DataFrame, length: int) -> pd.Series:
    """Punto medio del canale: ``(highest(high, len) + lowest(low, len)) / 2``.

    E' la primitiva su cui poggiano Tenkan, Kijun e Senkou B. La finestra
    include la barra corrente, come ``ta.highest`` in Pine.
    """
    return (df["high"].rolling(length).max() + df["low"].rolling(length).min()) / 2.0


def ichimoku(
    df: pd.DataFrame,
    tenkan_len: int = 9,
    kijun_len: int = 26,
    senkou_b_len: int = 52,
    disp: int = 26,
) -> pd.DataFrame:
    """Componenti Ichimoku allineate alla barra corrente.

    Restituisce ``tenkan``, ``kijun``, ``senkou_a``, ``senkou_b`` (valori
    calcolati sulla barra corrente, cioe' quelli che in Pine verrebbero
    *proiettati* in avanti di ``disp``), piu' ``cloud_top`` e ``cloud_bot``,
    che sono i valori proiettati ``disp`` barre fa e quindi **validi da usare
    ora**. E' la distinzione che separa un backtest corretto da uno con
    lookahead.

    ``chikou_clear`` replica il test classico ``close > high[disp]``.
    """
    tenkan = donchian_mid(df, tenkan_len)
    kijun = donchian_mid(df, kijun_len)
    senkou_a = (tenkan + kijun) / 2.0
    senkou_b = donchian_mid(df, senkou_b_len)

    # la nuvola sopra la barra corrente e' stata calcolata disp barre fa
    span_a_now = senkou_a.shift(disp)
    span_b_now = senkou_b.shift(disp)

    out = pd.DataFrame(
        {
            "tenkan": tenkan,
            "kijun": kijun,
            "senkou_a": senkou_a,
            "senkou_b": senkou_b,
            "span_a_now": span_a_now,
            "span_b_now": span_b_now,
            "cloud_top": pd.concat([span_a_now, span_b_now], axis=1).max(axis=1),
            "cloud_bot": pd.concat([span_a_now, span_b_now], axis=1).min(axis=1),
        },
        index=df.index,
    )
    out["cloud_bull"] = span_a_now > span_b_now
    out["price_above"] = df["close"] > out["cloud_top"]
    out["price_below"] = df["close"] < out["cloud_bot"]
    out["chikou_clear"] = df["close"] > df["high"].shift(disp)
    out["tk_bull"] = tenkan > kijun
    out["tk_cross_up"] = crossover(tenkan, kijun)
    out["tk_cross_down"] = crossunder(tenkan, kijun)
    return out


# --------------------------------------------------------------------------
# utilita'
# --------------------------------------------------------------------------

def crossover(a: pd.Series, b: pd.Series) -> pd.Series:
    """``ta.crossover(a, b)``: vero quando a supera b su questa barra."""
    return (a > b) & (a.shift(1) <= b.shift(1))


def crossunder(a: pd.Series, b: pd.Series) -> pd.Series:
    """``ta.crossunder(a, b)``."""
    return (a < b) & (a.shift(1) >= b.shift(1))


def change(src: pd.Series, length: int = 1) -> pd.Series:
    """``ta.change``."""
    return src - src.shift(length)


def rolling_sum(src: pd.Series, length: int) -> pd.Series:
    """``math.sum``."""
    return src.rolling(length).sum()


def dmi(df: pd.DataFrame, di_len: int = 14, adx_len: int = 14) -> pd.DataFrame:
    """``ta.dmi(di_len, adx_len)`` -> colonne ``di_plus``, ``di_minus``, ``adx``.

    Segue la definizione Pine riga per riga, incluso il denominatore posto a 1
    quando ``di_plus + di_minus`` e' zero.
    """
    up = change(df["high"])
    down = -change(df["low"])

    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    plus_dm = pd.Series(plus_dm, index=df.index).where(up.notna(), np.nan)
    minus_dm = pd.Series(minus_dm, index=df.index).where(down.notna(), np.nan)

    trur = rma(true_range(df, handle_na=False), di_len)
    di_plus = 100 * rma(plus_dm, di_len) / trur
    di_minus = 100 * rma(minus_dm, di_len) / trur

    total = di_plus + di_minus
    dx = (di_plus - di_minus).abs() / total.where(total != 0, 1.0)
    adx = 100 * rma(dx, adx_len)

    return pd.DataFrame({"di_plus": di_plus, "di_minus": di_minus, "adx": adx})
