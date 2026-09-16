#!/usr/bin/env python3
"""Donchian 55/20 su 53 futures, 15-30 anni. Vedi results/preregistrazione_futures_2.md.

Secondo e ultimo colpo pulito su pysystemtrade: dopo questo la fascia 15-30 anni
e' bruciata come lo era la fascia >=30 dopo il primo test. Un solo run, parametri
e modello di costo dichiarati e committati PRIMA di eseguire questo script.

Differenza rispetto al primo test (run_futures50.py), che e' fallito per un
costo dichiarato dieci-trenta volte quello vero di un future liquido: qui il
costo e' una frazione della volatilita' giornaliera **di ciascun mercato**, non
una percentuale fissa del prezzo. Calibrato sui 30 mercati gia' bruciati, non su
questi (vedi la pre-registrazione). Il verdetto si da' al livello piu' severo
dei tre dichiarati (20% di una sigma giornaliera), non al piu' realistico.
"""
from __future__ import annotations
import json, pathlib, sys
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from engine import backtest, metrics
from engine.backtest import Costs
from engine.strategies import donchian

RADICE = pathlib.Path(__file__).resolve().parent.parent
DATI = RADICE / "data" / "futures_daily_2"
CAP = 100_000.0

#: livelli dichiarati nella pre-registrazione, come frazione di una sigma
#: giornaliera di round-trip. Il verdetto si da' al primo (il piu' severo); gli
#: altri due sono sensibilita'.
LIVELLI = {"verdetto (20% sigma)": 0.20, "sensibilita' 10% sigma": 0.10,
           "sensibilita' 5% sigma": 0.05}


def carica() -> tuple[dict[str, pd.DataFrame], list[str]]:
    """L'universo congelato, meno i mercati con un difetto dei dati.

    Stessa regola del primo test, applicata qui perche' la pre-registrazione la
    richiede meccanicamente: prezzo <= 0 o salto giornaliero oltre il 50% indica
    un attraversamento dello zero nell'aggiustamento per differenza, non un
    evento di mercato. Non e' una selezione sui rendimenti — e' un controllo di
    validita' della serie, fatto prima di calcolare qualunque rendimento.
    """
    fuori, dentro = [], {}
    for m in open(RADICE / "data" / "futures_universe_2.txt").read().split():
        d = pd.read_csv(DATI / f"{m}.csv.gz")
        d["date"] = pd.to_datetime(d["date"]); d = d.set_index("date")
        if (d["close"] <= 0).any() or (d["close"].pct_change().abs() > 0.5).any():
            fuori.append(m); continue
        dentro[m] = d
    return dentro, fuori


def costi_per_mercato(uni: dict[str, pd.DataFrame], frazione_sigma: float) -> dict[str, Costs]:
    """Round-trip = frazione_sigma * (deviazione standard dei rendimenti giornalieri).

    Diviso a meta' fra i due lati (entrata + uscita), e a meta' fra commissione e
    slippage dentro ogni lato — la suddivisione interna e' arbitraria, conta solo
    la somma, che e' ``per_side`` in ``backtest.Costs``.
    """
    out = {}
    for n, df in uni.items():
        sigma = df["close"].pct_change().std()
        round_trip = frazione_sigma * sigma
        per_side = round_trip / 2.0
        out[n] = Costs(commission=per_side / 2.0, slippage=per_side / 2.0)
    return out


def porta(uni, costi):
    res = {}
    for n, df in uni.items():
        s = donchian.signals(df, allow_short=True)
        res[n] = backtest.run(df, entry_long=s["entry_long"], exit_long=s["exit_long"],
            entry_short=s["entry_short"], exit_short=s["exit_short"],
            stop_distance=s["stop_distance"], costs=costi[n],
            risk_pct=0.01, initial_capital=CAP)
    eq = metrics.portfolio_equity(res, CAP)
    r = backtest.Result(equity=eq, trades=[t for x in res.values() for t in x.trades])
    return metrics.compute(r, CAP), res


def main() -> int:
    uni, fuori = carica()
    inizio = min(d.index[0] for d in uni.values()); fine = max(d.index[-1] for d in uni.values())
    print(f"universo congelato: 53 mercati | esclusi per difetto dei dati: {len(fuori)}")
    print(f"  {', '.join(fuori)}")
    print(f"in test: {len(uni)} mercati | {inizio.date()} -> {fine.date()} | "
          f"{sum(len(d) for d in uni.values()):,} barre\n")

    out = {"esclusi": fuori, "mercati": sorted(uni), "livelli": {}}
    print(f"{'livello di costo':<26}{'MAR':>7}{'Sharpe':>8}{'CAGR':>8}{'maxDD':>8}{'trade':>8}{'SR/SE':>8}{'mkt+':>7}")
    print("-" * 80)
    for nome, frazione in LIVELLI.items():
        costi = costi_per_mercato(uni, frazione)
        st, res = porta(uni, costi)
        anni = (fine - inizio).days / 365.25
        se = ((1 + st.sharpe**2 / 2) / anni) ** 0.5
        pos = sum(1 for n in uni if metrics.compute(res[n], CAP).mar > 0)
        print(f"{nome:<26}{st.mar:7.2f}{st.sharpe:8.2f}{st.cagr:8.1%}{st.max_dd:8.1%}"
              f"{st.trades:8d}{st.sharpe / se:8.2f}{pos:6d}/53")
        out["livelli"][nome] = st.as_dict() | {"sr_su_se": st.sharpe / se,
                                                "mercati_positivi": pos, "anni": anni,
                                                "frazione_sigma": frazione}

    verdetto = out["livelli"]["verdetto (20% sigma)"]
    print(f"\nanni di storia: {verdetto['anni']:.1f}")
    print(f"soglia dichiarata prima: SR/SE > 1.96 (95%), al livello di costo piu' severo")
    print(f"esito al verdetto (20% sigma): SR/SE = {verdetto['sr_su_se']:.2f} -> "
          f"{'DISTINGUIBILE DA ZERO' if verdetto['sr_su_se'] > 1.96 else 'non distinguibile'}")
    (RADICE / "results" / "futures_50y_2.json").write_text(json.dumps(out, indent=2, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
