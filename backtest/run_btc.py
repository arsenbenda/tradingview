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
TFS = ["5m", "15m", "1h", "4h", "1d"]

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
    start, end = window
    if tf not in _cache:
        _cache[tf] = pd.read_parquet(os.path.join(DATA, f"btcusd_bitstamp_{tf}.parquet"))
    d = _cache[tf]
    if start:
        d = d[d.index >= start]
    if end:
        d = d[d.index < end]
    return d


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
            rows.append(summary(run(bars(tf, win), p, tf), f"Pine defaults ({tag})"))
    return pd.DataFrame(rows)


def phase2() -> pd.DataFrame:
    """Percent adaptation swept in-sample, then measured out-of-sample."""
    rows = []
    for tf, sep, (slm, slv), (dlbl, dkw) in itertools.product(TFS, SEP_GRID, SL_GRID, DIRS):
        p = cfg(sep, slm, slv, **dkw)
        a = summary(run(bars(tf, IS), p, tf))
        b = summary(run(bars(tf, OOS_FWD), p, tf))
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
    r = run(bars(tf, MODERN), cfg(sep, slm, slv, **dkw), tf)
    out["summary"] = pd.DataFrame([summary(r, "best config, 2017+")])
    out["yearly"] = yearly(r)
    out["trades"] = trades_frame(r)

    rows = []
    for lbl, win in [("in-sample 2017-2021", IS), ("OOS forward 2022-2026", OOS_FWD),
                     ("OOS backward 2012-2016", OOS_BACK), ("full 2012-2026", FULL)]:
        rows.append(summary(run(bars(tf, win), cfg(sep, slm, slv, **dkw), tf), lbl))
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
        rows.append(summary(run(bars(tf, MODERN), cfg(sep, slm, slv, **merged), tf), lbl))
    out["variants"] = pd.DataFrame(rows)

    pe = cfg(sep, slm, slv, **dkw)
    pe.qty_mode, pe.qty_pct_equity = "pct_equity", 100.0
    rc = run(bars(tf, MODERN), pe, tf)
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
        rb = run(bars(w.timeframe, OOS_BACK), p, w.timeframe)
        rf = run(bars(w.timeframe, MODERN), p, w.timeframe)
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


if __name__ == "__main__":
    main()
