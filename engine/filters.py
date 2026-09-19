"""Filtri direzionali da innestare su una strategia base.

Ogni filtro restituisce due serie booleane — se è consentito aprire long e se è
consentito aprire short su quella barra — e non genera segnali propri. Serve a
rispondere a una domanda sola: *questo componente aggiunge qualcosa a un trend
follower che già funziona?*

I filtri Gann implementano le uniche due ipotesi sopravvissute alla ricognizione
della letteratura (`research/state-of-the-art.md`):

* **angolo 1×1 normalizzato in ATR per barra.** "Un punto per barra" è
  dimensionalmente incoerente e non trasferibile fra strumenti; misurando la
  pendenza in ATR per barra diventa adimensionale e confrontabile fra BTC e
  mais. Le soglie testate sono i rapporti di Gann stessi (1×1, 1×2, 1×4, 1×8),
  non numeri scelti da noi.
* **ottavi in log-price** su un range ancorato meccanicamente (massimo e minimo
  a 252 barre). In prezzo lineare un ottavo significa cose diverse a prezzi
  diversi; in logaritmo no. Il controllo `mid_lineare` serve proprio a
  verificare se il logaritmo cambia qualcosa.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators as ind
from .strategies.confluence import htf_blocks

Filter = tuple[pd.Series, pd.Series]  # (long consentito, short consentito)

ANCHOR_LEN = 252   # 52 settimane
SLOPE_LEN = 26     # periodo del Kijun, non un valore scelto da noi
AVWAP_LOOKBACK = 50   # default dichiarato dall'autore di IQ-DAS, non scelto da noi


def _all(df: pd.DataFrame, value: bool = True) -> pd.Series:
    return pd.Series(value, index=df.index)


# --------------------------------------------------------------------------
# Ichimoku
# --------------------------------------------------------------------------

def ichi_cloud(df: pd.DataFrame) -> Filter:
    """Prezzo fuori dalla nuvola, nella direzione del trade."""
    ichi = ind.ichimoku(df)
    return ichi["price_above"].fillna(False), ichi["price_below"].fillna(False)


def ichi_tk(df: pd.DataFrame) -> Filter:
    """Tenkan sopra o sotto Kijun."""
    ichi = ind.ichimoku(df)
    return ichi["tk_bull"].fillna(False), (~ichi["tk_bull"]).fillna(False)


def ichi_chikou(df: pd.DataFrame) -> Filter:
    """Chikou libero: close oltre il massimo (o minimo) di 26 barre fa."""
    up = df["close"] > df["high"].shift(26)
    dn = df["close"] < df["low"].shift(26)
    return up.fillna(False), dn.fillna(False)


def ichi_thick(df: pd.DataFrame) -> Filter:
    """Nuvola spessa almeno mezzo ATR — filtro non direzionale."""
    ichi = ind.ichimoku(df)
    thick = (ichi["span_a_now"] - ichi["span_b_now"]).abs() >= 0.5 * ind.atr(df, 14)
    thick = thick.fillna(False)
    return thick, thick


def ichi_htf(df: pd.DataFrame) -> Filter:
    """Regime della nuvola sul timeframe superiore (blocchi di 5 barre)."""
    regime = htf_blocks(df, 5)["regime"]
    return (regime == 1).fillna(False), (regime == -1).fillna(False)


def ichi_full(df: pd.DataFrame) -> Filter:
    """Nuvola + TK + Chikou insieme: il nucleo dell'impostazione Ichimoku."""
    parts = [ichi_cloud(df), ichi_tk(df), ichi_chikou(df)]
    longs = parts[0][0] & parts[1][0] & parts[2][0]
    shorts = parts[0][1] & parts[1][1] & parts[2][1]
    return longs, shorts


# --------------------------------------------------------------------------
# Gann
# --------------------------------------------------------------------------

def _gann_slope(df: pd.DataFrame, ratio: float) -> Filter:
    """Pendenza su ``SLOPE_LEN`` barre misurata in ATR per barra.

    La linea 1×1 diventa "un ATR per barra": adimensionale, quindi la stessa
    condizione su ogni strumento.
    """
    atr = ind.atr(df, 14)
    slope = (df["close"] - df["close"].shift(SLOPE_LEN)) / (SLOPE_LEN * atr)
    return (slope >= ratio).fillna(False), (slope <= -ratio).fillna(False)


def gann_1x1(df: pd.DataFrame) -> Filter:
    return _gann_slope(df, 1.0)


def gann_1x2(df: pd.DataFrame) -> Filter:
    return _gann_slope(df, 0.5)


def gann_1x4(df: pd.DataFrame) -> Filter:
    return _gann_slope(df, 0.25)


def gann_1x8(df: pd.DataFrame) -> Filter:
    return _gann_slope(df, 0.125)


def _octave(df: pd.DataFrame, level: float, log_scale: bool = True) -> Filter:
    """Posizione entro il range ancorato, diviso in ottavi.

    L'àncora è meccanica — massimo e minimo a 252 barre — perché è l'unico modo
    di rendere Gann testabile: scegliendo l'àncora a posteriori qualunque
    risultato è ottenibile.
    """
    price = np.log(df["close"]) if log_scale else df["close"]
    hi = price.rolling(ANCHOR_LEN).max()
    lo = price.rolling(ANCHOR_LEN).min()
    threshold = lo + (hi - lo) * level
    mirror = lo + (hi - lo) * (1 - level)
    return (price > threshold).fillna(False), (price < mirror).fillna(False)


def gann_oct_4_8(df: pd.DataFrame) -> Filter:
    """Metà del range, in log-price."""
    return _octave(df, 0.500)


def gann_oct_5_8(df: pd.DataFrame) -> Filter:
    """5/8 = 62.5%, l'ottavo a cui Gann attribuiva più peso."""
    return _octave(df, 0.625)


def ctrl_mid_lineare(df: pd.DataFrame) -> Filter:
    """Controllo: stesso 4/8 ma in prezzo lineare, per isolare l'effetto del log."""
    return _octave(df, 0.500, log_scale=False)


# --------------------------------------------------------------------------
# AVWAP ancorato — ipotesi pre-registrata in results/prereg_peak_avwap.md
# --------------------------------------------------------------------------

def _anchored_vwap(df: pd.DataFrame, lookback: int = AVWAP_LOOKBACK
                   ) -> tuple[pd.Series, pd.Series]:
    """VWAP ancorate all'estremo della finestra precedente.

    Restituisce ``(peak_avwap, trough_avwap)``: la prima ancorata alla barra del
    massimo, la seconda a quella del minimo, entrambe cercate nelle ``lookback``
    barre che terminano in ``t-1``.

    La finestra è spostata di una barra per la stessa ragione dei canali di
    Donchian: se l'àncora potesse essere la barra su cui si decide, la
    condizione sarebbe in parte autoreferenziale — e sulla barra di rottura
    l'àncora *sarebbe* sempre quella barra, rendendo la media un punto solo.

    A parità di massimo vince la barra più vecchia (``argmax`` restituisce la
    prima): è una convenzione, dichiarata perché nei plateau cambia l'àncora.
    """
    high, low = df["high"].to_numpy(float), df["low"].to_numpy(float)
    tp = ((df["high"] + df["low"] + df["close"]) / 3.0).to_numpy(float)
    vol = df["volume"].to_numpy(float)

    # somme cumulate con uno zero davanti: la somma su [o, t] è cum[t+1]-cum[o]
    cum_pv = np.concatenate(([0.0], np.cumsum(tp * vol)))
    cum_v = np.concatenate(([0.0], np.cumsum(vol)))

    n = len(df)
    peak = np.full(n, np.nan)
    trough = np.full(n, np.nan)
    for t in range(lookback, n):
        start = t - lookback
        origins = (start + int(np.argmax(high[start:t])),
                   start + int(np.argmin(low[start:t])))
        for origin, out in zip(origins, (peak, trough)):
            volume = cum_v[t + 1] - cum_v[origin]
            if volume > 0:
                out[t] = (cum_pv[t + 1] - cum_pv[origin]) / volume

    return pd.Series(peak, index=df.index), pd.Series(trough, index=df.index)


def peak_avwap(df: pd.DataFrame) -> Filter:
    """Il prezzo ha riconquistato l'AVWAP ancorato all'estremo precedente?

    È l'unica componente di `IQ Dual Anchor Setup [IQ-TRADER]` che non ricada in
    una famiglia già misurata qui: a differenza di Ichimoku e Gann guarda i
    **volumi reali**, non solo la geometria del prezzo. Ipotesi singola,
    dichiarata prima del test in `results/prereg_peak_avwap.md`.

    Simmetrica per costruzione: long sopra l'AVWAP del massimo, short sotto
    quella del minimo — in entrambi i casi ci si ancora all'estremo da cui si
    riparte.
    """
    peak, trough = _anchored_vwap(df)
    return (df["close"] > peak).fillna(False), (df["close"] < trough).fillna(False)


# --------------------------------------------------------------------------
# indicatori occidentali, come termine di paragone
# --------------------------------------------------------------------------

def adx_15(df: pd.DataFrame) -> Filter:
    """ADX >= 15, la soglia usata dalla v3.2."""
    ok = (ind.dmi(df, 14, 14)["adx"] >= 15.0).fillna(False)
    return ok, ok


def sma_200(df: pd.DataFrame) -> Filter:
    """Prezzo sopra o sotto la media a 200: il filtro di trend più banale."""
    sma = ind.sma(df["close"], 200)
    return (df["close"] > sma).fillna(False), (df["close"] < sma).fillna(False)


CATALOGUE = {
    "ichi_cloud": ichi_cloud,
    "ichi_tk": ichi_tk,
    "ichi_chikou": ichi_chikou,
    "ichi_thick": ichi_thick,
    "ichi_htf": ichi_htf,
    "ichi_full": ichi_full,
    "gann_1x1": gann_1x1,
    "gann_1x2": gann_1x2,
    "gann_1x4": gann_1x4,
    "gann_1x8": gann_1x8,
    "gann_oct_4_8": gann_oct_4_8,
    "gann_oct_5_8": gann_oct_5_8,
    "ctrl_mid_lineare": ctrl_mid_lineare,
    "peak_avwap": peak_avwap,
    "adx_15": adx_15,
    "sma_200": sma_200,
}
