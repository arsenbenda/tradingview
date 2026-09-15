"""Il catalogo completo delle ipotesi testate, in un posto solo.

La regola di lavoro numero quattro dice che ogni ipotesi testata va contata. Fino
a ora il conteggio stava in due script diversi — quindici filtri in
`run_ablation.py`, sette varianti Ichimoku in `run_ichimoku_tests.py` — e il
totale si otteneva sommandolo a mano. Un conteggio tenuto a mano è un conteggio
che prima o poi sbaglia per difetto, e sbagliare per difetto il numero di
ipotesi è esattamente il modo in cui il Deflated Sharpe smette di proteggere da
qualcosa.

Qui ogni ipotesi è una voce del dizionario ``CATALOGUE`` e ``N_HYPOTHESES`` è la
sua lunghezza: il numero che finisce nel Deflated Sharpe non può più divergere
da quello che è stato davvero provato. Aggiungere un'ipotesi significa
aggiungere una riga qui, e il conteggio si aggiorna da solo.

Il benchmark **non** è un'ipotesi: è il termine di paragone, scelto prima dei
dati (parametri Turtle pubblicati). Sta in ``BASE_NAME``, fuori dal catalogo,
ma dentro ``SELECTION_POOL`` — perché una procedura di selezione onesta deve
poter concludere "nessuna variante, tengo il benchmark".
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

from . import backtest, costs as cost_table, filters
from .strategies import donchian, ichimoku_tf

CAPITAL = 100_000.0
RISK_PCT = 0.01

# (nome asset, serie, moltiplicatore dei costi) -> Result
Runner = Callable[[str, pd.DataFrame, float], backtest.Result]


def _exit_variant(mode: str) -> Runner:
    """Ingressi Donchian invariati, uscita sostituita."""

    def run(asset: str, df: pd.DataFrame, cost_mult: float = 1.0) -> backtest.Result:
        return backtest.run_strategy(
            df, donchian.DonchianWithExit(exit_mode=mode),
            costs=cost_table.for_asset(asset, cost_mult),
            risk_pct=RISK_PCT, initial_capital=CAPITAL,
        )

    return run


def _signal_variant(mode: str) -> Runner:
    """Ichimoku come segnale autonomo, simmetrico long/short."""

    def run(asset: str, df: pd.DataFrame, cost_mult: float = 1.0) -> backtest.Result:
        s = ichimoku_tf.signals(df, mode=mode)
        return backtest.run(
            df, entry_long=s["entry_long"], exit_long=s["exit_long"],
            entry_short=s["entry_short"], exit_short=s["exit_short"],
            stop_distance=s["stop_distance"],
            costs=cost_table.for_asset(asset, cost_mult),
            risk_pct=RISK_PCT, initial_capital=CAPITAL,
        )

    return run


def _filter_variant(gate) -> Runner:
    """Benchmark con un gate direzionale sugli ingressi."""

    def run(asset: str, df: pd.DataFrame, cost_mult: float = 1.0) -> backtest.Result:
        sig = donchian.signals(df, allow_short=True)
        allow_long, allow_short = gate(df)
        return backtest.run(
            df,
            entry_long=sig["entry_long"] & allow_long.reindex(df.index).fillna(False),
            exit_long=sig["exit_long"],
            entry_short=sig["entry_short"] & allow_short.reindex(df.index).fillna(False),
            exit_short=sig["exit_short"],
            stop_distance=sig["stop_distance"],
            costs=cost_table.for_asset(asset, cost_mult),
            risk_pct=RISK_PCT, initial_capital=CAPITAL,
        )

    return run


BASE_NAME = "donchian_base"
BASE: Runner = _exit_variant("canale")

#: le ipotesi testate, tutte quante. Il benchmark non è qui dentro.
CATALOGUE: dict[str, Runner] = {
    **{f"filter_{name}": _filter_variant(fn) for name, fn in filters.CATALOGUE.items()},
    **{f"signal_{mode}": _signal_variant(mode) for mode in ichimoku_tf.MODES},
    **{f"exit_{mode}": _exit_variant(mode)
       for mode in donchian.DonchianWithExit.EXIT_MODES if mode != "canale"},
}

#: quante ipotesi sono state provate. Entra nel Deflated Sharpe come N.
N_HYPOTHESES: int = len(CATALOGUE)

#: il candidato uscito dalla selezione su tutto il periodo.
CANDIDATE = "exit_cloud_exit"

#: cosa può scegliere una procedura di selezione: le ipotesi, più la rinuncia.
SELECTION_POOL: dict[str, Runner] = {BASE_NAME: BASE, **CATALOGUE}
