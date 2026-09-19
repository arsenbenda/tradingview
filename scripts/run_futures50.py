#!/usr/bin/env python3
"""Donchian 55/20 su futures, mezzo secolo. Vedi results/preregistrazione_futures.md.

Un solo run, parametri dichiarati prima, universo congelato. Le serie sono
close-only e back-adjusted per differenza: l'aggiustamento e' ancorato alla fine
(GOLD chiude a 2254 contro i ~2200 reali del marzo 2024), quindi i livelli
recenti sono veri e l'errore cresce andando indietro.

ESITO: fallito, e per un errore di specifica mio. Il costo dichiarato
(costs.DEFAULT, 0.30% round-trip) e' tarato su crypto ed ETF; per un future
liquido il round-trip vero sta fra 0.01% e 0.03%. Con ~8 trade per mercato
all'anno quel costo vale 2.4% annuo di attrito contro un rendimento lordo del
2%: il test misurava la mia assunzione, non il mercato. Vedi
results/futures_50y.md.
"""
from __future__ import annotations
import json, pathlib, sys
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from engine import backtest, costs as ct, metrics
from engine.strategies import donchian

RADICE = pathlib.Path(__file__).resolve().parent.parent
DATI = RADICE / "data" / "futures_daily"
CAP = 100_000.0

def carica() -> dict[str, pd.DataFrame]:
    """I mercati dell'universo congelato, meno quelli con un difetto dei dati.

    L'esclusione e' quella prevista dalla pre-registrazione: le serie
    back-adjusted per differenza attraversano lo zero su 19 mercati (fino al 76%
    delle barre su SOYMEAL). Un prezzo negativo rende privi di senso i costi in
    percentuale, il sizing e i rendimenti: non e' un dato sporco da pulire, e'
    una proprieta' del metodo di aggiustamento. Restano i mercati che non ci
    passano mai.
    """
    fuori, dentro = [], {}
    for m in open(RADICE / "data" / "futures_universe.txt").read().split():
        d = pd.read_csv(DATI / f"{m}.csv.gz")
        d["date"] = pd.to_datetime(d["date"]); d = d.set_index("date")
        if (d["close"] <= 0).any() or (d["close"].pct_change().abs() > 0.5).any():
            fuori.append(m); continue
        dentro[m] = d
    return dentro, fuori

def porta(uni, mult):
    res = {}
    for n, df in uni.items():
        s = donchian.signals(df, allow_short=True)
        res[n] = backtest.run(df, entry_long=s["entry_long"], exit_long=s["exit_long"],
            entry_short=s["entry_short"], exit_short=s["exit_short"],
            stop_distance=s["stop_distance"], costs=ct.for_asset("__default__", mult),
            risk_pct=0.01, initial_capital=CAP)
    eq = metrics.portfolio_equity(res, CAP)
    r = backtest.Result(equity=eq, trades=[t for x in res.values() for t in x.trades])
    return metrics.compute(r, CAP), res, r.returns

def main() -> int:
    uni, fuori = carica()
    inizio = min(d.index[0] for d in uni.values()); fine = max(d.index[-1] for d in uni.values())
    print(f"universo congelato: 49 mercati | esclusi per difetto dei dati: {len(fuori)}")
    print(f"  {', '.join(fuori)}")
    print(f"in test: {len(uni)} mercati | {inizio.date()} -> {fine.date()} | "
          f"{sum(len(d) for d in uni.values()):,} barre\n")

    out = {"esclusi": fuori, "mercati": sorted(uni), "scenari": {}}
    print(f"{'costi':<14}{'MAR':>7}{'Sharpe':>8}{'CAGR':>8}{'maxDD':>8}{'trade':>8}{'SR/SE':>8}")
    print("-" * 62)
    for nome, mult in [("dichiarati", 1.0), ("doppi", 2.0), ("quadrupli", 4.0)]:
        st, res, rend = porta(uni, mult)
        anni = (fine - inizio).days / 365.25
        se = ((1 + st.sharpe**2 / 2) / anni) ** 0.5
        pos = sum(1 for n in uni if metrics.compute(res[n], CAP).mar > 0)
        print(f"{nome:<14}{st.mar:7.2f}{st.sharpe:8.2f}{st.cagr:8.1%}{st.max_dd:8.1%}"
              f"{st.trades:8d}{st.sharpe/se:8.2f}")
        out["scenari"][nome] = st.as_dict() | {"sr_su_se": st.sharpe / se,
                                               "mercati_positivi": pos, "anni": anni}
    s1 = out["scenari"]["dichiarati"]
    print(f"\nanni di storia: {s1['anni']:.1f}")
    print(f"mercati con MAR positivo: {s1['mercati_positivi']}/{len(uni)}")
    print(f"\nsoglia dichiarata prima: SR/SE > 1.96 (95%)")
    print(f"esito a costi dichiarati: SR/SE = {s1['sr_su_se']:.2f} -> "
          f"{'DISTINGUIBILE DA ZERO' if s1['sr_su_se'] > 1.96 else 'non distinguibile'}")
    (RADICE / "results" / "futures_50y.json").write_text(json.dumps(out, indent=2, default=float))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
