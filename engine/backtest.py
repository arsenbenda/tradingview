"""Motore di backtest bar-by-bar, un asset alla volta.

Scelte che determinano se i numeri significano qualcosa:

**Segnale su t, esecuzione su t+1.** Il segnale usa solo dati fino alla chiusura
della barra t; l'ordine viene riempito all'apertura di t+1. Nessuna decisione
può usare il prezzo con cui viene eseguita.

**La size si calcola al prezzo di fill, non al close del segnale.** È il difetto
misurato sia sulla v3.2 sia sulla v5.5: entrambe calcolano `qty` e lo stop sul
close della barra di segnale, ma vengono riempite all'apertura successiva. Su
USO lo scarto mediano fra i due prezzi è 0.774% e un giorno su sette supera il
2%, quindi il "rischio 1% per trade" nominale diventa un rischio reale
arbitrario. Qui la quantità viene derivata dal prezzo effettivo di ingresso.

**Lo slippage è in percentuale, non in tick.** `slippage=2` in Pine vale
0.00003% su BTC e 0.0999% su CORN: un fattore 3300 fra due asset dello stesso
portafoglio. Una percentuale per asset è l'unico modo di confrontarli.

**I fill sono pessimistici.** Se una barra apre già oltre lo stop, l'uscita
avviene all'apertura, non allo stop. Se nella stessa barra vengono toccati sia
stop sia obiettivo, vince lo stop: non sapendo l'ordine intrabar, si assume il
peggiore.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Costs:
    """Costi di transazione, in frazione di prezzo (0.001 = 0.1%)."""

    commission: float = 0.001
    slippage: float = 0.0005

    @property
    def per_side(self) -> float:
        return self.commission + self.slippage


@dataclass
class Trade:
    direction: int  # +1 long, -1 short
    entry_date: pd.Timestamp
    entry_price: float
    qty: float
    exit_date: pd.Timestamp | None = None
    exit_price: float | None = None
    exit_reason: str = ""
    pnl: float = 0.0
    r_multiple: float = 0.0
    risk_amount: float = 0.0
    bars_held: int = 0
    tag: str = ""

    @property
    def is_open(self) -> bool:
        return self.exit_date is None


@dataclass
class Result:
    equity: pd.Series
    trades: list[Trade] = field(default_factory=list)
    exposure: float = 0.0

    @property
    def returns(self) -> pd.Series:
        return self.equity.pct_change().fillna(0.0)


def run(
    df: pd.DataFrame,
    *,
    entry_long: pd.Series,
    exit_long: pd.Series,
    stop_distance: pd.Series,
    entry_short: pd.Series | None = None,
    exit_short: pd.Series | None = None,
    costs: Costs = Costs(),
    risk_pct: float = 0.01,
    initial_capital: float = 100_000.0,
    max_notional_pct: float = 1.0,
    trail_stop: pd.Series | None = None,
    tags: pd.Series | None = None,
) -> Result:
    """Esegue una strategia a posizione singola.

    Tutte le serie in ingresso sono indicizzate come ``df`` e si riferiscono
    alla **barra di segnale**: la loro decisione viene eseguita sulla barra
    successiva.

    ``stop_distance`` è la distanza dello stop in unità di prezzo (tipicamente
    un multiplo di ATR) valida al momento del segnale; ``trail_stop``, se
    fornita, è un livello assoluto verso cui trascinare lo stop, applicato solo
    in senso favorevole (non allontana mai lo stop dal prezzo).
    """
    idx = df.index
    n = len(df)
    open_, high, low, close = (df[c].to_numpy(float) for c in ("open", "high", "low", "close"))

    def arr(s: pd.Series | None, default: float = 0.0) -> np.ndarray:
        if s is None:
            return np.full(n, default)
        return s.reindex(idx).to_numpy(float)

    e_long = arr(entry_long).astype(bool)
    x_long = arr(exit_long).astype(bool)
    e_short = arr(entry_short).astype(bool)
    x_short = arr(exit_short).astype(bool)
    stop_dist = arr(stop_distance, np.nan)
    trail = arr(trail_stop, np.nan)
    tag_values = tags.reindex(idx).to_numpy() if tags is not None else np.full(n, "")

    equity = np.full(n, initial_capital)
    cash = initial_capital
    trades: list[Trade] = []

    direction = 0
    qty = 0.0
    entry_price = 0.0
    stop_level = np.nan
    entry_i = 0
    bars_in_market = 0
    pending: tuple[int, float, str] | None = None  # (direzione, distanza stop, tag)

    def close_position(i: int, price: float, reason: str) -> None:
        nonlocal cash, direction, qty, stop_level
        proceeds = price * (1 - costs.per_side) if direction > 0 else price * (1 + costs.per_side)
        trade = trades[-1]
        trade.exit_date = idx[i]
        trade.exit_price = proceeds
        trade.exit_reason = reason
        trade.pnl = (proceeds - trade.entry_price) * qty * direction
        trade.bars_held = i - entry_i
        trade.r_multiple = trade.pnl / trade.risk_amount if trade.risk_amount else 0.0
        cash += trade.pnl
        direction, qty, stop_level = 0, 0.0, np.nan

    for i in range(n):
        # ---- esecuzione all'apertura di ciò che è stato deciso alla chiusura
        # della barra precedente
        if pending is not None and direction == 0:
            want_dir, dist, tag = pending
            pending = None
            if dist > 0 and np.isfinite(dist):
                fill = open_[i] * (1 + costs.per_side) if want_dir > 0 else open_[i] * (1 - costs.per_side)
                risk_amount = cash * risk_pct
                size = risk_amount / dist                      # size derivata dal fill, non dal close di segnale
                size = min(size, cash * max_notional_pct / fill)
                if size > 0:
                    direction, qty, entry_price, entry_i = want_dir, size, fill, i
                    stop_level = fill - dist if want_dir > 0 else fill + dist
                    trades.append(
                        Trade(
                            direction=want_dir,
                            entry_date=idx[i],
                            entry_price=fill,
                            qty=size,
                            risk_amount=risk_amount,
                            tag=str(tag),
                        )
                    )

        # ---- gestione della posizione aperta, sulla stessa barra del fill
        if direction != 0:
            bars_in_market += 1
            hit = (low[i] <= stop_level) if direction > 0 else (high[i] >= stop_level)
            if hit:
                # se la barra apre già oltre lo stop, si esce all'apertura
                gapped = (open_[i] <= stop_level) if direction > 0 else (open_[i] >= stop_level)
                close_position(i, open_[i] if gapped else stop_level, "gap" if gapped else "stop")
            else:
                if direction > 0 and x_long[i]:
                    close_position(i, close[i], "segnale")
                elif direction < 0 and x_short[i]:
                    close_position(i, close[i], "segnale")
                elif np.isfinite(trail[i]):
                    stop_level = max(stop_level, trail[i]) if direction > 0 else min(stop_level, trail[i])

        # ---- decisione per la barra successiva
        if direction == 0 and pending is None:
            if e_long[i]:
                pending = (1, stop_dist[i], tag_values[i])
            elif e_short[i]:
                pending = (-1, stop_dist[i], tag_values[i])

        mark = cash
        if direction != 0:
            mark = cash + (close[i] - entry_price) * qty * direction
        equity[i] = mark

    if direction != 0:
        close_position(n - 1, close[-1], "fine serie")
        equity[-1] = cash

    return Result(
        equity=pd.Series(equity, index=idx),
        trades=trades,
        exposure=bars_in_market / n if n else 0.0,
    )
