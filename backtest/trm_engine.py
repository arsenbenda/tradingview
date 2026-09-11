"""
Trend Rebalance Map [Herman] -- Python port of the Pine Script v6 strategy.

Source strategy:
  https://github.com/HermanTrading/Trend-Rebalance-Map-Herman-

Engine rules reproduced from the Pine source
--------------------------------------------
* Signals are evaluated on CLOSED bars only (`barstate.isconfirmed`).
      bullishCross = ta.crossover(close, sma50)
      bearishCross = ta.crossunder(close, sma50)
      longDirection  = sma50 < sma200      (buy the dip in a down-skewed pair)
      shortDirection = sma50 > sma200      (sell the rip in an up-skewed pair)
      separationPass = |sma50 - sma200| / pointSize > minSeparation
* `process_orders_on_close = true`  -> the entry fills at the close of the
  signal bar.
* Stop / target orders issued at the close of bar *i* are live for bar *i+1*
  (no look-ahead, no intrabar re-pricing).  In "Dynamic" mode the target is
  re-issued every bar at the current 200 SMA, exactly as the Pine script does.
* One position at a time; opposite signals are ignored while a trade is open;
  no new entry on the bar a trade closed (`lastExitBar` guard).
* Intrabar fill order follows TradingView's broker-emulator assumption:
  up bar  (close >= open):  open -> low -> high -> close
  down bar(close <  open):  open -> high -> low -> close
  A gap through a level fills at the bar open.
* Slippage is charged on market/stop fills only (TradingView does not slip
  limit fills).  Commission is charged per contract, per side.

Extensions beyond the Pine source (opt-in, off by default) exist because the
published defaults are calibrated for index futures where price is ~20,000 and
constant over the test window.  BTC ran from $13 to $126,000 across this data
set, so a *fixed dollar* separation filter and a *fixed dollar* stop cannot
mean the same thing at both ends.  `sep_mode="percent"` and
`sl_mode="percent"` express those two inputs as a share of price instead.
Everything else -- signal, direction rule, one-trade-at-a-time, dynamic 200
SMA target, fill model -- is unchanged.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# configuration
# --------------------------------------------------------------------------
@dataclass
class Params:
    # --- signal (Pine: G_SIG) ---
    sma_fast: int = 50
    sma_slow: int = 200
    point_size: float = 1.0
    min_separation: float = 30.0          # in "points" (sep_mode="points")
    sep_mode: str = "points"              # "points" | "percent"
    min_separation_pct: float = 1.0       # |fast-slow| / close * 100

    # --- direction (Pine: G_DIR) ---
    enable_longs: bool = True
    enable_shorts: bool = True

    # --- take profit (Pine: G_TP) ---
    tp_mode: str = "200 SMA"              # "200 SMA" | "Fixed Points"
    sma_target_behaviour: str = "Dynamic"  # "Dynamic" | "Locked at Entry"
    tp_fixed_points: float = 100.0

    # --- stop loss (Pine: G_SL) ---
    sl_mode: str = "Fixed Points"         # "Fixed Points" | "1R to TP" | "Percent" | "ATR"
    sl_fixed_points: float = 125.0
    sl_pct: float = 2.0                   # used when sl_mode == "Percent"
    atr_len: int = 14                     # used when sl_mode == "ATR"
    atr_mult: float = 2.0

    # --- broker model (Pine: strategy() header) ---
    initial_capital: float = 100_000.0
    qty_mode: str = "fixed"               # "fixed" | "pct_equity" | "notional"
    qty_fixed: float = 1.0                # contracts (BTC) per trade
    qty_pct_equity: float = 100.0         # notional as % of equity
    qty_notional: float = 10_000.0        # constant $ notional per trade
    commission_per_contract: float = 2.5  # cash per contract, per side
    commission_pct: float = 0.0           # % of notional, per side (crypto fees)
    slippage_ticks: float = 2.0
    mintick: float = 1.0


@dataclass
class Trade:
    side: int
    entry_bar: int
    exit_bar: int
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_px: float
    exit_px: float
    qty: float
    stop_px: float
    tp_px_at_entry: float
    reason: str
    pnl: float
    pnl_pct: float          # net return on the traded notional
    bars_held: int


@dataclass
class Result:
    params: Params
    timeframe: str
    trades: List[Trade] = field(default_factory=list)
    equity: Optional[pd.Series] = None      # mark-to-market, per bar
    bars: int = 0
    start: Optional[pd.Timestamp] = None
    end: Optional[pd.Timestamp] = None


# --------------------------------------------------------------------------
# engine
# --------------------------------------------------------------------------
def run(df: pd.DataFrame, p: Params, timeframe: str = "",
        trade_from: Optional[pd.Timestamp] = None) -> Result:
    """df: DatetimeIndex with columns open/high/low/close (UTC).

    `trade_from` marks the first bar allowed to OPEN a trade.  Bars before it
    still feed the moving averages, so a test window is not silently short of
    its first `sma_slow` bars -- it warms up on the history preceding it, the
    way a chart does.  A trade opened inside the window is still carried to its
    natural exit.
    """
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    idx = df.index

    close_s = df["close"]
    fast = close_s.rolling(p.sma_fast).mean().to_numpy(float)
    slow = close_s.rolling(p.sma_slow).mean().to_numpy(float)

    # ta.crossover / ta.crossunder against the fast SMA
    prev_c = np.roll(c, 1)
    prev_f = np.roll(fast, 1)
    prev_c[0] = np.nan
    prev_f[0] = np.nan
    cross_up = (c > fast) & (prev_c <= prev_f)
    cross_dn = (c < fast) & (prev_c >= prev_f)

    if p.sep_mode == "percent":
        sep_ok = (np.abs(fast - slow) / c * 100.0) > p.min_separation_pct
    else:
        sep_ok = (np.abs(fast - slow) / p.point_size) > p.min_separation

    if p.sl_mode == "ATR":
        prev_close = close_s.shift(1)
        tr = pd.concat([df["high"] - df["low"],
                        (df["high"] - prev_close).abs(),
                        (df["low"] - prev_close).abs()], axis=1).max(axis=1)
        ATR = tr.ewm(alpha=1.0 / p.atr_len, adjust=False).mean().to_numpy(float).tolist()
    else:
        ATR = None

    valid = ~np.isnan(fast) & ~np.isnan(slow) & ~np.isnan(prev_f)
    long_sig = cross_up & (fast < slow) & sep_ok & valid & p.enable_longs
    short_sig = cross_dn & (fast > slow) & sep_ok & valid & p.enable_shorts

    # python lists index faster than numpy scalars in a tight loop
    O, H, L, C = o.tolist(), h.tolist(), l.tolist(), c.tolist()
    SLOW = slow.tolist()
    LS, SS = long_sig.tolist(), short_sig.tolist()

    slip = p.slippage_ticks * p.mintick
    n = len(df)
    i0 = int(idx.searchsorted(trade_from)) if trade_from is not None else 0

    pos = 0                 # 0 flat, +1 long, -1 short
    entry_px = 0.0
    qty = 0.0
    stop_lvl = math.nan     # level live for the CURRENT bar
    tp_lvl = math.nan
    tp_locked = math.nan
    entry_bar = -1
    last_exit_bar = -1
    equity = p.initial_capital
    eq_curve = np.empty(n)
    eq_curve[:] = np.nan
    trades: List[Trade] = []

    for i in range(n):
        oi, hi, li, ci = O[i], H[i], L[i], C[i]

        # ---------- 1. exits: orders placed at the close of bar i-1 ----------
        if pos != 0 and not math.isnan(stop_lvl):
            fill_px = None
            reason = ""
            if pos == 1:
                if oi <= stop_lvl:                       # gapped through stop
                    fill_px, reason = oi - slip, "SL"
                elif oi >= tp_lvl:                       # gapped through target
                    fill_px, reason = oi, "TP"
                elif ci >= oi:                           # up bar: O -> L -> H -> C
                    if li <= stop_lvl:
                        fill_px, reason = stop_lvl - slip, "SL"
                    elif hi >= tp_lvl:
                        fill_px, reason = tp_lvl, "TP"
                else:                                    # down bar: O -> H -> L -> C
                    if hi >= tp_lvl:
                        fill_px, reason = tp_lvl, "TP"
                    elif li <= stop_lvl:
                        fill_px, reason = stop_lvl - slip, "SL"
            else:
                if oi >= stop_lvl:
                    fill_px, reason = oi + slip, "SL"
                elif oi <= tp_lvl:
                    fill_px, reason = oi, "TP"
                elif ci >= oi:                           # up bar: O -> L -> H -> C
                    if li <= tp_lvl:
                        fill_px, reason = tp_lvl, "TP"
                    elif hi >= stop_lvl:
                        fill_px, reason = stop_lvl + slip, "SL"
                else:                                    # down bar: O -> H -> L -> C
                    if hi >= stop_lvl:
                        fill_px, reason = stop_lvl + slip, "SL"
                    elif li <= tp_lvl:
                        fill_px, reason = tp_lvl, "TP"

            if fill_px is not None:
                gross = (fill_px - entry_px) * qty * pos
                fees = _fees(p, qty, entry_px, fill_px)
                pnl = gross - fees
                equity += pnl
                trades.append(Trade(
                    side=pos, entry_bar=entry_bar, exit_bar=i,
                    entry_time=idx[entry_bar], exit_time=idx[i],
                    entry_px=entry_px, exit_px=fill_px, qty=qty,
                    stop_px=stop_lvl, tp_px_at_entry=tp_locked,
                    reason=reason, pnl=pnl,
                    pnl_pct=pnl / (entry_px * qty) if qty else 0.0,
                    bars_held=i - entry_bar,
                ))
                pos = 0
                qty = 0.0
                stop_lvl = math.nan
                tp_lvl = math.nan
                last_exit_bar = i                        # Pine: no entry on this bar

        # ---------- 2. entry at the close of bar i ----------
        if pos == 0 and i != last_exit_bar and i >= i0:
            side = 1 if LS[i] else (-1 if SS[i] else 0)
            if side:
                ref = ci + slip * side                   # slipped market fill
                if p.tp_mode == "200 SMA":
                    init_tp = SLOW[i]
                else:
                    init_tp = ref + side * p.tp_fixed_points * p.point_size
                dist = abs(init_tp - ref)
                if p.sl_mode == "1R to TP":
                    sl = ref - side * dist
                elif p.sl_mode == "Percent":
                    sl = ref * (1.0 - side * p.sl_pct / 100.0)
                elif p.sl_mode == "ATR":
                    sl = ref - side * ATR[i] * p.atr_mult
                else:
                    sl = ref - side * p.sl_fixed_points * p.point_size

                if p.qty_mode == "fixed":
                    qty = p.qty_fixed
                elif p.qty_mode == "notional":
                    qty = p.qty_notional / ref
                else:
                    qty = max(equity, 0.0) * p.qty_pct_equity / 100.0 / ref
                if qty > 0:
                    pos, entry_px, entry_bar = side, ref, i
                    tp_locked = init_tp
                    stop_lvl = sl
                    tp_lvl = init_tp

        # ---------- 3. re-issue the target for bar i+1 (Dynamic mode) --------
        if pos != 0:
            if p.tp_mode == "200 SMA" and p.sma_target_behaviour == "Dynamic":
                s = SLOW[i]
                if not math.isnan(s):
                    tp_lvl = s
            eq_curve[i] = equity + (ci - entry_px) * qty * pos
        else:
            eq_curve[i] = equity

    eq = pd.Series(eq_curve, index=idx)[i0:]
    return Result(params=p, timeframe=timeframe, trades=trades,
                  equity=eq, bars=n - i0,
                  start=idx[i0] if n > i0 else None, end=idx[-1] if n else None)


def _fees(p: Params, qty: float, entry_px: float, exit_px: float) -> float:
    """Commission for both sides of a round turn."""
    cash = p.commission_per_contract * qty * 2.0
    pct = p.commission_pct / 100.0 * qty * (entry_px + exit_px)
    return cash + pct
