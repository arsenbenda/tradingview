#!/usr/bin/env python3
"""Il rischio per trade ottimale, scelto fuori campione invece che in-sample.

`results/universe_extended.md` misura che il MAR **non** e' invariante rispetto
al rischio per trade: sale fino a un massimo intorno al 4-8% e poi ridiscende.
Quel massimo pero' e' letto sulla curva calcolata su tutto il periodo, cioe' e'
scelto con il senno di poi. La regola 7 del progetto dice che un vantaggio
in-sample non e' un risultato: va validata la **procedura** che lo sceglie.

Questo runner applica al rischio esattamente il protocollo che
`run_validation.py` applica alle ventidue ipotesi:

1. **Riferimento in-sample** — la curva su tutto il periodo, per avere il numero
   che si vuole falsificare.
2. **Walk-forward con selezione** — dentro ogni finestra di training si sceglie
   il rischio con il MAR migliore, e lo si misura sulla finestra di test
   successiva, mai vista. E' il test vero.
3. **K-fold purgato con embargo** — stessa selezione, partizione diversa.
4. **Stabilita' della scelta** — quante volte vince quale rischio, e quanto la
   classifica in-sample predice quella fuori campione.

Il confronto non e' "il rischio scelto batte zero", che sarebbe banale: e' **il
rischio scelto contro il rischio fisso all'1%**, cioe' contro il non scegliere.

Uso: python3 scripts/run_risk_walkforward.py [--universe core|extended|no-crypto]
                                             [--short]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine import backtest, costs as cost_table, data, validation as V
from engine.strategies import donchian

OUT = pathlib.Path(__file__).resolve().parent.parent / "results"
CAPITAL = V.CAPITAL

#: la griglia dei rischi provati, in percentuale del capitale per trade.
#:
#: Dichiarata qui e non cercata: e' una griglia logaritmica che copre due ordini
#: di grandezza intorno all'1% pubblicato, e si ferma al 32% perche' oltre il 16%
#: il motore satura sul capitale disponibile (nessun margine) e i punti oltre
#: sarebbero copie dello stesso.
GRIGLIA = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0)

#: il rischio con cui e' stato misurato tutto il progetto, e il termine di
#: paragone di ogni confronto qui dentro: e' la scelta "non scegliere".
RIFERIMENTO = 1.0


def runner_per_rischio(risk_pct: float, allow_short: bool):
    def run(asset: str, df: pd.DataFrame, cost_mult: float = 1.0) -> backtest.Result:
        sig = donchian.signals(df, allow_short=allow_short)
        return backtest.run(
            df, entry_long=sig["entry_long"], exit_long=sig["exit_long"],
            entry_short=sig["entry_short"], exit_short=sig["exit_short"],
            stop_distance=sig["stop_distance"],
            costs=cost_table.for_asset(asset, cost_mult),
            risk_pct=risk_pct / 100.0, initial_capital=CAPITAL,
        )
    return run


def nome(r: float) -> str:
    return f"rischio {r:g}%"


def distribuzione(valori) -> dict:
    a = np.array([x for x in valori if np.isfinite(x)], dtype=float)
    if not len(a):
        return {}
    return {"n": int(len(a)), "media": float(a.mean()), "mediana": float(np.median(a)),
            "min": float(a.min()), "max": float(a.max()),
            "std": float(a.std(ddof=1)) if len(a) > 1 else 0.0,
            "positivi": int((a > 0).sum())}


def stampa_distribuzione(etichetta: str, d: dict) -> None:
    if not d:
        print(f"  {etichetta}: nessun valore definito")
        return
    print(f"  {etichetta}: media {d['media']:+.2f}, mediana {d['mediana']:+.2f}, "
          f"min {d['min']:+.2f}, max {d['max']:+.2f}, "
          f"sd {d['std']:.2f}, positivi {d['positivi']}/{d['n']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", choices=("core", "extended", "no-crypto"), default="core")
    ap.add_argument("--short", action="store_true",
                    help="benchmark long/short (default: solo long, la direzione in cui "
                         "la curva del rischio e' stata misurata)")
    args = ap.parse_args()

    nomi = {"core": data.CORE, "extended": data.EXTENDED,
            "no-crypto": data.NO_CRYPTO}[args.universe]
    universe = data.load_universe(nomi)
    universe = {k: v[v.index >= data.DEFAULT_START] for k, v in universe.items()}
    start, end = data.common_period(universe)
    n_asset = len(universe)

    pool = {nome(r): runner_per_rischio(r, args.short) for r in GRIGLIA}
    base = nome(RIFERIMENTO)

    print(f"universo: {', '.join(universe)}")
    print(f"periodo: {start.date()} -> {end.date()}")
    print(f"direzione: {'long/short' if args.short else 'solo long'}")
    print(f"griglia: {', '.join(f'{r:g}%' for r in GRIGLIA)} — "
          f"riferimento {RIFERIMENTO:g}% (non scegliere)")

    summary = {"universo": args.universe, "asset": list(universe),
               "allow_short": args.short, "griglia": list(GRIGLIA),
               "riferimento": RIFERIMENTO}

    # ---------------------------------------------------------------- 0
    print("\n" + "=" * 78)
    print("0) RIFERIMENTO IN-SAMPLE — la curva su tutto il periodo")
    print("=" * 78)
    intero = [V.Segment(start, end)]
    is_res = {n: V.evaluate(universe, r, intero) for n, r in pool.items()}
    print(f"{'rischio':14s} {'MAR':>6s} {'Sharpe':>7s} {'CAGR':>8s} {'maxDD':>7s}")
    for r in GRIGLIA:
        s = is_res[nome(r)].stats
        print(f"{nome(r):14s} {s.mar:6.2f} {s.sharpe:7.2f} {s.cagr:8.1%} {s.max_dd:7.1%}")
    is_best = max(is_res, key=lambda n: is_res[n].stats.mar)
    print(f"\nmassimo in-sample: {is_best} (MAR {is_res[is_best].stats.mar:.2f}) "
          f"contro {base} (MAR {is_res[base].stats.mar:.2f})")
    summary["in_sample"] = {n: r.stats.as_dict() for n, r in is_res.items()}
    summary["in_sample_migliore"] = is_best

    # ---------------------------------------------------------------- 1
    print("\n" + "=" * 78)
    print("1) WALK-FORWARD CON SELEZIONE — si sceglie sul training, si misura sul test")
    print("=" * 78)
    finestre = V.rolling_windows(start, end, train_years=3, test_years=1, step_years=1)
    print(f"{len(finestre)} finestre di test contigue, training di 3 anni, avanzamento annuale")
    print(f"\n{'finestra':26s} {'scelta':14s} {'MAR IS':>7s} {'MAR OOS':>8s} "
          f"{'OOS a 1%':>9s} {'delta':>7s} {'rho':>6s}")

    deltas, rho_list, scelte, righe = [], [], [], []
    for w in finestre:
        scelta, tr = V.select_best(universe, pool, [w.train])
        oos = {n: V.evaluate(universe, r, [w.test]) for n, r in pool.items()}
        rho = V.rank_correlation({n: r.stats.mar for n, r in tr.items()},
                                 {n: r.stats.mar for n, r in oos.items()})
        oos_sel = oos[scelta].stats.mar
        oos_base = oos[base].stats.mar
        d = oos_sel - oos_base
        deltas.append(d), rho_list.append(rho), scelte.append(scelta)
        print(f"{w.label:26s} {scelta:14s} {tr[scelta].stats.mar:7.2f} {oos_sel:8.2f} "
              f"{oos_base:9.2f} {d:+7.2f} {rho:6.2f}")
        righe.append({"finestra": w.label, "scelta": scelta,
                      "mar_is": tr[scelta].stats.mar, "mar_oos": oos_sel,
                      "mar_oos_riferimento": oos_base, "delta": d, "rho_is_oos": rho})

    print("\ndistribuzione della procedura di selezione del rischio:")
    stampa_distribuzione("delta MAR (scelto − 1% fisso)", distribuzione(deltas))
    stampa_distribuzione("rho di rango in-sample vs OOS", distribuzione(rho_list))
    conteggi = pd.Series(scelte).value_counts()
    print("\n  cosa viene scelto, finestra per finestra:")
    for n, k in conteggi.items():
        print(f"    {n:14s} {k}/{len(finestre)}")

    test_segs = [w.test for w in finestre]
    agg = {n: V.evaluate(universe, r, test_segs) for n, r in pool.items()}
    print(f"\naggregato sulle {len(test_segs)} finestre di test concatenate:")
    print(f"{'rischio':14s} {'MAR':>6s} {'Sharpe':>7s} {'CAGR':>8s} {'maxDD':>7s}")
    for r in GRIGLIA:
        s = agg[nome(r)].stats
        print(f"{nome(r):14s} {s.mar:6.2f} {s.sharpe:7.2f} {s.cagr:8.1%} {s.max_dd:7.1%}")
    oos_best = max(agg, key=lambda n: agg[n].stats.mar)
    print(f"\nmassimo fuori campione: {oos_best} (MAR {agg[oos_best].stats.mar:.2f})")
    summary["walk_forward"] = {
        "finestre": righe, "delta_mar": distribuzione(deltas),
        "rho": distribuzione(rho_list), "scelte": conteggi.to_dict(),
        "aggregato": {n: r.stats.as_dict() for n, r in agg.items()},
        "aggregato_migliore": oos_best,
    }

    # ---------------------------------------------------------------- 2
    print("\n" + "=" * 78)
    print("2) K-FOLD PURGATO CON EMBARGO — stessa selezione, partizione diversa")
    print("=" * 78)
    folds = V.purged_folds(start, end, n_splits=5)
    print(f"{len(folds)} fold, purge {V.MAX_HOLDING_DAYS} giorni, embargo {V.EMBARGO_DAYS}")
    print(f"\n{'fold':26s} {'scelta':14s} {'MAR IS':>7s} {'MAR OOS':>8s} "
          f"{'OOS a 1%':>9s} {'delta':>7s}")

    d_fold, scelte_fold, righe_fold = [], [], []
    for f in folds:
        scelta, tr = V.select_best(universe, pool, f.train)
        oos = {n: V.evaluate(universe, r, [f.test]) for n, r in pool.items()}
        oos_sel, oos_base = oos[scelta].stats.mar, oos[base].stats.mar
        d = oos_sel - oos_base
        d_fold.append(d), scelte_fold.append(scelta)
        print(f"{f.label:26s} {scelta:14s} {tr[scelta].stats.mar:7.2f} {oos_sel:8.2f} "
              f"{oos_base:9.2f} {d:+7.2f}")
        righe_fold.append({"fold": f.label, "scelta": scelta, "mar_is": tr[scelta].stats.mar,
                           "mar_oos": oos_sel, "mar_oos_riferimento": oos_base, "delta": d})

    print("\ndistribuzione sui fold:")
    stampa_distribuzione("delta MAR (scelto − 1% fisso)", distribuzione(d_fold))
    conteggi_fold = pd.Series(scelte_fold).value_counts()
    print("\n  cosa viene scelto:")
    for n, k in conteggi_fold.items():
        print(f"    {n:14s} {k}/{len(folds)}")
    summary["k_fold"] = {"fold": righe_fold, "delta_mar": distribuzione(d_fold),
                         "scelte": conteggi_fold.to_dict()}

    # ---------------------------------------------------------------- verdetto
    print("\n" + "=" * 78)
    print("VERDETTO")
    print("=" * 78)
    dm, dk = distribuzione(deltas), distribuzione(d_fold)
    print(f"  massimo in-sample                       {is_best} "
          f"(MAR {is_res[is_best].stats.mar:.2f} contro {is_res[base].stats.mar:.2f} a 1%)")
    if dm:
        print(f"  delta della procedura, walk-forward     {dm['media']:+.2f} di MAR medio, "
              f"positivo in {dm['positivi']}/{dm['n']} finestre")
    if dk:
        print(f"  delta della procedura, k-fold purgato   {dk['media']:+.2f} di MAR medio, "
              f"positivo in {dk['positivi']}/{dk['n']} fold")
    rr = distribuzione(rho_list)
    if rr:
        print(f"  rho di rango fra IS e OOS               {rr['media']:+.2f} medio "
              f"(1.00 = la classifica in-sample predice perfettamente)")
    print(f"  massimo fuori campione, aggregato       {oos_best}")

    OUT.mkdir(exist_ok=True)
    suff = "" if args.universe == "core" else f"_{args.universe}"
    suff += "_ls" if args.short else ""
    path = OUT / f"risk_walkforward{suff}.json"
    path.write_text(json.dumps(summary, indent=2, default=float))
    print(f"\nrisultati salvati in results/{path.name}")
    print(f"(n_asset = {n_asset}; ogni MAR di finestra e' calcolato su un anno solo, "
          f"quindi e' una statistica rumorosa: contano le distribuzioni, non le righe)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
