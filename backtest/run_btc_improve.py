"""
Can Trend Rebalance Map be repaired on BTC/USD?

run_btc.py asks whether the published strategy works. This asks the harder
question: given everything that test diagnosed, can the premise be modified
into something that clears profit factor 1 and *stays* there.

Each added degree of freedom answers one diagnosed failure, so the search space
stays small and motivated rather than dredged:

  target too far      -> "Retrace": take part of the way to the SMA200 instead
                         of the whole trip (a 4:1..35:1 demand on BTC)
  filter backwards    -> a separation CAP: stand down when the pair is stretched
                         beyond it, which is a trend, not a rubber band
  short side hopeless -> long-only is tested as a first-class option
  dead trades         -> an optional time stop

Selection is on 2017-2021 only. A configuration has to clear break-even there
AND forward on 2022-2026 AND backward on 2012-2016 AND survive the deletion of
its single best trade before it counts as anything.
"""
from __future__ import annotations

import itertools
import os

import numpy as np
import pandas as pd

from metrics import summary
from trm_engine import Params
import run_btc as R

OUT = R.OUT
TFS = ["15m", "1h", "4h", "1d"]
RETRACE = [0.25, 0.5, 0.75, 1.0]
STOPS = [("ATR", 1.0), ("ATR", 2.0), ("ATR", 3.0), ("Percent", 3.0), ("Percent", 5.0)]
SEP_MIN = [0.5, 2.0]
SEP_MAX = [0.0, 10.0, 20.0]
DIRS = [("long only", dict(enable_shorts=False)), ("both", {})]
MIN_TRADES = 40


def cfg(sep_min, sep_max, slm, slv, retrace, **kw) -> Params:
    p = R.cfg(sep_min, slm, slv, **kw)
    p.max_separation_pct = sep_max
    p.tp_mode = "Retrace"
    p.retrace_frac = retrace
    return p


def screen() -> pd.DataFrame:
    rows = []
    for tf, (dlbl, dkw), rt, (slm, slv), smin, smax in itertools.product(
            TFS, DIRS, RETRACE, STOPS, SEP_MIN, SEP_MAX):
        p = cfg(smin, smax, slm, slv, rt, **dkw)
        a = summary(R.go(tf, R.IS, p))
        if a["trades"] < MIN_TRADES or not (a["profit_factor"] > 1):
            rows.append({"tf": tf, "dir": dlbl, "retrace": rt, "stop": f"{slv}{'xATR' if slm=='ATR' else '%'}",
                         "sep_min": smin, "sep_max": smax, "is_trades": a["trades"],
                         "is_pf": a["profit_factor"], "passed_is": False})
            continue
        b = summary(R.go(tf, R.OOS_FWD, p))
        c = summary(R.go(tf, R.OOS_BACK, p))
        m = R.go(tf, R.MODERN, p)
        pnl = np.array([t.pnl for t in m.trades])
        drop = np.delete(pnl, pnl.argmax()) if len(pnl) else pnl
        pf_wo = (drop[drop > 0].sum() / -drop[drop <= 0].sum()) if (drop <= 0).any() else np.inf
        gp = pnl[pnl > 0].sum()
        rows.append({
            "tf": tf, "dir": dlbl, "retrace": rt, "stop": f"{slv}{'xATR' if slm=='ATR' else '%'}",
            "sep_min": smin, "sep_max": smax,
            "is_trades": a["trades"], "is_pf": a["profit_factor"], "passed_is": True,
            "oos_fwd_pf": b["profit_factor"], "oos_fwd_trades": b["trades"],
            "oos_back_pf": c["profit_factor"], "oos_back_trades": c["trades"],
            "pf_wo_best": round(float(pf_wo), 3),
            "top1_share": round(100 * float(pnl.max() / gp), 1) if gp > 0 else np.nan,
            "worst_trade_pct": round(100 * min(t.pnl_pct for t in m.trades), 2) if m.trades else np.nan,
        })
    return pd.DataFrame(rows)


def main() -> None:
    pd.set_option("display.width", 240, "display.max_columns", 40)
    df = screen()
    df.to_csv(os.path.join(OUT, "phase6_repair_search.csv"), index=False)
    n = len(df)
    ok_is = df[df.passed_is]
    print("=" * 104)
    print("PHASE 6  |  can the premise be repaired on BTC?")
    print("=" * 104)
    print(f"configurations tested: {n}")
    print(f"  cleared break-even in-sample with >= {MIN_TRADES} trades: {len(ok_is)}")
    if not len(ok_is):
        print("  nothing to carry forward")
        return
    s1 = ok_is[ok_is.oos_fwd_pf > 1]
    s2 = s1[s1.oos_back_pf > 1]
    s3 = s2[s2.pf_wo_best > 1]
    print(f"  ... and profitable forward 2022-2026:              {len(s1)}")
    print(f"  ... and profitable backward 2012-2016:             {len(s2)}")
    print(f"  ... and still profitable minus its best trade:     {len(s3)}")
    cols = ["tf", "dir", "retrace", "stop", "sep_min", "sep_max", "is_trades", "is_pf",
            "oos_fwd_trades", "oos_fwd_pf", "oos_back_pf", "pf_wo_best", "top1_share"]
    print("\n--- best 12 by in-sample PF ---")
    print(ok_is.sort_values("is_pf", ascending=False)[cols].head(12).to_string(index=False))
    if len(s1):
        print("\n--- cleared both the selection window and forward ---")
        print(s1.sort_values("oos_fwd_pf", ascending=False)[cols].to_string(index=False))
    if len(s3):
        print("\n--- SURVIVORS of the full screen ---")
        print(s3.sort_values("is_pf", ascending=False)[cols].to_string(index=False))


if __name__ == "__main__":
    main()
