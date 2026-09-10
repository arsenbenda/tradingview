"""Export a compact JSON bundle of backtest results for the written report."""
import json
import os
import numpy as np
import pandas as pd

from trm_engine import Params, run
from metrics import summary
import run_btc as R

OUT = R.OUT
os.makedirs(OUT, exist_ok=True)

p1 = pd.read_csv(os.path.join(OUT, "phase1_pine_defaults.csv"))
p2 = pd.read_csv(os.path.join(OUT, "phase2_sweep.csv"))
p4 = pd.read_csv(os.path.join(OUT, "phase4_fragility.csv"))
yr = pd.read_csv(os.path.join(OUT, "phase3_yearly.csv"))
per = pd.read_csv(os.path.join(OUT, "phase3_periods.csv"))
var = pd.read_csv(os.path.join(OUT, "phase3_variants.csv"))

# equity of the best in-sample config, compounding, vs BTC, weekly, 2017+
best = dict(tf="1d", sep=5.0, slm="Percent", slv=0.625, dkw={})
p = R.cfg(best["sep"], best["slm"], best["slv"])
p.qty_mode, p.qty_pct_equity = "pct_equity", 100.0
d = R.bars("1d", R.MODERN)
r = run(d, p, "1d")
eq = r.equity.resample("1W").last().dropna()
btc = d["close"].resample("1W").last().dropna().reindex(eq.index).ffill()
curve = [{"t": t.strftime("%Y-%m-%d"),
          "s": round(float(v) / 100_000 * 100, 2),
          "b": round(float(b) / float(btc.iloc[0]) * 100, 2)}
         for t, v, b in zip(eq.index, eq.values, btc.values)]

bundle = {
    "meta": {
        "symbol": "BTC/USD (Bitstamp spot)",
        "source": "https://github.com/ff137/bitstamp-btcusd-minute-data",
        "strategy": "Trend Rebalance Map [Herman] v1.1",
        "strategy_source": "https://github.com/HermanTrading/Trend-Rebalance-Map-Herman-",
        "data_start": str(R.bars("1d", R.FULL).index[0].date()),
        "data_end": str(R.bars("1d", R.FULL).index[-1].date()),
        "minutes": 7_727_131,
        "configs_tested": int(len(p2)),
        "is_window": "2017-01-01 .. 2021-12-31",
        "oos_fwd": "2022-01-01 .. 2026-09-10",
        "oos_back": "2012-01-01 .. 2016-12-31",
        "median_is_pf": round(float(p2.is_pf.median()), 3),
        "median_oos_pf": round(float(p2.oos_pf.median()), 3),
        "is_winners": int(((p2.is_pf > 1) & (p2.is_trades >= 30)).sum()),
        "both_windows": int(((p2.is_pf > 1) & (p2.oos_pf > 1) &
                             (p2.is_trades >= 30) & (p2.oos_trades >= 30)).sum()),
        "survivors": 0,
    },
    "pine_defaults": p1[["timeframe", "label", "trades", "win_rate", "profit_factor",
                         "net_profit_pct", "max_dd_pct", "sl_exits", "tp_exits"]].to_dict("records"),
    "scatter": [{"tf": t, "x": round(min(float(a), 5.0), 3), "y": round(min(float(b), 5.0), 3),
                 "n": int(n)}
                for t, a, b, n in zip(p2.timeframe, p2.is_pf.fillna(0), p2.oos_pf.fillna(0),
                                      p2.is_trades)],
    "by_tf": (p2.groupby("timeframe")
              .apply(lambda g: {"configs": int(len(g)),
                                "is_pf_gt1": int((g.is_pf > 1).sum()),
                                "oos_pf_gt1": int((g.oos_pf > 1).sum()),
                                "median_oos_pf": round(float(g.oos_pf.median()), 3)},
                     include_groups=False).to_dict()),
    "by_dir": (p2.groupby("direction")
               .apply(lambda g: {"median_is_pf": round(float(g.is_pf.median()), 3),
                                 "median_oos_pf": round(float(g.oos_pf.median()), 3)},
                      include_groups=False).to_dict()),
    "yearly": yr.to_dict("records"),
    "periods": per[["label", "trades", "win_rate", "profit_factor", "net_profit_pct",
                    "max_dd_pct"]].to_dict("records"),
    "variants": var[["label", "trades", "win_rate", "profit_factor", "net_profit_pct"]].to_dict("records"),
    "fragility": p4.sort_values("is_pf", ascending=False).head(12).to_dict("records"),
    "equity": curve,
    "buyhold": [R.buy_hold("1d", w) for w in [R.MODERN, R.IS, R.OOS_FWD, R.FULL]],
    "target_distance": [
        {"tf": "1h", "median_target_pct": 2.10, "p90_target_pct": 7.01,
         "median_sep_pct": 2.42, "median_bar_range_pct": 0.68},
        {"tf": "4h", "median_target_pct": 4.72, "p90_target_pct": 15.60,
         "median_sep_pct": 5.49, "median_bar_range_pct": 1.46},
        {"tf": "1d", "median_target_pct": 16.66, "p90_target_pct": 36.95,
         "median_sep_pct": 19.42, "median_bar_range_pct": 3.98},
    ],
}


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) or np.isinf(o) else round(float(o), 4)
    if isinstance(o, float):
        return None if (np.isnan(o) or np.isinf(o)) else o
    return o


path = os.path.join(OUT, "report_data.json")
json.dump(clean(bundle), open(path, "w"), indent=1)
print("wrote", path, os.path.getsize(path), "bytes")
print("equity points:", len(curve), curve[0], curve[-1])
