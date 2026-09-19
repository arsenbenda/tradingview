#!/usr/bin/env python3
"""Esecuzione del test pre-registrato in results/prereg_livelli_sr.md.

I livelli agiscono da supporto e resistenza? Primario dichiarato: la **nuvola**,
perché è il solo livello fissato 26 barre prima che il prezzo ci arrivi e il solo
raro e lontano. Tenkan, Kijun e i sette ottavi di Gann sono secondari
esplorativi e non possono sostenere nessuna affermazione: riportare la migliore
di dieci è il massimo-di-N che ha ucciso `cloud_exit`.

Ogni livello è confrontato con **sé stesso spostato** di 0.5-1.5 ATR, cinque
volte. È l'unico controllo che isoli la posizione del livello da tutto il resto.

Uso: python3 scripts/run_prereg_levels.py
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine import data, indicators as ind, levels as L

START = "2015-08-08"
SEED = 20260919          # dichiarato, non pescato
MIN_ASSET_CONCORDI = 4   # condizione 3 della pre-registrazione
OUT = pathlib.Path(__file__).resolve().parent.parent / "results"

PRIMARIO = ("cloud_top", "cloud_bot")
SECONDARI = ("tenkan", "kijun") + tuple(f"gann_{n}_8" for n in range(1, 8))


def per_asset(df: pd.DataFrame, seed: int) -> dict[str, dict]:
    """Esiti reali e placebo, per famiglia, su un asset."""
    atr = ind.atr(df, L.ATR_LEN)
    fam = L.level_families(df, L.PIVOT_K)
    fuori = {}
    for i, (nome, lv) in enumerate(fam.items()):
        _, esiti = L.measure(df, lv, atr)
        plac = []
        for p in L.placebo_levels(lv, atr, n=L.N_PLACEBO, seed=seed + 1000 * i):
            _, e = L.measure(df, p, atr)
            plac.append(e)
        fuori[nome] = {"reale": esiti,
                       "placebo": np.concatenate(plac) if plac else np.empty(0, int)}
    return fuori


def pool(per: dict[str, dict[str, dict]], famiglie) -> tuple[np.ndarray, np.ndarray]:
    r = [per[a][f]["reale"] for a in per for f in famiglie]
    p = [per[a][f]["placebo"] for a in per for f in famiglie]
    return np.concatenate(r), np.concatenate(p)


def quota(esiti: np.ndarray) -> tuple[int, float]:
    d = esiti[esiti != L.CENSORED]
    return len(d), (float((d == L.REJECT).mean()) if len(d) else float("nan"))


def riga(nome: str, r: np.ndarray, p: np.ndarray, seed: int) -> dict:
    nr, pr = quota(r)
    np_, pp = quota(p)
    bs = L.bootstrap_delta(r, p, seed=seed)
    return {"famiglia": nome, "n_reale": nr, "p_reale": pr,
            "n_placebo": np_, "p_placebo": pp, **bs}


def stampa(rows: list[dict]) -> None:
    print(f"{'famiglia':12s} {'n reale':>8s} {'P(rif)':>7s} {'n plac':>8s} "
          f"{'P(rif)':>7s} {'delta':>7s} {'IC 95%':>18s} {'P(d<=0)':>8s}")
    for x in rows:
        print(f"{x['famiglia']:12s} {x['n_reale']:8d} {x['p_reale']:7.3f} "
              f"{x['n_placebo']:8d} {x['p_placebo']:7.3f} {x['delta']:+7.3f} "
              f"[{x['lo']:+.3f}, {x['hi']:+.3f}] {x['p_negative']:8.1%}")


def main() -> int:
    universe = {k: v[v.index >= START] for k, v in data.load_universe().items()}
    start, end = data.common_period(universe)
    print(f"periodo: {start.date()} -> {end.date()} | sei asset")
    print(f"pre-registrazione: results/prereg_livelli_sr.md | seed {SEED}")
    print(f"corsa: barriere a {L.BARRIER_ATR} ATR({L.ATR_LEN}), orizzonte "
          f"{L.HORIZON} barre, pausa {L.MIN_GAP} | placebo {L.N_PLACEBO}x "
          f"({L.SHIFT_MIN}-{L.SHIFT_MAX} ATR)\n")

    per = {a: per_asset(df, SEED) for a, df in universe.items()}

    # ---------------- primario ----------------
    r, p = pool(per, PRIMARIO)
    prim = riga("cloud", r, p, SEED)
    print("PRIMARIO — la nuvola (cloud_top + cloud_bot)")
    stampa([prim])

    print("\n  per bordo, descrittivo:")
    stampa([riga(f, *pool(per, (f,)), SEED) for f in PRIMARIO])

    # condizione 3: concordanza fra asset
    per_a = {}
    for a in per:
        rr = np.concatenate([per[a][f]["reale"] for f in PRIMARIO])
        pp = np.concatenate([per[a][f]["placebo"] for f in PRIMARIO])
        per_a[a] = riga(a, rr, pp, SEED)
    print("\n  per asset (regola 5: un effetto su un asset e' di quell'asset):")
    stampa(list(per_a.values()))
    concordi = sum(1 for x in per_a.values() if np.isfinite(x["delta"]) and x["delta"] > 0)
    print(f"\n  delta positivo su {concordi}/{len(per_a)} asset")

    passa = (prim["delta"] > 0 and prim["lo"] > 0 and concordi >= MIN_ASSET_CONCORDI)
    print(f"\nVERDETTO PRIMARIO: {'la nuvola AGISCE da S/R' if passa else 'NON agisce da S/R in modo distinguibile'}")
    print(f"  servivano: delta > 0 ({prim['delta']:+.3f}), IC che esclude lo zero "
          f"(lo = {prim['lo']:+.3f}), >= {MIN_ASSET_CONCORDI}/6 asset ({concordi})")

    # ---------------- concentrazione, regola 8 ----------------
    print("\nCONCENTRAZIONE (regola 8, obbligatoria su ogni esito)")
    ordinati = sorted(per_a.items(), key=lambda kv: -(kv[1]["delta"] if np.isfinite(kv[1]["delta"]) else -9))
    peggio = ordinati[0][0]
    rr = np.concatenate([per[a][f]["reale"] for a in per if a != peggio for f in PRIMARIO])
    pp = np.concatenate([per[a][f]["placebo"] for a in per if a != peggio for f in PRIMARIO])
    senza = riga(f"senza {peggio}", rr, pp, SEED)
    print(f"  primo contribuente: {peggio} (delta {ordinati[0][1]['delta']:+.3f})")
    stampa([senza])

    # ---------------- secondari ----------------
    print(f"\nSECONDARI — esplorativi, molteplicita' {len(SECONDARI)} dichiarata.")
    print("Nessuno di questi puo' sostenere un'affermazione: la migliore di dieci")
    print("e' il massimo-di-N, ed e' l'errore che questo progetto esiste per evitare.\n")
    sec = [riga(f, *pool(per, (f,)), SEED) for f in SECONDARI]
    stampa(sec)

    OUT.mkdir(exist_ok=True)
    (OUT / "prereg_livelli_sr.json").write_text(json.dumps({
        "period": {"start": str(start.date()), "end": str(end.date())},
        "seed": SEED,
        "parametri": {"pivot_k": L.PIVOT_K, "min_gap": L.MIN_GAP,
                      "barrier_atr": L.BARRIER_ATR, "horizon": L.HORIZON,
                      "n_placebo": L.N_PLACEBO,
                      "shift": [L.SHIFT_MIN, L.SHIFT_MAX]},
        "primario": prim, "per_bordo": [riga(f, *pool(per, (f,)), SEED) for f in PRIMARIO],
        "per_asset": per_a, "asset_concordi": concordi,
        "senza_primo_contribuente": senza,
        "secondari": sec,
        "verdetto": "agisce" if passa else "non_distinguibile",
    }, indent=2, default=float))
    print("\nrisultati in results/prereg_livelli_sr.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
