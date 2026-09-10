"""Performance statistics for a Result produced by trm_engine.run()."""
from __future__ import annotations

import numpy as np
import pandas as pd

from trm_engine import Result


def _max_dd(eq: pd.Series):
    peak = eq.cummax()
    dd = eq - peak
    dd_pct = dd / peak.replace(0, np.nan)
    i = dd_pct.idxmin() if len(dd_pct.dropna()) else None
    return float(dd.min() if len(dd) else 0.0), float(dd_pct.min() * 100 if i is not None else 0.0)


def summary(r: Result, label: str = "") -> dict:
    t = r.trades
    p = r.params
    eq = r.equity.dropna()
    n = len(t)
    pnl = np.array([x.pnl for x in t]) if n else np.array([])
    pct = np.array([x.pnl_pct for x in t]) if n else np.array([])
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    gp, gl = float(wins.sum()), float(-losses.sum())

    years = ((r.end - r.start).days / 365.25) if (r.start is not None and n >= 0) else np.nan
    final = float(eq.iloc[-1]) if len(eq) else p.initial_capital
    net = final - p.initial_capital
    cagr = ((final / p.initial_capital) ** (1 / years) - 1) * 100 if years and final > 0 else np.nan
    dd_abs, dd_pct = _max_dd(eq) if len(eq) else (0.0, 0.0)

    bars_in = sum(x.bars_held for x in t)
    longs = [x for x in t if x.side == 1]
    shorts = [x for x in t if x.side == -1]

    # Sharpe on daily marked-to-market equity
    daily = eq.resample("1D").last().dropna()
    rets = daily.pct_change().dropna()
    sharpe = (rets.mean() / rets.std() * np.sqrt(365)) if len(rets) > 5 and rets.std() > 0 else np.nan

    return {
        "label": label,
        "timeframe": r.timeframe,
        "start": r.start.date().isoformat() if r.start is not None else "",
        "end": r.end.date().isoformat() if r.end is not None else "",
        "years": round(years, 2) if years == years else np.nan,
        "trades": n,
        "wins": int((pnl > 0).sum()),
        "losses": int((pnl <= 0).sum()),
        "win_rate": round(100.0 * (pnl > 0).sum() / n, 2) if n else np.nan,
        "profit_factor": round(gp / gl, 3) if gl > 0 else (np.inf if gp > 0 else np.nan),
        "net_profit": round(net, 2),
        "net_profit_pct": round(100.0 * net / p.initial_capital, 2),
        "cagr_pct": round(cagr, 2) if cagr == cagr else np.nan,
        "max_dd_pct": round(dd_pct, 2),
        "sharpe": round(float(sharpe), 2) if sharpe == sharpe else np.nan,
        "avg_trade_pct": round(100.0 * pct.mean(), 4) if n else np.nan,
        "avg_win_pct": round(100.0 * pct[pct > 0].mean(), 3) if (pct > 0).any() else np.nan,
        "avg_loss_pct": round(100.0 * pct[pct <= 0].mean(), 3) if (pct <= 0).any() else np.nan,
        "tp_exits": sum(1 for x in t if x.reason == "TP"),
        "sl_exits": sum(1 for x in t if x.reason == "SL"),
        "long_trades": len(longs),
        "long_wr": round(100.0 * sum(1 for x in longs if x.pnl > 0) / len(longs), 1) if longs else np.nan,
        "long_pnl": round(sum(x.pnl for x in longs), 2),
        "short_trades": len(shorts),
        "short_wr": round(100.0 * sum(1 for x in shorts if x.pnl > 0) / len(shorts), 1) if shorts else np.nan,
        "short_pnl": round(sum(x.pnl for x in shorts), 2),
        "exposure_pct": round(100.0 * bars_in / r.bars, 2) if r.bars else np.nan,
        "avg_bars_held": round(bars_in / n, 1) if n else np.nan,
    }


def trades_frame(r: Result) -> pd.DataFrame:
    return pd.DataFrame([{
        "side": "long" if x.side == 1 else "short",
        "entry_time": x.entry_time, "exit_time": x.exit_time,
        "entry_px": round(x.entry_px, 2), "exit_px": round(x.exit_px, 2),
        "stop_px": round(x.stop_px, 2), "tp_at_entry": round(x.tp_px_at_entry, 2),
        "qty": round(x.qty, 6), "reason": x.reason,
        "pnl": round(x.pnl, 2), "pnl_pct": round(100 * x.pnl_pct, 3),
        "bars_held": x.bars_held,
    } for x in r.trades])


def yearly(r: Result) -> pd.DataFrame:
    if not r.trades:
        return pd.DataFrame()
    df = trades_frame(r)
    df["year"] = pd.to_datetime(df["exit_time"]).dt.year
    g = df.groupby("year")
    out = pd.DataFrame({
        "trades": g.size(),
        "win_rate": (g["pnl"].apply(lambda s: 100.0 * (s > 0).mean())).round(1),
        "net_pnl": g["pnl"].sum().round(2),
        "avg_pct": (g["pnl_pct"].mean()).round(3),
    })
    return out.reset_index()
