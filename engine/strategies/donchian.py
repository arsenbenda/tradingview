"""Benchmark: breakout di Donchian, parametri Turtle non ottimizzati.

Questa è la barra che Ichimoku + Gann devono superare. Il punto non è che sia
una buona strategia, ma che sia **la più banale possibile fra quelle che
catturano un trend**: se una macchina a 53 input non batte cinquanta righe con
parametri pubblicati negli anni Ottanta, la complessità non si giustifica.

Parametri: sistema Turtle "System 2" — ingresso sul breakout a 55 barre, uscita
sul canale a 20, stop a 2×ATR(20), rischio 1% per trade. Sono **pubblicati e
precedenti a questo lavoro**, quindi il benchmark non gode di alcun vantaggio di
adattamento ai dati: è una scelta deliberata, per rendere il confronto onesto.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import indicators as ind
from ..backtest import Intent, Strategy

ENTRY_LEN = 55
EXIT_LEN = 20
ATR_LEN = 20
STOP_ATR = 2.0


def signals(
    df: pd.DataFrame,
    *,
    entry_len: int = ENTRY_LEN,
    exit_len: int = EXIT_LEN,
    atr_len: int = ATR_LEN,
    stop_atr: float = STOP_ATR,
    allow_short: bool = True,
) -> dict[str, pd.Series]:
    """Segnali Donchian.

    I canali sono spostati di una barra: il breakout si misura contro il massimo
    delle ``entry_len`` barre **precedenti**, non contro una finestra che
    contiene la barra stessa — altrimenti la condizione sarebbe in parte
    autoreferenziale.
    """
    hi_entry = df["high"].rolling(entry_len).max().shift(1)
    lo_entry = df["low"].rolling(entry_len).min().shift(1)
    hi_exit = df["high"].rolling(exit_len).max().shift(1)
    lo_exit = df["low"].rolling(exit_len).min().shift(1)
    atr = ind.atr(df, atr_len)

    empty = pd.Series(False, index=df.index)
    return {
        "entry_long": df["close"] > hi_entry,
        "exit_long": df["close"] < lo_exit,
        "entry_short": (df["close"] < lo_entry) if allow_short else empty,
        "exit_short": (df["close"] > hi_exit) if allow_short else empty,
        "stop_distance": stop_atr * atr,
    }


class DonchianWithExit(Strategy):
    """Ingressi Donchian invariati, meccanismo di uscita sostituibile.

    Serve a isolare l'ultima ipotesi Ichimoku rimasta: il trail sulla nuvola e
    sul Kijun è l'unico pezzo delle strategie Pine che non compete con il
    breakout — lo gestisce dopo. Gli ingressi restano identici al benchmark,
    così la differenza misurata è attribuibile solo all'uscita.

    Modalità: ``canale`` (il 20 barre del benchmark), ``kijun_trail``,
    ``cloud_trail``, ``cloud_exit`` (uscita quando il prezzo rientra nella
    nuvola), ``kijun_cross``.
    """

    EXIT_MODES = ("canale", "kijun_trail", "cloud_trail", "cloud_exit", "kijun_cross")

    def __init__(self, *, exit_mode: str = "canale", entry_len: int = ENTRY_LEN,
                 exit_len: int = EXIT_LEN, atr_len: int = ATR_LEN, stop_atr: float = STOP_ATR):
        if exit_mode not in self.EXIT_MODES:
            raise ValueError(f"exit_mode deve essere uno di {self.EXIT_MODES}")
        self.exit_mode = exit_mode
        self.entry_len, self.exit_len = entry_len, exit_len
        self.atr_len, self.stop_atr = atr_len, stop_atr

    def prepare(self, df):
        sig = signals(df, entry_len=self.entry_len, exit_len=self.exit_len,
                      atr_len=self.atr_len, stop_atr=self.stop_atr)
        ichi = ind.ichimoku(df)
        self.d = {
            "e_long": sig["entry_long"].fillna(False).to_numpy(bool),
            "e_short": sig["entry_short"].fillna(False).to_numpy(bool),
            "x_long": sig["exit_long"].fillna(False).to_numpy(bool),
            "x_short": sig["exit_short"].fillna(False).to_numpy(bool),
            "stop": sig["stop_distance"].to_numpy(float),
            "close": df["close"].to_numpy(float),
            "kijun": ichi["kijun"].to_numpy(float),
            "cloud_top": ichi["cloud_top"].to_numpy(float),
            "cloud_bot": ichi["cloud_bot"].to_numpy(float),
            "above": ichi["price_above"].fillna(False).to_numpy(bool),
            "below": ichi["price_below"].fillna(False).to_numpy(bool),
        }

    def entry(self, state):
        i, d = state.i, self.d
        if d["e_long"][i]:
            return Intent(1, d["stop"][i], tag="L")
        if d["e_short"][i]:
            return Intent(-1, d["stop"][i], tag="S")
        return None

    def manage(self, state):
        i, d = state.i, self.d
        long_ = state.direction > 0
        mode = self.exit_mode

        if mode == "canale":
            return (d["x_long"][i] if long_ else d["x_short"][i]), None

        if mode == "kijun_trail":
            k = d["kijun"][i]
            return False, (k if np.isfinite(k) else None)

        if mode == "cloud_trail":
            level = d["cloud_bot"][i] if long_ else d["cloud_top"][i]
            return False, (level if np.isfinite(level) else None)

        if mode == "cloud_exit":
            # esce quando il prezzo rientra nella nuvola (perde il lato)
            return (not d["above"][i]) if long_ else (not d["below"][i]), None

        # kijun_cross
        k = d["kijun"][i]
        if not np.isfinite(k):
            return False, None
        return (d["close"][i] < k) if long_ else (d["close"][i] > k), None
