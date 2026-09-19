#!/usr/bin/env python3
"""Le due ipotesi Ichimoku rimaste aperte.

A) Ichimoku come **generatore di segnale** simmetrico long/short. Stop, rischio,
   costi e motore identici al benchmark: l'unica cosa che cambia e' cosa decide
   di entrare.
B) Ichimoku come **meccanismo di uscita** sopra gli ingressi del benchmark. E'
   l'unico pezzo delle strategie Pine che non compete con il breakout.

Uso: python3 scripts/run_ichimoku_tests.py
"""
from __future__ import annotations

import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine import backtest, costs as cost_table, data, metrics
from engine.strategies import donchian, ichimoku_tf

CAPITAL = 100_000.0
OUT = pathlib.Path(__file__).resolve().parent.parent / "results"


def portfolio(results):
    rows = {n: metrics.compute(r, CAPITAL) for n, r in results.items()}
    eq = metrics.portfolio_equity(results, CAPITAL)
    pf = metrics.compute(
        backtest.Result(equity=eq, trades=[t for r in results.values() for t in r.trades],
                        exposure=sum(r.exposure for r in results.values()) / len(results)), CAPITAL)
    return pf, rows


def line(label, pf, base=None, per_asset=None, base_assets=None):
    delta = f"{pf.mar - base.mar:+6.2f}" if base else "      "
    better = ""
    if per_asset and base_assets:
        b = sum(1 for a, s in per_asset.items()
                if s.mar == s.mar and base_assets[a].mar == base_assets[a].mar
                and s.mar > base_assets[a].mar)
        better = f"{b}/6"
    print(f"{label:24s} {pf.mar:6.2f} {delta} {pf.sharpe:7.2f} {pf.cagr:7.1%} "
          f"{pf.max_dd:7.1%} {pf.profit_factor:6.2f} {pf.trades:6d} {better:>5s}")


def main() -> int:
    universe = {k: v[v.index >= data.DEFAULT_START] for k, v in data.load_universe().items()}
    start, end = data.common_period(universe)
    print(f"periodo: {start.date()} -> {end.date()} | un solo set di parametri | costi per asset")
    head = f"{'':24s} {'MAR':>6s} {'delta':>6s} {'Sharpe':>7s} {'CAGR':>7s} {'maxDD':>7s} {'PF':>6s} {'trade':>6s} {'best':>5s}"

    base_res = {n: backtest.run_strategy(df, donchian.DonchianWithExit(exit_mode="canale"),
                                         costs=cost_table.for_asset(n), risk_pct=0.01,
                                         initial_capital=CAPITAL)
                for n, df in universe.items()}
    base_pf, base_assets = portfolio(base_res)

    summary = {"base": base_pf.as_dict()}

    print("\nA) ICHIMOKU COME SEGNALE — simmetrico long/short, stop e costi del benchmark")
    print(head)
    line("Donchian (benchmark)", base_pf)
    for mode in ichimoku_tf.MODES:
        res = {}
        for n, df in universe.items():
            s = ichimoku_tf.signals(df, mode=mode)
            res[n] = backtest.run(df, entry_long=s["entry_long"], exit_long=s["exit_long"],
                                  entry_short=s["entry_short"], exit_short=s["exit_short"],
                                  stop_distance=s["stop_distance"],
                                  costs=cost_table.for_asset(n), risk_pct=0.01,
                                  initial_capital=CAPITAL)
        pf, rows = portfolio(res)
        line(f"ichimoku {mode}", pf, base_pf, rows, base_assets)
        summary[f"signal_{mode}"] = pf.as_dict()

    print("\nB) ICHIMOKU COME USCITA — ingressi del benchmark invariati")
    print(head)
    for mode in donchian.DonchianWithExit.EXIT_MODES:
        res = {n: backtest.run_strategy(df, donchian.DonchianWithExit(exit_mode=mode),
                                        costs=cost_table.for_asset(n), risk_pct=0.01,
                                        initial_capital=CAPITAL)
               for n, df in universe.items()}
        pf, rows = portfolio(res)
        etichetta = "canale 20 (benchmark)" if mode == "canale" else mode
        line(etichetta, pf, None if mode == "canale" else base_pf,
             None if mode == "canale" else rows, base_assets)
        summary[f"exit_{mode}"] = pf.as_dict()

    OUT.mkdir(exist_ok=True)
    (OUT / "ichimoku_tests.json").write_text(json.dumps(summary, indent=2, default=float))
    print("\nrisultati in results/ichimoku_tests.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
