#!/usr/bin/env python3
"""Validazione fuori campione del candidato `cloud_exit`.

La domanda è una sola: il vantaggio del candidato sopravvive quando gli si
toglie il privilegio di essere stato scelto guardando gli stessi dati su cui
viene misurato? Quattro prove, dalla più indulgente alla più severa.

1. **Walk-forward a candidato fisso.** Otto finestre di test contigue, il
   candidato e il benchmark sottoposti allo stesso identico protocollo. Misura
   la stabilità nel tempo. Non misura la selezione: con parametri fissi non c'è
   nulla che venga adattato in-sample, e il candidato è stato comunque scelto
   conoscendo tutto il periodo.
2. **Walk-forward con selezione.** Dentro ogni finestra di training viene
   rieseguita l'intera procedura di ricerca — ventitré varianti, si tiene la
   migliore per MAR — e il risultato si misura sulla finestra successiva, mai
   vista. È il test della *procedura*, non del suo vincitore, ed è l'unica delle
   quattro che riproduce onestamente cosa sarebbe successo decidendo in tempo
   reale.
3. **K-fold purgato con embargo.** Cinque blocchi, training purgato dei 200
   giorni che precedono il test (la durata massima osservata di un trade) e in
   embargo per i 40 che lo seguono.
4. **Deflated Sharpe Ratio** su N = 22 ipotesi provate, più un bootstrap a
   blocchi circolari per un intervallo di confidenza sul delta di MAR.

Uso: python3 scripts/run_validation.py [--boot 2000]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine import data, hypotheses as H, validation as V

OUT = pathlib.Path(__file__).resolve().parent.parent / "results"
CAPITAL = V.CAPITAL


def riga(label: str, s, delta: float | None = None, extra: str = "") -> None:
    d = f"{delta:+6.2f}" if delta is not None and np.isfinite(delta) else "      "
    def num(x, fmt):
        return format(x, fmt) if np.isfinite(x) else "     —"
    print(f"{label:26s} {num(s.mar, '6.2f')} {d} {num(s.sharpe, '7.2f')} "
          f"{num(s.cagr, '7.1%')} {num(s.max_dd, '7.1%')} {s.trades:6d}  {extra}")


TESTA = (f"{'':26s} {'MAR':>6s} {'delta':>6s} {'Sharpe':>7s} {'CAGR':>7s} "
         f"{'maxDD':>7s} {'trade':>6s}")


def distribuzione(valori: list[float]) -> dict:
    a = np.array([x for x in valori if np.isfinite(x)], dtype=float)
    if not len(a):
        return {}
    return {"n": int(len(a)), "media": float(a.mean()), "mediana": float(np.median(a)),
            "min": float(a.min()), "max": float(a.max()), "std": float(a.std(ddof=1)) if len(a) > 1 else 0.0,
            "positivi": int((a > 0).sum())}


def stampa_distribuzione(nome: str, d: dict) -> None:
    if not d:
        print(f"  {nome}: nessun valore definito")
        return
    print(f"  {nome:34s} mediana {d['mediana']:+6.2f}  media {d['media']:+6.2f}  "
          f"min {d['min']:+6.2f}  max {d['max']:+6.2f}  positivi {d['positivi']}/{d['n']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=2000, help="ricampionamenti del bootstrap")
    args = ap.parse_args()

    universe = {k: v[v.index >= "2015-08-08"] for k, v in data.load_universe().items()}
    start, end = data.common_period(universe)
    intero = [V.Segment(start, end)]
    base_runner = H.SELECTION_POOL[H.BASE_NAME]
    cand_runner = H.SELECTION_POOL[H.CANDIDATE]

    print(f"periodo: {start.date()} → {end.date()} | {len(universe)} asset | "
          f"un solo set di parametri | costi per asset")
    print(f"candidato: {H.CANDIDATE} | benchmark: {H.BASE_NAME} | "
          f"ipotesi provate finora: {H.N_HYPOTHESES}")

    summary: dict = {"periodo": [str(start.date()), str(end.date())],
                     "ipotesi": H.N_HYPOTHESES, "candidato": H.CANDIDATE}

    # ---------------------------------------------------------------- 0
    print("\n" + "=" * 78)
    print("0) RIFERIMENTO IN-SAMPLE — tutto il periodo, gli stessi dati della selezione")
    print("=" * 78)
    print(TESTA)
    is_base = V.evaluate(universe, base_runner, intero)
    is_cand = V.evaluate(universe, cand_runner, intero)
    riga("benchmark", is_base.stats)
    riga("candidato", is_cand.stats, is_cand.stats.mar - is_base.stats.mar,
         f"{is_cand.assets_better_than(is_base)}/6 asset")
    summary["in_sample"] = {"base": is_base.stats.as_dict(), "candidato": is_cand.stats.as_dict()}

    # ---------------------------------------------------------------- 1
    print("\n" + "=" * 78)
    print("1) WALK-FORWARD A CANDIDATO FISSO — stabilità, non selezione")
    print("=" * 78)
    finestre = V.rolling_windows(start, end, train_years=3, test_years=1, step_years=1)
    print(f"{len(finestre)} finestre di test contigue, training di 3 anni, avanzamento annuale")
    print(f"\n{'finestra':26s} {'MAR base':>9s} {'MAR cand':>9s} {'delta':>7s} "
          f"{'Sh base':>8s} {'Sh cand':>8s} {'asset':>6s}")

    d_mar, d_sharpe, righe_wf = [], [], []
    for w in finestre:
        b = V.evaluate(universe, base_runner, [w.test])
        c = V.evaluate(universe, cand_runner, [w.test])
        dm = c.stats.mar - b.stats.mar
        ds = c.stats.sharpe - b.stats.sharpe
        d_mar.append(dm), d_sharpe.append(ds)
        migliori = c.assets_better_than(b)
        print(f"{w.label:26s} {b.stats.mar:9.2f} {c.stats.mar:9.2f} {dm:+7.2f} "
              f"{b.stats.sharpe:8.2f} {c.stats.sharpe:8.2f} {migliori:4d}/6")
        righe_wf.append({"finestra": w.label, "base": b.stats.as_dict(),
                         "candidato": c.stats.as_dict(), "delta_mar": dm,
                         "delta_sharpe": ds, "asset_migliorati": migliori})

    print("\ndistribuzione del delta sulle finestre:")
    stampa_distribuzione("delta MAR", distribuzione(d_mar))
    stampa_distribuzione("delta Sharpe", distribuzione(d_sharpe))

    test_segs = [w.test for w in finestre]
    agg_base = V.evaluate(universe, base_runner, test_segs)
    agg_cand = V.evaluate(universe, cand_runner, test_segs)
    print(f"\naggregato sulle {len(test_segs)} finestre concatenate "
          f"({test_segs[0].start.date()} → {test_segs[-1].end.date()}):")
    print(TESTA)
    riga("benchmark", agg_base.stats)
    riga("candidato", agg_cand.stats, agg_cand.stats.mar - agg_base.stats.mar,
         f"{agg_cand.assets_better_than(agg_base)}/6 asset")
    summary["walk_forward_fisso"] = {
        "finestre": righe_wf, "delta_mar": distribuzione(d_mar),
        "delta_sharpe": distribuzione(d_sharpe),
        "aggregato": {"base": agg_base.stats.as_dict(), "candidato": agg_cand.stats.as_dict()},
    }

    # ---------------------------------------------------------------- 2
    print("\n" + "=" * 78)
    print("2) WALK-FORWARD CON SELEZIONE — la procedura, non il suo vincitore")
    print("=" * 78)
    print(f"dentro ogni training si rieseguono tutte le {len(H.SELECTION_POOL)} varianti "
          f"({H.N_HYPOTHESES} ipotesi + il benchmark) e si tiene la migliore per MAR")
    print(f"\n{'finestra':26s} {'scelta in-sample':22s} {'MAR IS':>7s} {'MAR OOS':>8s} "
          f"{'base OOS':>9s} {'delta':>7s} {'rho':>6s}")

    d_sel, rho_list, scelte, righe_sel = [], [], [], []
    for w in finestre:
        scelta, is_res = V.select_best(universe, H.SELECTION_POOL, [w.train])
        oos_res = {n: V.evaluate(universe, r, [w.test]) for n, r in H.SELECTION_POOL.items()}
        rho = V.rank_correlation({n: r.stats.mar for n, r in is_res.items()},
                                 {n: r.stats.mar for n, r in oos_res.items()})
        base_oos = oos_res[H.BASE_NAME].stats.mar
        sel_oos = oos_res[scelta].stats.mar
        delta = sel_oos - base_oos
        d_sel.append(delta), rho_list.append(rho), scelte.append(scelta)
        print(f"{w.label:26s} {scelta:22s} {is_res[scelta].stats.mar:7.2f} {sel_oos:8.2f} "
              f"{base_oos:9.2f} {delta:+7.2f} {rho:6.2f}")
        righe_sel.append({"finestra": w.label, "scelta": scelta,
                          "mar_is": is_res[scelta].stats.mar, "mar_oos": sel_oos,
                          "mar_oos_base": base_oos, "delta": delta, "rho_is_oos": rho,
                          "mar_oos_candidato": oos_res[H.CANDIDATE].stats.mar})

    print("\ndistribuzione del delta della procedura di selezione:")
    stampa_distribuzione("delta MAR (scelta − benchmark)", distribuzione(d_sel))
    stampa_distribuzione("rho di rango in-sample vs OOS", distribuzione(rho_list))
    conteggi = pd.Series(scelte).value_counts()
    print("\n  cosa viene scelto, finestra per finestra:")
    for nome, n in conteggi.items():
        print(f"    {nome:24s} {n}/{len(finestre)}")
    print(f"    il candidato '{H.CANDIDATE}' viene scelto "
          f"{scelte.count(H.CANDIDATE)}/{len(finestre)} volte")
    summary["walk_forward_selezione"] = {
        "finestre": righe_sel, "delta_mar": distribuzione(d_sel),
        "rho": distribuzione(rho_list), "scelte": conteggi.to_dict(),
    }

    # ---------------------------------------------------------------- 3
    print("\n" + "=" * 78)
    print("3) K-FOLD PURGATO CON EMBARGO")
    print("=" * 78)
    folds = V.purged_folds(start, end, n_splits=5,
                           purge_days=V.MAX_HOLDING_DAYS, embargo_days=V.EMBARGO_DAYS)
    print(f"{len(folds)} fold | purge {V.MAX_HOLDING_DAYS} giorni (durata massima osservata "
          f"di un trade) | embargo {V.EMBARGO_DAYS} giorni")
    print(f"\n{'fold':30s} {'MAR base':>9s} {'MAR cand':>9s} {'delta':>7s} "
          f"{'scelta sul training':24s} {'MAR OOS':>8s}")

    d_fold, d_fold_sel, diverse, righe_fold = [], [], 0, []
    for f in folds:
        b = V.evaluate(universe, base_runner, [f.test])
        c = V.evaluate(universe, cand_runner, [f.test])
        scelta, _ = V.select_best(universe, H.SELECTION_POOL, list(f.train))
        # stesso fold senza purge né embargo: isola quanto pesa la contaminazione
        sporco = [V.Segment(start, f.test.start), V.Segment(f.test.end, end)]
        sporco = [s for s in sporco if s.days > 365]
        scelta_sporca, _ = V.select_best(universe, H.SELECTION_POOL, sporco)
        diverse += int(scelta != scelta_sporca)
        sel_oos = V.evaluate(universe, H.SELECTION_POOL[scelta], [f.test])
        dm = c.stats.mar - b.stats.mar
        d_fold.append(dm)
        d_fold_sel.append(sel_oos.stats.mar - b.stats.mar)
        print(f"{f.label:30s} {b.stats.mar:9.2f} {c.stats.mar:9.2f} {dm:+7.2f} "
              f"{scelta:24s} {sel_oos.stats.mar:8.2f}")
        righe_fold.append({"fold": f.label, "base": b.stats.as_dict(),
                           "candidato": c.stats.as_dict(), "delta_mar": dm,
                           "scelta_purgata": scelta, "scelta_non_purgata": scelta_sporca,
                           "mar_oos_scelta": sel_oos.stats.mar,
                           "train_anni": f.train_years})

    print("\ndistribuzione sui fold:")
    stampa_distribuzione("delta MAR (candidato − benchmark)", distribuzione(d_fold))
    stampa_distribuzione("delta MAR (scelta − benchmark)", distribuzione(d_fold_sel))
    print(f"\n  fold in cui purge ed embargo cambiano la variante scelta: "
          f"{diverse}/{len(folds)}")
    summary["kfold_purgato"] = {
        "fold": righe_fold, "delta_mar": distribuzione(d_fold),
        "delta_mar_selezione": distribuzione(d_fold_sel),
        "purge_giorni": V.MAX_HOLDING_DAYS, "embargo_giorni": V.EMBARGO_DAYS,
        "scelte_cambiate_dal_purging": diverse,
    }

    # ---------------------------------------------------------------- 4
    print("\n" + "=" * 78)
    print(f"4) DEFLATED SHARPE RATIO — N = {H.N_HYPOTHESES} ipotesi provate")
    print("=" * 78)
    prove = {n: V.evaluate(universe, r, intero) for n, r in H.CATALOGUE.items()}
    sharpe_prove = {n: V.sharpe_per_bar(r.returns) for n, r in prove.items()}
    validi = [x for x in sharpe_prove.values() if np.isfinite(x)]
    indefiniti = [n for n, x in sharpe_prove.items() if not np.isfinite(x)]

    def verdetto(dsr: float) -> str:
        return ("distinguibile" if dsr > 0.95 else "dubbio" if dsr > 0.5 else "NON distinguibile")

    print(f"Sharpe per barra delle {len(sharpe_prove)} ipotesi: min {min(validi):.4f}  "
          f"max {max(validi):.4f}  dev.std {np.std(validi, ddof=1):.4f}")
    if indefiniti:
        print(f"  Sharpe indefinito (nessun trade, quindi varianza nulla): "
              f"{', '.join(indefiniti)} — contati in N, esclusi dalla dispersione")

    print("\n4a) sullo Sharpe assoluto")
    print(f"{'':24s} {'SR/anno':>8s} {'soglia N':>9s} {'PSR':>7s} {'DSR':>7s}  interpretazione")
    dsr_out = {}
    for etichetta, res in [(H.CANDIDATE, is_cand), ("donchian (non scelto)", is_base),
                           ("exit_kijun_cross", prove["exit_kijun_cross"]),
                           ("signal_sanyaku", prove["signal_sanyaku"])]:
        ds = V.deflated_sharpe(res.returns, validi, n_trials=H.N_HYPOTHESES)
        print(f"{etichetta:24s} {ds.sr_annual:8.2f} {ds.sr0_annual:9.2f} "
              f"{ds.psr:7.3f} {ds.dsr:7.3f}  {verdetto(ds.dsr)}")
        dsr_out[etichetta] = ds.as_dict()

    print("\n  Il benchmark, che non è stato scelto da nessuna procedura, passa esattamente")
    print("  come il candidato: undici anni di esposizione a un trend follower bastano a")
    print("  rendere lo Sharpe assoluto significativo, e le ventidue ipotesi sono varianti")
    print("  della stessa esposizione, quindi poco disperse e con una soglia bassa. Il test")
    print("  sullo Sharpe assoluto non risponde alla domanda: non separa il candidato dalla")
    print("  cosa banale che doveva battere.")

    print("\n4b) sul differenziale candidato − benchmark — il test che discrimina")
    diff = {n: V.differential_returns(r.returns, is_base.returns) for n, r in prove.items()}
    sharpe_diff = {n: V.sharpe_per_bar(d) for n, d in diff.items()}
    validi_diff = [x for x in sharpe_diff.values() if np.isfinite(x)]
    print(f"Sharpe per barra dei {len(validi_diff)} differenziali: min {min(validi_diff):+.4f}  "
          f"max {max(validi_diff):+.4f}  dev.std {np.std(validi_diff, ddof=1):.4f}")
    migliore = max(sharpe_diff, key=lambda n: sharpe_diff[n] if np.isfinite(sharpe_diff[n]) else -9)
    print(f"il differenziale più alto delle {H.N_HYPOTHESES} ipotesi è {migliore}")
    print(f"\n{'':24s} {'SR/anno':>8s} {'soglia N':>9s} {'PSR':>7s} {'DSR':>7s}  interpretazione")
    da_mostrare = dict.fromkeys([H.CANDIDATE, migliore, "exit_kijun_cross", "signal_sanyaku"])
    for etichetta in da_mostrare:
        ds = V.deflated_sharpe(diff[etichetta], validi_diff, n_trials=H.N_HYPOTHESES)
        print(f"{etichetta + ' − base':24s} {ds.sr_annual:8.2f} {ds.sr0_annual:9.2f} "
              f"{ds.psr:7.3f} {ds.dsr:7.3f}  {verdetto(ds.dsr)}")
        dsr_out[f"{etichetta} - base"] = ds.as_dict()

    print("\n  PSR = P(Sharpe vero > 0), ignora quante cose sono state provate.")
    print("  DSR = P(Sharpe vero > soglia), dove la soglia è lo Sharpe atteso dal migliore")
    print(f"        di {H.N_HYPOTHESES} strategie senza alcun vantaggio.")
    summary["deflated_sharpe"] = {"sharpe_prove": sharpe_prove, "sharpe_differenziali": sharpe_diff,
                                  "risultati": dsr_out}

    # ---------------------------------------------------------------- 5
    print("\n" + "=" * 78)
    print("5) BOOTSTRAP A BLOCCHI CIRCOLARI — intervallo sul delta di MAR")
    print("=" * 78)
    print(f"{args.boot} ricampionamenti appaiati, blocchi di lunghezza fissa\n")
    print(f"{'serie':30s} {'blocco':>7s} {'delta medio':>12s} {'IC 95%':>22s} {'P(delta<=0)':>12s}")
    boot_out = {}
    for etichetta, cand_r, base_r in [
        ("intero periodo (in-sample)", is_cand.returns, is_base.returns),
        ("finestre di test concatenate", agg_cand.returns, agg_base.returns),
    ]:
        for blocco in (21, 63):
            ci = V.block_bootstrap_delta(cand_r, base_r, block_bars=blocco,
                                         n_boot=args.boot, seed=20260915)
            print(f"{etichetta:30s} {blocco:7d} {ci.mean:12.2f} "
                  f"{f'[{ci.lo:+.2f}, {ci.hi:+.2f}]':>22s} {ci.p_negative:12.1%}")
            boot_out[f"{etichetta} | blocco {blocco}"] = ci.as_dict()
    summary["bootstrap"] = boot_out

    OUT.mkdir(exist_ok=True)
    (OUT / "validation.json").write_text(json.dumps(summary, indent=2, default=float))
    print("\nrisultati in results/validation.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
