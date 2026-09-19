#!/usr/bin/env python3
"""Ablazione: ogni componente innestato sul benchmark, uno alla volta.

La domanda non è "questo sistema funziona?" ma "questo **componente** aggiunge
qualcosa a un trend follower che già funziona?". Base identica per tutti
(Donchian 55/20 long-short, parametri Turtle), un filtro alla volta, stesso
periodo e stessi costi. L'unica cosa che cambia è il gate sugli ingressi.

Due salvaguardie contro l'autoinganno:

* si riporta **su quanti asset su sei** il MAR migliora. Un filtro che aiuta solo
  BTC è un filtro adattato a BTC, non un filtro;
* si riporta il **numero di ipotesi testate**. Con sedici filtri, il migliore
  per caso migliora comunque qualcosa: senza questo conteggio il risultato non è
  interpretabile.

Uso: python3 scripts/run_ablation.py
"""

from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine import backtest, costs as cost_table, data, filters, metrics
from engine.strategies import donchian

CAPITAL = 100_000.0
OUT = pathlib.Path(__file__).resolve().parent.parent / "results"


def run_with_filter(df: pd.DataFrame, name: str, gate=None):
    sig = donchian.signals(df, allow_short=True)
    e_long, e_short = sig["entry_long"], sig["entry_short"]
    if gate is not None:
        allow_long, allow_short = gate(df)
        e_long = e_long & allow_long.reindex(df.index).fillna(False)
        e_short = e_short & allow_short.reindex(df.index).fillna(False)
    return backtest.run(
        df, entry_long=e_long, exit_long=sig["exit_long"],
        entry_short=e_short, exit_short=sig["exit_short"],
        stop_distance=sig["stop_distance"],
        costs=cost_table.for_asset(name), risk_pct=0.01, initial_capital=CAPITAL,
    )


def evaluate(universe, gate=None):
    results = {n: run_with_filter(df, n, gate) for n, df in universe.items()}
    per_asset = {n: metrics.compute(r, CAPITAL) for n, r in results.items()}
    pf_eq = metrics.portfolio_equity(results, CAPITAL)
    pf = metrics.compute(
        backtest.Result(equity=pf_eq,
                        trades=[t for r in results.values() for t in r.trades],
                        exposure=sum(r.exposure for r in results.values()) / len(results)),
        CAPITAL,
    )
    return pf, per_asset


def main() -> int:
    universe = {k: v[v.index >= data.DEFAULT_START] for k, v in data.load_universe().items()}
    start, end = data.common_period(universe)
    print(f"periodo: {start.date()} -> {end.date()} | base: Donchian 55/20 long-short")

    base_pf, base_assets = evaluate(universe)
    print(f"\nBASE senza filtri: MAR {base_pf.mar:.2f} | Sharpe {base_pf.sharpe:.2f} | "
          f"CAGR {base_pf.cagr:.1%} | maxDD {base_pf.max_dd:.1%} | {base_pf.trades} trade")

    print(f"\n{'filtro':18s} {'MAR':>6s} {'delta':>7s} {'Sharpe':>7s} {'CAGR':>7s} "
          f"{'maxDD':>7s} {'trade':>6s} {'asset meglio':>13s}")
    print(f"{'(base)':18s} {base_pf.mar:6.2f} {'':>7s} {base_pf.sharpe:7.2f} "
          f"{base_pf.cagr:6.1%} {base_pf.max_dd:6.1%} {base_pf.trades:6d} {'':>13s}")

    rows = []
    for fname, fn in filters.CATALOGUE.items():
        pf, per_asset = evaluate(universe, fn)
        better = sum(1 for a, s in per_asset.items()
                     if pd.notna(s.mar) and pd.notna(base_assets[a].mar) and s.mar > base_assets[a].mar)
        delta = pf.mar - base_pf.mar
        rows.append((fname, pf, delta, better))
        print(f"{fname:18s} {pf.mar:6.2f} {delta:+7.2f} {pf.sharpe:7.2f} {pf.cagr:6.1%} "
              f"{pf.max_dd:6.1%} {pf.trades:6d} {better:>9d}/6")

    rows.sort(key=lambda r: -r[2])
    print(f"\nipotesi testate: {len(rows)}")
    print("migliori tre per delta di MAR:")
    for fname, pf, delta, better in rows[:3]:
        print(f"  {fname:18s} delta {delta:+.2f}  migliora {better}/6 asset  ({pf.trades} trade)")

    OUT.mkdir(exist_ok=True)
    (OUT / "ablation.json").write_text(json.dumps(
        {"base": base_pf.as_dict(),
         "filters": {f: {"stats": p.as_dict(), "delta_mar": d, "assets_improved": b}
                     for f, p, d, b in rows},
         "hypotheses_tested": len(rows)},
        indent=2, default=float))
    print("\nrisultati in results/ablation.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
