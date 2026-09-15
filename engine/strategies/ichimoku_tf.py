"""Ichimoku come generatore di segnale autonomo, simmetrico long/short.

Buco lasciato aperto dai test precedenti: l'ablazione usa Ichimoku come
*filtro* sopra un breakout, la v5.5 è long-only e la v3.2 ha gli short gatati da
SMA e soglie asimmetriche. Nessuno dei tre risponde alla domanda più semplice —
**un Ichimoku simmetrico, usato come segnale e non come filtro, batte il
benchmark?**

Per isolare il segnale, tutto il resto è identico al benchmark Donchian: stesso
stop (2×ATR(20)), stesso rischio per trade, stessi costi, stesso motore. L'unica
cosa che cambia è *cosa decide di entrare*.

Tre varianti canoniche, nessuna inventata qui:

``cloud``    rottura della nuvola — il segnale Ichimoku più usato
``tk``       incrocio Tenkan/Kijun, con la nuvola come conferma di direzione
``sanyaku``  i tre segnali allineati (prezzo fuori dalla nuvola, TK a favore,
             Chikou libero): è il "Sanyaku Kouten/Gyakuten" della v3.2, ma
             simmetrico e senza score
"""

from __future__ import annotations

import pandas as pd

from .. import indicators as ind

MODES = ("cloud", "tk", "sanyaku")
ATR_LEN = 20
STOP_ATR = 2.0


def signals(df: pd.DataFrame, *, mode: str = "cloud",
            atr_len: int = ATR_LEN, stop_atr: float = STOP_ATR) -> dict[str, pd.Series]:
    """Segnali Ichimoku simmetrici.

    L'uscita è il segnale opposto: un trend follower resta nel trade finché la
    condizione che l'ha aperto regge, e lo stop fa il resto.
    """
    if mode not in MODES:
        raise ValueError(f"mode deve essere uno di {MODES}")

    ichi = ind.ichimoku(df)
    close = df["close"]
    above, below = ichi["price_above"], ichi["price_below"]
    tk_bull = ichi["tk_bull"]
    chikou_up = ichi["chikou_clear"]
    chikou_dn = close < df["low"].shift(26)

    if mode == "cloud":
        bull, bear = above, below
    elif mode == "tk":
        bull = tk_bull & above
        bear = (~tk_bull) & below
    else:  # sanyaku
        bull = above & tk_bull & chikou_up
        bear = below & (~tk_bull) & chikou_dn

    bull, bear = bull.fillna(False), bear.fillna(False)

    return {
        # si entra sulla transizione, non su tutte le barre in cui la
        # condizione e' vera: altrimenti si rientrerebbe subito dopo ogni stop
        "entry_long": bull & ~bull.shift(1, fill_value=False),
        "exit_long": ~bull,
        "entry_short": bear & ~bear.shift(1, fill_value=False),
        "exit_short": ~bear,
        "stop_distance": stop_atr * ind.atr(df, atr_len),
    }
