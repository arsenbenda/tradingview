#!/usr/bin/env python3
"""Esecuzione del test pre-registrato in results/prereg_peak_avwap.md.

Una sola ipotesi, dichiarata prima: il Peak-AVWAP ancorato all'estremo
precedente aggiunge qualcosa al benchmark come gate sugli ingressi?

Oltre alle metriche riporta il **tasso di blocco**, cioè quante barre di
ingresso il gate ferma davvero. È la misura che distingue un filtro da una
tautologia: il Chikou bloccava 0 ingressi su 1.728 e per questo non era un
filtro, era un teorema.

Uso: python3 scripts/run_prereg_avwap.py
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
START = "2015-08-08"
OUT = pathlib.Path(__file__).resolve().parent.parent / "results"

# le due condizioni fissate nella pre-registrazione
MIN_ASSETS_IMPROVED = 4


def run(df: pd.DataFrame, asset: str, gate=None) -> backtest.Result:
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
        costs=cost_table.for_asset(asset), risk_pct=0.01, initial_capital=CAPITAL,
    )


def portfolio(results: dict[str, backtest.Result]) -> metrics.Stats:
    return metrics.compute(
        backtest.Result(
            equity=metrics.portfolio_equity(results, CAPITAL),
            trades=[t for r in results.values() for t in r.trades],
            exposure=sum(r.exposure for r in results.values()) / len(results),
        ),
        CAPITAL,
    )


def blocking(universe: dict[str, pd.DataFrame]) -> dict:
    """Quante barre di ingresso il gate blocca, per lato e in totale.

    Riporta anche quanto il gate è aperto su **tutte** le barre, non solo su
    quelle di ingresso. È il confronto che distingue due diagnosi opposte:

    * aperto quasi sempre *ovunque* → la condizione è vacua, codificata male;
    * aperto su una minoranza delle barre ma quasi sempre **sulle rotture** →
      la condizione è selettiva, ma è **implicata** dal segnale di ingresso.

    Solo la seconda è una tautologia condizionale, ed è quella che rende il
    componente non testabile come gate su un breakout.
    """
    rows, tot = {}, {"long_sig": 0, "long_blocked": 0, "short_sig": 0, "short_blocked": 0,
                     "bars": 0, "long_open_bars": 0}
    for asset, df in universe.items():
        sig = donchian.signals(df, allow_short=True)
        allow_long, allow_short = filters.peak_avwap(df)
        row = {"bars": len(df),
               "long_open_all_bars": float(allow_long.mean())}
        tot["bars"] += len(df)
        tot["long_open_bars"] += int(allow_long.sum())
        for side, s, allow in (("long", sig["entry_long"], allow_long),
                               ("short", sig["entry_short"], allow_short)):
            s = s.fillna(False)
            n = int(s.sum())
            blocked = int((s & ~allow.reindex(df.index).fillna(False)).sum())
            row[f"{side}_sig"], row[f"{side}_blocked"] = n, blocked
            row[f"{side}_pct"] = blocked / n if n else float("nan")
            tot[f"{side}_sig"] += n
            tot[f"{side}_blocked"] += blocked
        rows[asset] = row
    for side in ("long", "short"):
        tot[f"{side}_pct"] = (tot[f"{side}_blocked"] / tot[f"{side}_sig"]
                              if tot[f"{side}_sig"] else float("nan"))
    tot["long_open_all_bars"] = tot["long_open_bars"] / tot["bars"] if tot["bars"] else float("nan")
    tot["long_open_on_entries"] = (1.0 - tot["long_pct"]) if tot["long_sig"] else float("nan")
    tot["all_sig"] = tot["long_sig"] + tot["short_sig"]
    tot["all_blocked"] = tot["long_blocked"] + tot["short_blocked"]
    tot["all_pct"] = tot["all_blocked"] / tot["all_sig"] if tot["all_sig"] else float("nan")
    return {"per_asset": rows, "total": tot}


def main() -> int:
    universe = {k: v[v.index >= START] for k, v in data.load_universe().items()}
    start, end = data.common_period(universe)
    print(f"periodo: {start.date()} -> {end.date()} | base: Donchian 55/20 long-short")
    print("ipotesi pre-registrata: results/prereg_peak_avwap.md\n")

    base = {a: run(df, a) for a, df in universe.items()}
    gated = {a: run(df, a, filters.peak_avwap) for a, df in universe.items()}

    pf_base, pf_gate = portfolio(base), portfolio(gated)
    s_base = {a: metrics.compute(r, CAPITAL) for a, r in base.items()}
    s_gate = {a: metrics.compute(r, CAPITAL) for a, r in gated.items()}

    print(f"{'':10s} {'MAR':>6s} {'Sharpe':>7s} {'CAGR':>7s} {'maxDD':>7s} {'trade':>6s}")
    for label, pf in (("base", pf_base), ("peak_avwap", pf_gate)):
        print(f"{label:10s} {pf.mar:6.2f} {pf.sharpe:7.2f} {pf.cagr:6.1%} "
              f"{pf.max_dd:6.1%} {pf.trades:6d}")
    delta = pf_gate.mar - pf_base.mar
    print(f"\ndelta MAR di portafoglio: {delta:+.2f}")

    print(f"\n{'asset':8s} {'MAR base':>9s} {'MAR gate':>9s} {'delta':>7s}  {'meglio':>6s}")
    improved = 0
    for a in universe:
        b, g = s_base[a].mar, s_gate[a].mar
        ok = pd.notna(b) and pd.notna(g) and g > b
        improved += bool(ok)
        print(f"{a:8s} {b:9.2f} {g:9.2f} {g - b:+7.2f}  {'si' if ok else 'no':>6s}")
    print(f"\nmigliora {improved}/{len(universe)} asset")

    blk = blocking(universe)
    t = blk["total"]
    print(f"\ntasso di blocco — long {t['long_blocked']}/{t['long_sig']} "
          f"({t['long_pct']:.1%}) | short {t['short_blocked']}/{t['short_sig']} "
          f"({t['short_pct']:.1%}) | totale {t['all_blocked']}/{t['all_sig']} "
          f"({t['all_pct']:.1%})")

    print(f"\ngate long aperto su tutte le barre: {t['long_open_all_bars']:.1%}"
          f"  ->  sulle sole barre di rottura: {t['long_open_on_entries']:.1%}")
    print("   selettivo in generale, implicato dal breakout: tautologia condizionale")

    aggiunge = delta > 0 and improved >= MIN_ASSETS_IMPROVED
    print(f"\nVERDETTO: {'aggiunge valore' if aggiunge else 'NON aggiunge valore'} "
          f"(serviva delta > 0 e almeno {MIN_ASSETS_IMPROVED}/6 asset)")

    OUT.mkdir(exist_ok=True)
    (OUT / "prereg_peak_avwap.json").write_text(json.dumps({
        "period": {"start": str(start.date()), "end": str(end.date())},
        "base": pf_base.as_dict(), "peak_avwap": pf_gate.as_dict(),
        "delta_mar": delta, "assets_improved": improved,
        "per_asset": {a: {"base": s_base[a].as_dict(), "gated": s_gate[a].as_dict()}
                      for a in universe},
        "blocking": blk,
        "verdict": "adds_value" if aggiunge else "no_value",
    }, indent=2, default=float))
    print("\nrisultati in results/prereg_peak_avwap.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
