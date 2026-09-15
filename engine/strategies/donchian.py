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

import pandas as pd

from .. import indicators as ind

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
