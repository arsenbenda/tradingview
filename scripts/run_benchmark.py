#!/usr/bin/env python3
"""Esegue il benchmark Donchian sull'universo a sei asset.

Un solo set di parametri per tutti — parametri Turtle pubblicati, non adattati a
questi dati. È la barra di riferimento: ogni strategia successiva va confrontata
con questi numeri, non con il buy & hold.

Vengono prodotti tre scenari:
  * long/short, costi stimati
  * solo long, costi stimati — quantifica cosa costa il vincolo long-only
  * long/short, costi doppi — se una strategia sopravvive solo al primo
    scenario, non è una strategia

Il periodo di default è quello comune all'universo (`data.DEFAULT_START`), lo
stesso di ogni altro runner: senza, questo script girerebbe sulla storia piena di
ciascuna serie e produrrebbe numeri non confrontabili con nessun altro risultato
del progetto.

Uso: python3 scripts/run_benchmark.py [--start AAAA-MM-GG]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine import backtest, costs as cost_table, data, metrics
from engine.strategies import donchian

CAPITAL = 100_000.0
OUT = pathlib.Path(__file__).resolve().parent.parent / "results"


def run_scenario(universe: dict[str, pd.DataFrame], *, allow_short: bool, cost_mult: float):
    results = {}
    for name, df in universe.items():
        sig = donchian.signals(df, allow_short=allow_short)
        results[name] = backtest.run(
            df,
            entry_long=sig["entry_long"],
            exit_long=sig["exit_long"],
            entry_short=sig["entry_short"],
            exit_short=sig["exit_short"],
            stop_distance=sig["stop_distance"],
            costs=cost_table.for_asset(name, cost_mult),
            risk_pct=0.01,
            initial_capital=CAPITAL,
        )
    return results


def buy_and_hold(df: pd.DataFrame) -> metrics.Stats:
    eq = CAPITAL * df["close"] / df["close"].iloc[0]
    fake = backtest.Result(equity=eq, trades=[], exposure=1.0)
    return metrics.compute(fake, CAPITAL)


def table(rows: list[tuple[str, metrics.Stats]], title: str) -> None:
    print(f"\n{title}")
    print(f"{'asset':9s} {'trade':>6s} {'CAGR':>8s} {'maxDD':>8s} {'MAR':>6s} "
          f"{'Sharpe':>7s} {'PF':>6s} {'win%':>6s} {'avgR':>6s} {'espos.':>7s}")
    for name, s in rows:
        print(f"{name:9s} {s.trades:6d} {s.cagr:7.1%} {s.max_dd:7.1%} {s.mar:6.2f} "
              f"{s.sharpe:7.2f} {s.profit_factor:6.2f} {s.win_rate:5.0%} {s.avg_r:6.2f} {s.exposure:6.0%}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=data.DEFAULT_START,
                    help="limita tutte le serie da questa data (default: il periodo "
                         "comune dell'universo; usare --start 1900-01-01 per la storia piena)")
    args = ap.parse_args()

    universe = data.load_universe()
    if args.start:
        universe = {k: v[v.index >= args.start] for k, v in universe.items()}
    start, end = data.common_period(universe)
    print(f"universo: {', '.join(universe)}")
    print(f"periodo comune: {start.date()} -> {end.date()}")
    print(f"parametri Donchian: ingresso {donchian.ENTRY_LEN}, uscita {donchian.EXIT_LEN}, "
          f"stop {donchian.STOP_ATR}xATR({donchian.ATR_LEN}), rischio 1%/trade — identici su tutti gli asset")

    scenarios = {
        "LONG/SHORT — costi stimati": dict(allow_short=True, cost_mult=1.0),
        "SOLO LONG — costi stimati": dict(allow_short=False, cost_mult=1.0),
        "LONG/SHORT — costi doppi": dict(allow_short=True, cost_mult=2.0),
    }

    summary = {}
    for label, kwargs in scenarios.items():
        results = run_scenario(universe, **kwargs)
        rows = [(n, metrics.compute(r, CAPITAL)) for n, r in results.items()]
        pf_eq = metrics.portfolio_equity(results, CAPITAL)
        pf_stats = metrics.compute(backtest.Result(equity=pf_eq, trades=[t for r in results.values() for t in r.trades],
                                                   exposure=sum(r.exposure for r in results.values()) / len(results)),
                                   CAPITAL)
        table(rows + [("PORTAFOGLIO", pf_stats)], label)
        summary[label] = {n: s.as_dict() for n, s in rows} | {"PORTAFOGLIO": pf_stats.as_dict()}

    table([(n, buy_and_hold(df)) for n, df in universe.items()], "BUY & HOLD (riferimento)")

    OUT.mkdir(exist_ok=True)
    (OUT / "benchmark_donchian.json").write_text(json.dumps(summary, indent=2, default=float))
    print(f"\nrisultati salvati in results/benchmark_donchian.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
