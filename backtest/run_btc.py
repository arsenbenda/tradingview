"""
Backtest "Trend Rebalance Map [Herman]" on BTC/USD.

Data:  Bitstamp BTC/USD 1-minute candles (2012-01-01 -> today), resampled by
       data_prep.py.  Real spot BTC/USD, not a USDT-perp proxy.

Design
  Phase 1  the Pine defaults exactly as published (they are calibrated for
           index futures: 30-point separation filter, 125-point stop).
  Phase 2  a percent-of-price adaptation of those two inputs, swept over
           5 timeframes x 6 separation filters x 6 stop sizes x 3 directions,
           SELECTED on 2017-2021 and then measured on unseen data:
             forward  out-of-sample  2022-01-01 -> today
             backward out-of-sample  2012-01-01 -> 2016-12-31
  Phase 3  deep dive on the best in-sample configuration.
  Phase 4  fragility screen of every in-sample winner: does it survive
           out-of-sample, and does it survive deleting its single best trade?
"""
from __future__ import annotations

import os
import itertools
import numpy as np
import pandas as pd

from trm_engine import Params, run
from metrics import summary, trades_frame, yearly

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.abspath(os.path.join(HERE, "..", "results"))
TFS = ["5m", "15m", "1h", "4h", "1d", "1w"]

IS = ("2017-01-01", "2022-01-01")        # selection window
OOS_FWD = ("2022-01-01", None)           # never used for selection
OOS_BACK = ("2012-01-01", "2017-01-01")  # never used for selection
FULL = ("2012-01-01", None)
MODERN = ("2017-01-01", None)

# realistic spot-crypto round turn: 0.05 % per side (taker) + 2 ticks slippage
REAL = dict(commission_per_contract=0.0, commission_pct=0.05,
            slippage_ticks=2.0, mintick=1.0)
# exactly what the Pine header specifies
PINE = dict(commission_per_contract=2.5, commission_pct=0.0,
            slippage_ticks=2.0, mintick=1.0)

SEP_GRID = [0.15, 0.5, 1.0, 2.0, 3.0, 5.0]
SL_GRID = [("Percent", 0.625), ("Percent", 1.5), ("Percent", 3.0),
           ("Percent", 5.0), ("Percent", 8.0), ("1R to TP", None),
           ("ATR", 1.0), ("ATR", 1.5), ("ATR", 2.0), ("ATR", 3.0), ("ATR", 4.0)]
DIRS = [("both", {}), ("long only", dict(enable_shorts=False)),
        ("short only", dict(enable_longs=False))]

_cache: dict = {}


def bars(tf: str, window=MODERN) -> pd.DataFrame:
    """The window itself, with nothing before it (used for buy & hold)."""
    start, end = window
    if tf not in _cache:
        _cache[tf] = pd.read_parquet(os.path.join(DATA, f"btcusd_bitstamp_{tf}.parquet"))
    d = _cache[tf]
    if start:
        d = d[d.index >= start]
    if end:
        d = d[d.index < end]
    return d


def go(tf: str, window, p: Params):
    """Run `p` over `window`, warming the moving averages up on the bars BEFORE it.

    Slicing a window and then computing a 200-period SMA inside it silently
    throws away the window's first 200 bars.  That is 11 % of a five-year daily
    window and 77 % of a five-year weekly one, so the averages are fed from
    prior history and only entries are gated to the window.
    """
    start, end = window
    full = bars(tf, (None, end))
    warm = max(p.sma_slow, p.atr_len) + 2
    if start is None:
        return run(full, p, tf)
    pos = int(full.index.searchsorted(pd.Timestamp(start, tz="UTC")))
    if pos >= len(full):
        return run(full.iloc[:0], p, tf)
    return run(full.iloc[max(0, pos - warm):], p, tf, trade_from=full.index[pos])


def cfg(sep, slm, slv, **kw) -> Params:
    base = dict(sep_mode="percent", min_separation_pct=sep, sl_mode=slm,
                sl_pct=(slv or 0.0) if slm == "Percent" else 0.0,
                atr_mult=(slv or 0.0) if slm == "ATR" else 2.0,
                qty_mode="notional", qty_notional=10_000.0)
    base.update(REAL)
    base.update(kw)
    return Params(**base)


def buy_hold(tf: str, window) -> dict:
    d = bars(tf, window)
    ret = d["close"].iloc[-1] / d["close"].iloc[0] - 1
    yrs = (d.index[-1] - d.index[0]).days / 365.25
    eq = d["close"] / d["close"].iloc[0]
    return {"label": "BUY & HOLD", "timeframe": tf,
            "start": d.index[0].date().isoformat(), "end": d.index[-1].date().isoformat(),
            "net_profit_pct": round(ret * 100, 2),
            "cagr_pct": round(((1 + ret) ** (1 / yrs) - 1) * 100, 2),
            "max_dd_pct": round((eq / eq.cummax() - 1).min() * 100, 2),
            "exposure_pct": 100.0}


# --------------------------------------------------------------------------
def phase1() -> pd.DataFrame:
    """Pine defaults, verbatim: 1 BTC per trade on a $100k account."""
    rows = []
    for tf in TFS:
        for win, tag in [(MODERN, "2017+"), (("2024-01-01", None), "2024+")]:
            p = Params(qty_mode="fixed", qty_fixed=1.0, **PINE)
            rows.append(summary(go(tf, win, p), f"Pine defaults ({tag})"))
    return pd.DataFrame(rows)


def phase2() -> pd.DataFrame:
    """Percent adaptation swept in-sample, then measured out-of-sample."""
    rows = []
    for tf, sep, (slm, slv), (dlbl, dkw) in itertools.product(TFS, SEP_GRID, SL_GRID, DIRS):
        p = cfg(sep, slm, slv, **dkw)
        a = summary(go(tf, IS, p))
        b = summary(go(tf, OOS_FWD, p))
        rows.append({
            "timeframe": tf, "sep_pct": sep, "direction": dlbl,
            "sl_kind": slm, "sl_val": slv,
            "is_trades": a["trades"], "is_wr": a["win_rate"], "is_pf": a["profit_factor"],
            "is_net": a["net_profit"], "is_avg_pct": a["avg_trade_pct"],
            "oos_trades": b["trades"], "oos_wr": b["win_rate"], "oos_pf": b["profit_factor"],
            "oos_net": b["net_profit"], "oos_avg_pct": b["avg_trade_pct"],
        })
    return pd.DataFrame(rows)


def phase3(best: dict) -> dict:
    tf, sep, slm, slv = best["tf"], best["sep"], best["slm"], best["slv"]
    dkw = best["dkw"]
    out = {"best": best}
    r = go(tf, MODERN, cfg(sep, slm, slv, **dkw))
    out["summary"] = pd.DataFrame([summary(r, "best config, 2017+")])
    out["yearly"] = yearly(r)
    out["trades"] = trades_frame(r)

    rows = []
    for lbl, win in [("in-sample 2017-2021", IS), ("OOS forward 2022-2026", OOS_FWD),
                     ("OOS backward 2012-2016", OOS_BACK), ("full 2012-2026", FULL)]:
        rows.append(summary(go(tf, win, cfg(sep, slm, slv, **dkw)), lbl))
    out["periods"] = pd.DataFrame(rows)

    rows = []
    for lbl, kw in [("both directions", {}),
                    ("long only", dict(enable_shorts=False)),
                    ("short only", dict(enable_longs=False)),
                    ("Pine costs ($2.5/contract)", PINE),
                    ("realistic 0.05%/side", REAL),
                    ("high cost 0.10%/side", dict(REAL, commission_pct=0.10)),
                    ("zero cost", dict(commission_per_contract=0.0, commission_pct=0.0,
                                       slippage_ticks=0.0, mintick=1.0)),
                    ("TP 200SMA dynamic", {}),
                    ("TP 200SMA locked at entry", dict(sma_target_behaviour="Locked at Entry")),
                    ("SMA 20/200", dict(sma_fast=20, sma_slow=200)),
                    ("SMA 50/100", dict(sma_fast=50, sma_slow=100)),
                    ("SMA 100/400", dict(sma_fast=100, sma_slow=400)),
                    ("SMA 50/300", dict(sma_fast=50, sma_slow=300))]:
        merged = dict(dkw)
        merged.update(kw)
        rows.append(summary(go(tf, MODERN, cfg(sep, slm, slv, **merged)), lbl))
    out["variants"] = pd.DataFrame(rows)

    pe = cfg(sep, slm, slv, **dkw)
    pe.qty_mode, pe.qty_pct_equity = "pct_equity", 100.0
    rc = go(tf, MODERN, pe)
    out["compound"] = pd.DataFrame([summary(rc, "100% of equity per trade, compounding")])
    out["equity"] = rc.equity
    return out


def phase4(p2: pd.DataFrame) -> pd.DataFrame:
    """Every in-sample winner: does it hold up out-of-sample and without its best trade?"""
    win = p2[(p2.is_pf > 1.0) & (p2.is_trades >= 30)].copy()
    rows = []
    for _, w in win.iterrows():
        dkw = dict(DIRS[[d[0] for d in DIRS].index(w.direction)][1])
        slv = None if w.sl_kind == "1R to TP" else float(w.sl_val)
        p = cfg(float(w.sep_pct), w.sl_kind, slv, **dkw)
        rb = go(w.timeframe, OOS_BACK, p)
        rf = go(w.timeframe, MODERN, p)
        pnl = np.array([t.pnl for t in rf.trades])
        if len(pnl) == 0:
            continue
        drop = np.delete(pnl, pnl.argmax())
        gp, gl = drop[drop > 0].sum(), -drop[drop <= 0].sum()
        top3 = np.sort(pnl)[-3:].sum()
        gross_profit = pnl[pnl > 0].sum()
        sb = summary(rb)
        rows.append({
            "timeframe": w.timeframe, "direction": w.direction, "sep_pct": w.sep_pct,
            "sl": (w.sl_kind if slv is None
                   else (f"{slv}xATR" if w.sl_kind == "ATR" else f"{slv}%")),
            "is_pf": w.is_pf, "is_trades": w.is_trades,
            "oos_fwd_pf": w.oos_pf, "oos_fwd_trades": w.oos_trades,
            "oos_back_pf": sb["profit_factor"], "oos_back_trades": sb["trades"],
            "pf_2017plus": round(float(gross_profit / -pnl[pnl <= 0].sum()), 3) if (pnl <= 0).any() else np.inf,
            "pf_wo_best_trade": round(float(gp / gl), 3) if gl > 0 else np.inf,
            "top3_share_of_gross_profit": round(100 * float(top3 / gross_profit), 1) if gross_profit > 0 else np.nan,
        })
    return pd.DataFrame(rows)


def phase5_weekly() -> dict:
    """1D and 1W head to head, and everything that could make 1W work.

    The standard screen cannot judge 1W at all: a 200-week SMA is 3.8 years of
    warmup and the strategy fires so rarely that no window reaches the 30-trade
    minimum.  So the weekly grid is run over the whole history instead, and the
    SMA pair is varied down to lengths a weekly chart can actually support.
    """
    out = {}

    rows = []
    for tf in ["1d", "1w"]:
        for win, tag in [(MODERN, "2017+"), (FULL, "2012+")]:
            p = Params(qty_mode="fixed", qty_fixed=1.0, **PINE)
            rows.append(summary(go(tf, win, p), f"{tf} Pine defaults {tag}"))
    out["defaults"] = pd.DataFrame(rows)

    # the full adapted grid on 1W, over all available history
    rows = []
    for sep, (slm, slv), (dlbl, dkw) in itertools.product(SEP_GRID, SL_GRID, DIRS):
        p = cfg(sep, slm, slv, **dkw)
        s_ = summary(go("1w", FULL, p), f"sep {sep}% / {slm}{'' if slv is None else ' ' + str(slv)}")
        s_["sep_pct"], s_["sl_kind"], s_["sl_val"], s_["direction"] = sep, slm, slv, dlbl
        rows.append(s_)
    out["grid"] = pd.DataFrame(rows)

    # a 200-week average is 3.8 years -- try pairs a weekly chart can support
    rows = []
    for f, sl in [(50, 200), (20, 100), (20, 50), (10, 40), (5, 20), (4, 12)]:
        for slm, slv, lbl in [("Percent", 5.0, "5% stop"), ("1R to TP", None, "1R"),
                              ("ATR", 2.0, "2xATR")]:
            p = cfg(3.0, slm, slv, sma_fast=f, sma_slow=sl)
            s_ = summary(go("1w", FULL, p), f"SMA {f}/{sl} · {lbl}")
            s_["fast"], s_["slow"], s_["stop"] = f, sl, lbl
            rows.append(s_)
    out["smapairs"] = pd.DataFrame(rows)

    # does the answer depend on where the week is cut?
    rows = []
    for tf, lbl in [("1w", "weeks open Monday"), ("1w-sun", "weeks open Sunday")]:
        rows.append(summary(go(tf, FULL, Params(qty_mode="fixed", qty_fixed=1.0, **PINE)),
                            f"Pine defaults · {lbl}"))
        rows.append(summary(go(tf, FULL, cfg(3.0, "Percent", 5.0, sma_fast=10, sma_slow=40)),
                            f"SMA 10/40, 5% stop · {lbl}"))
    out["anchor"] = pd.DataFrame(rows)

    # how far away is the target on a weekly chart?
    rows = []
    for tf in ["1d", "1w"]:
        d = bars(tf, FULL)
        f_ = d.close.rolling(50).mean()
        s_ = d.close.rolling(200).mean()
        xu = (d.close > f_) & (d.close.shift(1) <= f_.shift(1))
        xd = (d.close < f_) & (d.close.shift(1) >= f_.shift(1))
        sig = (xu & (f_ < s_)) | (xd & (f_ > s_))
        dist = ((s_ - d.close).abs() / d.close * 100)[sig].dropna()
        rng = ((d.high - d.low) / d.close * 100).dropna()
        rows.append({"timeframe": tf, "bars": len(d), "signals": int(sig.sum()),
                     "median_target_pct": round(float(dist.median()), 2),
                     "p90_target_pct": round(float(dist.quantile(.9)), 2),
                     "median_bar_range_pct": round(float(rng.median()), 2),
                     "target_over_bar_range": round(float(dist.median() / rng.median()), 1)})
    out["geometry"] = pd.DataFrame(rows)
    return out


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    pd.set_option("display.width", 240, "display.max_columns", 40)

    print("=" * 108)
    print("PHASE 1  |  Pine defaults verbatim on BTC/USD  (1 BTC/trade, $100k, $2.5/contract, 2 ticks slip)")
    print("=" * 108)
    p1 = phase1()
    p1.to_csv(os.path.join(OUT, "phase1_pine_defaults.csv"), index=False)
    print(p1[["label", "timeframe", "trades", "win_rate", "profit_factor", "net_profit",
              "net_profit_pct", "max_dd_pct", "sl_exits", "tp_exits", "avg_loss_pct",
              "avg_bars_held"]].to_string(index=False))

    print("\n" + "=" * 108)
    print("PHASE 2  |  percent-of-price adaptation: selected on 2017-2021, measured on 2022-2026")
    print("=" * 108)
    p2 = phase2()
    p2.to_csv(os.path.join(OUT, "phase2_sweep.csv"), index=False)
    print(f"configurations tested: {len(p2)}")
    print(f"  profitable in-sample (PF>1, >=30 trades): "
          f"{len(p2[(p2.is_pf > 1) & (p2.is_trades >= 30)])}")
    print(f"  profitable in BOTH windows:               "
          f"{len(p2[(p2.is_pf > 1) & (p2.oos_pf > 1) & (p2.is_trades >= 30) & (p2.oos_trades >= 30)])}")
    print("\nBest in-sample PF per timeframe / direction:")
    g = (p2[p2.is_trades >= 30].sort_values("is_pf", ascending=False)
         .groupby(["timeframe", "direction"]).head(1)
         .sort_values(["timeframe", "is_pf"], ascending=[True, False]))
    print(g[["timeframe", "direction", "sep_pct", "sl_kind", "sl_val", "is_trades",
             "is_wr", "is_pf", "oos_trades", "oos_wr", "oos_pf"]].to_string(index=False))

    viable = p2[(p2.is_trades >= 30)].sort_values("is_pf", ascending=False)
    b = viable.iloc[0]
    best = {"tf": b.timeframe, "sep": float(b.sep_pct), "slm": b.sl_kind,
            "slv": (None if b.sl_kind == "1R to TP" else float(b.sl_val)),
            "direction": b.direction,
            "dkw": dict(DIRS[[d[0] for d in DIRS].index(b.direction)][1])}
    print(f"\nBEST IN-SAMPLE: {b.timeframe} {b.direction} sep {b.sep_pct}% "
          f"SL {b.sl_kind}{'' if b.sl_val != b.sl_val else ' ' + str(b.sl_val) + '%'}  "
          f"IS PF {b.is_pf} ({b.is_trades} trades)  ->  OOS PF {b.oos_pf} ({b.oos_trades} trades)")

    print("\n" + "=" * 108)
    print("PHASE 3  |  deep dive on the best in-sample configuration")
    print("=" * 108)
    d3 = phase3(best)
    show = ["label", "start", "end", "trades", "win_rate", "profit_factor", "net_profit",
            "net_profit_pct", "cagr_pct", "max_dd_pct", "sharpe", "avg_trade_pct", "exposure_pct"]
    for k in ["summary", "periods", "variants", "compound"]:
        df = d3[k]
        df.to_csv(os.path.join(OUT, f"phase3_{k}.csv"), index=False)
        print(f"\n--- {k} ---")
        print(df[[c for c in show if c in df.columns]].to_string(index=False))
    print("\n--- per calendar year ---")
    print(d3["yearly"].to_string(index=False))
    d3["yearly"].to_csv(os.path.join(OUT, "phase3_yearly.csv"), index=False)
    d3["trades"].to_csv(os.path.join(OUT, "phase3_trades.csv"), index=False)
    d3["equity"].to_frame("equity").to_csv(os.path.join(OUT, "phase3_equity.csv"))

    print("\n--- buy & hold, same windows ---")
    print(pd.DataFrame([buy_hold(best["tf"], MODERN), buy_hold(best["tf"], IS),
                        buy_hold(best["tf"], OOS_FWD), buy_hold(best["tf"], FULL)
                        ]).to_string(index=False))

    print("\n" + "=" * 108)
    print("PHASE 4  |  fragility screen of every in-sample winner")
    print("=" * 108)
    p4 = phase4(p2)
    p4.to_csv(os.path.join(OUT, "phase4_fragility.csv"), index=False)
    if len(p4):
        print(p4.sort_values("is_pf", ascending=False).to_string(index=False))
        surv = p4[(p4.oos_fwd_pf > 1) & (p4.oos_back_pf > 1) & (p4.pf_wo_best_trade > 1)]
        print(f"\nconfigurations profitable in-sample: {len(p4)}")
        print(f"still profitable forward-OOS, backward-OOS and after deleting their best "
              f"single trade: {len(surv)}")
        if len(surv):
            print(surv.to_string(index=False))
    else:
        print("no configuration was profitable in-sample with >=30 trades")

    print("\n" + "=" * 108)
    print("PHASE 5  |  daily vs weekly")
    print("=" * 108)
    d5 = phase5_weekly()
    show = ["label", "start", "end", "trades", "win_rate", "profit_factor", "net_profit_pct",
            "max_dd_pct", "avg_trade_pct", "sl_exits", "tp_exits", "exposure_pct"]
    for k in ["defaults", "anchor", "geometry"]:
        print(f"\n--- {k} ---")
        df = d5[k]
        print(df[[c for c in show if c in df.columns]].to_string(index=False)
              if k != "geometry" else df.to_string(index=False))
        df.to_csv(os.path.join(OUT, f"phase5_{k}.csv"), index=False)
    g = d5["grid"].sort_values("profit_factor", ascending=False)
    g.to_csv(os.path.join(OUT, "phase5_weekly_grid.csv"), index=False)
    print(f"\n--- weekly grid: {len(g)} configurations over the full history ---")
    print(f"  configurations reaching 30 trades: {int((g.trades >= 30).sum())}"
          f"   ·  reaching 10 trades: {int((g.trades >= 10).sum())}")
    print(f"  median trades per configuration: {int(g.trades.median())}"
          f"   ·  median profit factor: {g.profit_factor.median():.3f}")
    print(f"  profitable (PF>1): {int((g.profit_factor > 1).sum())}"
          f"   ·  of those, with >=10 trades: {int(((g.profit_factor > 1) & (g.trades >= 10)).sum())}")
    print(g[["sep_pct", "sl_kind", "sl_val", "direction", "trades", "win_rate",
             "profit_factor", "avg_trade_pct"]].head(8).to_string(index=False))
    sp = d5["smapairs"].sort_values("profit_factor", ascending=False)
    sp.to_csv(os.path.join(OUT, "phase5_weekly_smapairs.csv"), index=False)
    print("\n--- weekly with shorter SMA pairs (full history, 3% filter) ---")
    print(sp[["label", "trades", "win_rate", "profit_factor", "avg_trade_pct",
              "net_profit_pct", "max_dd_pct"]].to_string(index=False))


if __name__ == "__main__":
    main()
