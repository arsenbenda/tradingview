"""Motore di backtest bar-by-bar, un asset alla volta.

Scelte che determinano se i numeri significano qualcosa:

**Segnale su t, esecuzione su t+1.** Il segnale usa solo dati fino alla chiusura
della barra t; l'ordine viene riempito all'apertura di t+1. Nessuna decisione
può usare il prezzo con cui viene eseguita.

**La size si calcola al prezzo di fill, non al close del segnale.** È il difetto
misurato sia sulla v3.2 sia sulla v5.5: entrambe calcolano `qty` e lo stop sul
close della barra di segnale, ma vengono riempite all'apertura successiva. Su
USO lo scarto mediano fra i due prezzi è 0.774% e un giorno su sette supera il
2%. Il flag ``size_at_signal`` riproduce di proposito il comportamento Pine, per
poter **misurare** quanto costa il difetto invece di affermarlo.

**Lo slippage è in percentuale, non in tick.** `slippage=2` in Pine vale
0.00003% su BTC e 0.0999% su CORN: un fattore 3300 fra due asset dello stesso
portafoglio.

**I fill sono pessimistici.** Se una barra apre già oltre lo stop, l'uscita
avviene all'apertura, non allo stop. Non sapendo l'ordine intrabar, si assume il
peggiore.

Le strategie con stato (cooldown, zone lock, pause, circuit breaker) non sono
esprimibili come serie precalcolate, perché dipendono dall'esito dei trade
precedenti. Implementano l'interfaccia ``Strategy``; le strategie senza stato
passano da ``run``, che è un adattatore sullo stesso identico motore — un solo
percorso di esecuzione, quindi nessuna possibilità che i due divergano.
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
    qty: float          # quantita' ancora aperta
    initial_qty: float = 0.0
    partials: int = 0
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


@dataclass
class Intent:
    """Intenzione di apertura, decisa alla chiusura di una barra."""

    direction: int
    stop_distance: float
    risk_mult: float = 1.0
    tag: str = ""


@dataclass
class State:
    """Stato visibile alla strategia alla barra ``i``.

    Contiene tutto ciò che serve a replicare i controlli basati sulla storia
    dei trade: ``strategy.equity``, il drawdown corrente, la barra dell'ultima
    uscita, l'esito dell'ultimo trade, le perdite consecutive.
    """

    i: int
    direction: int = 0
    entry_price: float = 0.0
    entry_index: int = -1
    entry_tag: str = ""
    stop_level: float = float("nan")
    equity: float = 0.0
    cash: float = 0.0
    peak_equity: float = 0.0
    last_exit_index: int = -10_000
    last_trade_was_loss: bool = False
    consecutive_losses: int = 0
    closed_trades: int = 0

    @property
    def flat(self) -> bool:
        return self.direction == 0

    @property
    def bars_since_exit(self) -> int:
        return self.i - self.last_exit_index

    @property
    def bars_in_trade(self) -> int:
        return self.i - self.entry_index

    @property
    def drawdown_pct(self) -> float:
        if self.peak_equity <= 0:
            return 0.0
        return (self.peak_equity - self.equity) / self.peak_equity * 100.0


class Strategy:
    """Interfaccia delle strategie con stato."""

    name = "strategy"

    def prepare(self, df: pd.DataFrame) -> None:
        """Precalcola gli indicatori vettoriali."""

    def entry(self, state: State) -> Intent | None:
        """Decisione di apertura alla chiusura della barra ``state.i``."""
        return None

    def manage(self, state: State) -> tuple[bool | float, float | None]:
        """Gestione della posizione aperta.

        Restituisce ``(uscita, nuovo_livello_di_stop)``. L'uscita puo' essere un
        booleano (chiusura totale) oppure una frazione fra 0 e 1, per le
        strategie che scalano l'uscita in piu' tranche. Il nuovo livello di stop
        viene applicato solo se muove lo stop a favore.
        """
        return False, None


class _SignalStrategy(Strategy):
    """Adattatore per strategie esprimibili come serie precalcolate."""

    def __init__(self, entry_long, exit_long, entry_short, exit_short,
                 stop_distance, trail_stop, tags, index):
        def arr(s, default=0.0):
            if s is None:
                return np.full(len(index), default)
            return s.reindex(index).to_numpy(float)

        self.e_long = arr(entry_long).astype(bool)
        self.x_long = arr(exit_long).astype(bool)
        self.e_short = arr(entry_short).astype(bool)
        self.x_short = arr(exit_short).astype(bool)
        self.stop_dist = arr(stop_distance, np.nan)
        self.trail = arr(trail_stop, np.nan)
        self.tags = tags.reindex(index).to_numpy() if tags is not None else np.full(len(index), "")

    def entry(self, state: State) -> Intent | None:
        i = state.i
        if self.e_long[i]:
            return Intent(1, self.stop_dist[i], tag=str(self.tags[i]))
        if self.e_short[i]:
            return Intent(-1, self.stop_dist[i], tag=str(self.tags[i]))
        return None

    def manage(self, state: State) -> tuple[bool, float | None]:
        i = state.i
        if state.direction > 0 and self.x_long[i]:
            return True, None
        if state.direction < 0 and self.x_short[i]:
            return True, None
        trail = self.trail[i]
        return False, (trail if np.isfinite(trail) else None)


def run_strategy(
    df: pd.DataFrame,
    strategy: Strategy,
    *,
    costs: Costs = Costs(),
    risk_pct: float = 0.01,
    initial_capital: float = 100_000.0,
    max_notional_pct: float = 1.0,
    size_at_signal: bool = False,
    notional_sizing: bool = False,
) -> Result:
    """Esegue una strategia a posizione singola.

    ``size_at_signal=True`` riproduce il comportamento Pine: quantità e stop
    ancorati al close della barra di segnale invece che al prezzo di fill.
    Serve a misurare il costo di quel difetto, non a usarlo.

    ``notional_sizing=True`` sostituisce la regola di dimensionamento: la
    posizione vale ``max_notional_pct`` del capitale disponibile invece di
    ``rischio / distanza dello stop``. Lo stop continua a governare le uscite,
    ma non la quantità — quindi la volatilità dello strumento non entra più nel
    sizing. È l'ipotesi 23 del catalogo, e ``risk_pct`` diventa inerte.
    """
    strategy.prepare(df)

    idx = df.index
    n = len(df)
    open_, high, low, close = (df[c].to_numpy(float) for c in ("open", "high", "low", "close"))

    equity = np.full(n, initial_capital)
    trades: list[Trade] = []
    st = State(i=0, cash=initial_capital, equity=initial_capital, peak_equity=initial_capital)
    bars_in_market = 0
    pending: tuple[Intent, float] | None = None  # (intent, close di segnale)

    def close_position(i: int, price: float, reason: str, fraction: float = 1.0) -> None:
        """Chiude tutta la posizione o una frazione.

        Il P&L di una chiusura parziale viene realizzato subito e sommato al
        trade, che resta aperto con la quantita' residua: il record finale
        rappresenta l'operazione completa, tranche incluse.
        """
        proceeds = price * (1 - costs.per_side) if st.direction > 0 else price * (1 + costs.per_side)
        trade = trades[-1]
        closing = trade.qty if fraction >= 1.0 else trade.qty * fraction
        realized = (proceeds - trade.entry_price) * closing * st.direction
        trade.pnl += realized
        st.cash += realized

        if fraction < 1.0:
            trade.qty -= closing
            trade.partials += 1
            return

        trade.qty = 0.0
        trade.exit_date = idx[i]
        trade.exit_price = proceeds
        trade.exit_reason = reason
        trade.bars_held = i - st.entry_index
        trade.r_multiple = trade.pnl / trade.risk_amount if trade.risk_amount else 0.0
        st.direction, st.stop_level = 0, float("nan")
        st.last_exit_index = i
        st.last_trade_was_loss = trade.pnl < 0
        st.consecutive_losses = st.consecutive_losses + 1 if trade.pnl < 0 else 0
        st.closed_trades += 1

    for i in range(n):
        st.i = i

        # ---- esecuzione all'apertura di quanto deciso alla chiusura precedente
        if pending is not None and st.flat:
            intent, signal_close = pending
            pending = None
            dist = intent.stop_distance
            if dist > 0 and np.isfinite(dist):
                fill = open_[i] * (1 + costs.per_side) if intent.direction > 0 else open_[i] * (1 - costs.per_side)
                anchor = signal_close if size_at_signal else fill
                if notional_sizing:
                    size = st.cash * max_notional_pct / fill
                    # il rischio non è più un input ma una conseguenza: tenerlo
                    # nominale renderebbe incomparabili gli R fra le due regole
                    risk_amount = size * dist
                else:
                    risk_amount = st.cash * risk_pct * intent.risk_mult
                    size = min(risk_amount / dist, st.cash * max_notional_pct / fill)
                if size > 0:
                    st.direction, st.entry_price, st.entry_index = intent.direction, fill, i
                    st.entry_tag = intent.tag
                    st.stop_level = anchor - dist if intent.direction > 0 else anchor + dist
                    trades.append(
                        Trade(direction=intent.direction, entry_date=idx[i], entry_price=fill,
                              qty=size, initial_qty=size, risk_amount=risk_amount, tag=intent.tag)
                    )

        # ---- gestione della posizione, già attiva sulla barra di fill
        if not st.flat:
            bars_in_market += 1
            hit = (low[i] <= st.stop_level) if st.direction > 0 else (high[i] >= st.stop_level)
            if hit:
                gapped = (open_[i] <= st.stop_level) if st.direction > 0 else (open_[i] >= st.stop_level)
                close_position(i, open_[i] if gapped else st.stop_level, "gap" if gapped else "stop")
            else:
                st.equity = st.cash + (close[i] - st.entry_price) * trades[-1].qty * st.direction
                should_exit, new_stop = strategy.manage(st)
                fraction = 1.0 if should_exit is True else (0.0 if should_exit is False else float(should_exit))
                if fraction > 0:
                    close_position(i, close[i], "segnale", fraction)
                if not st.flat and new_stop is not None and np.isfinite(new_stop):
                    st.stop_level = max(st.stop_level, new_stop) if st.direction > 0 else min(st.stop_level, new_stop)

        # ---- aggiornamento equity e decisione per la barra successiva
        st.equity = st.cash if st.flat else st.cash + (close[i] - st.entry_price) * trades[-1].qty * st.direction
        st.peak_equity = max(st.peak_equity, st.equity)
        equity[i] = st.equity

        if st.flat and pending is None:
            intent = strategy.entry(st)
            if intent is not None and intent.direction != 0:
                pending = (intent, close[i])

    if not st.flat:
        close_position(n - 1, close[-1], "fine serie")
        equity[-1] = st.cash

    return Result(equity=pd.Series(equity, index=idx), trades=trades,
                  exposure=bars_in_market / n if n else 0.0)


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
    size_at_signal: bool = False,
    notional_sizing: bool = False,
) -> Result:
    """Esegue una strategia espressa come serie di segnali."""
    strategy = _SignalStrategy(entry_long, exit_long, entry_short, exit_short,
                               stop_distance, trail_stop, tags, df.index)
    return run_strategy(df, strategy, costs=costs, risk_pct=risk_pct,
                        initial_capital=initial_capital, max_notional_pct=max_notional_pct,
                        size_at_signal=size_at_signal, notional_sizing=notional_sizing)
