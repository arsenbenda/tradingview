#!/usr/bin/env python3
"""Confronta le strategie portate dal Pine con il benchmark Donchian.

Stesso periodo, stessi costi, un solo set di parametri per tutti gli asset.
Ogni strategia viene eseguita anche nella variante ``size_at_signal``, che
riproduce il difetto del Pine (quantità e stop ancorati al close della barra di
segnale invece che al prezzo di fill), così il suo costo si misura.

Uso: python3 scripts/compare_strategies.py [--start AAAA-MM-GG]
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
from engine.strategies.confluence import ConfluenceV32
from engine.strategies.sanyaku import SanyakuV55

CAPITAL = 100_000.0
OUT = pathlib.Path(__file__).resolve().parent.parent / "results"


def run_donchian(df, name, cost_mult=1.0, **_):
    sig = donchian.signals(df, allow_short=True)
    return backtest.run(
        df, entry_long=sig["entry_long"], exit_long=sig["exit_long"],
        entry_short=sig["entry_short"], exit_short=sig["exit_short"],
        stop_distance=sig["stop_distance"],
        costs=cost_table.for_asset(name, cost_mult), risk_pct=0.01, initial_capital=CAPITAL,
    )


def run_sanyaku(df, name, cost_mult=1.0, size_at_signal=False, **kwargs):
    return backtest.run_strategy(
        df, SanyakuV55(**kwargs),
        costs=cost_table.for_asset(name, cost_mult), risk_pct=0.01,
        initial_capital=CAPITAL, max_notional_pct=0.60, size_at_signal=size_at_signal,
    )


def run_confluence(df, name, cost_mult=1.0, size_at_signal=False, **kwargs):
    return backtest.run_strategy(
        df, ConfluenceV32(**kwargs),
        costs=cost_table.for_asset(name, cost_mult), risk_pct=0.01,
        initial_capital=CAPITAL, size_at_signal=size_at_signal,
    )


def evaluate(universe, runner, **kwargs):
    results = {n: runner(df, n, **kwargs) for n, df in universe.items()}
    rows = [(n, metrics.compute(r, CAPITAL)) for n, r in results.items()]
    pf_eq = metrics.portfolio_equity(results, CAPITAL)
    pf = metrics.compute(
        backtest.Result(equity=pf_eq,
                        trades=[t for r in results.values() for t in r.trades],
                        exposure=sum(r.exposure for r in results.values()) / len(results)),
        CAPITAL,
    )
    return rows, pf, results


def table(rows, title):
    print(f"\n{title}")
    print(f"{'asset':9s} {'trade':>6s} {'CAGR':>8s} {'maxDD':>8s} {'MAR':>6s} "
          f"{'Sharpe':>7s} {'PF':>6s} {'win%':>6s} {'avgR':>6s} {'espos.':>7s}")
    for name, s in rows:
        print(f"{name:9s} {s.trades:6d} {s.cagr:7.1%} {s.max_dd:7.1%} {s.mar:6.2f} "
              f"{s.sharpe:7.2f} {s.profit_factor:6.2f} {s.win_rate:5.0%} {s.avg_r:6.2f} {s.exposure:6.0%}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=data.DEFAULT_START)
    args = ap.parse_args()

    universe = {k: v[v.index >= args.start] for k, v in data.load_universe().items()}
    start, end = data.common_period(universe)
    print(f"periodo: {start.date()} -> {end.date()} | costi per asset | un solo set di parametri")

    summary = {}

    rows, pf, _ = evaluate(universe, run_donchian)
    table(rows + [("PORTAFOGLIO", pf)], "BENCHMARK — Donchian 55/20 long-short")
    summary["donchian"] = {n: s.as_dict() for n, s in rows} | {"PORTAFOGLIO": pf.as_dict()}

    rows, pf, per_asset = evaluate(universe, run_sanyaku)
    table(rows + [("PORTAFOGLIO", pf)], "SANYAKU v5.5 — porting fedele, size al fill")
    summary["sanyaku_v55"] = {n: s.as_dict() for n, s in rows} | {"PORTAFOGLIO": pf.as_dict()}

    rows, pf, conf_assets = evaluate(universe, run_confluence)
    table(rows + [("PORTAFOGLIO", pf)], "CONFLUENCE v3.2 — porting fedele, size al fill")
    summary["confluence_v32"] = {n: s.as_dict() for n, s in rows} | {"PORTAFOGLIO": pf.as_dict()}

    rows_sig, pf_sig, _ = evaluate(universe, run_sanyaku, size_at_signal=True)
    table(rows_sig + [("PORTAFOGLIO", pf_sig)], "SANYAKU v5.5 — size al close di segnale (difetto del Pine)")
    summary["sanyaku_v55_size_at_signal"] = {n: s.as_dict() for n, s in rows_sig} | {"PORTAFOGLIO": pf_sig.as_dict()}

    # quali ingressi producono i trade, e con che esito
    print("\nSANYAKU v5.5 — scomposizione per tipo di ingresso")
    print(f"{'tipo':6s} {'trade':>6s} {'win%':>6s} {'avgR':>7s} {'PnL totale':>14s}")
    by_tag: dict[str, list] = {}
    for res in per_asset.values():
        for t in res.trades:
            if not t.is_open:
                by_tag.setdefault(t.tag, []).append(t)
    for tag in sorted(by_tag):
        ts = by_tag[tag]
        wins = sum(1 for t in ts if t.pnl > 0)
        print(f"{tag:6s} {len(ts):6d} {wins/len(ts):5.0%} "
              f"{sum(t.r_multiple for t in ts)/len(ts):7.2f} {sum(t.pnl for t in ts):14,.0f}")

    OUT.mkdir(exist_ok=True)
    (OUT / "comparison.json").write_text(json.dumps(summary, indent=2, default=float))
    print("\nrisultati in results/comparison.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
