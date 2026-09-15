#!/usr/bin/env python3
"""Parity test: il motore contro l'export dello Strategy Tester di TradingView.

TradingView non espone API per lo Strategy Tester, ma l'export in xlsx contiene
tre cose che bastano: la lista dei trade con date e prezzi, il riepilogo di
performance, e — decisivo — il foglio ``Properties`` con **tutti i valori degli
input** usati in quella esecuzione.

Quest'ultimo è il motivo per cui il primo confronto era sbagliato. L'export si
chiama "Conservative" perché è un *preset*, non la configurazione di default del
Pine: sei input differiscono, e due di quei sei spengono altrettanti meccanismi
di ingresso. Confrontare il porting a default contro un preset produce uno scarto
che sembra un difetto di porting e non lo è.

**Regola che ne esce: leggere sempre il foglio Properties prima di confrontare, e
costruire la strategia con quei valori.** Le differenze che restano dopo sono le
uniche che parlano del codice.

Uso: python3 scripts/run_parity.py [--xlsx PERCORSO] [--tolleranza-giorni 2]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine import backtest, costs as cost_table
from engine.strategies.sanyaku import SanyakuV55

OUT = pathlib.Path(__file__).resolve().parent.parent / "results"

#: i sei input in cui il preset "Conservative" differisce dai default del Pine.
#: Ricavati dal foglio ``Properties``, non indovinati.
PRESET_CONSERVATIVE = dict(
    enabled_entries=(1, 2, 4),   # Entry 3 e Entry 5: Off
    htf_gate=False,              # HTF gate on continuation entries: Off
    e4_bypass_lock=False,        # Entry 4 ignores zone lock: Off
    dd_threshold=12.0,           # soglia del circuit breaker: 12 invece di 15
    dd_risk_factor=0.9,          # fattore di riduzione: 0.9 invece di 0.5
)


def trade_di_tradingview(xlsx: pathlib.Path) -> pd.DataFrame:
    tv = pd.read_excel(xlsx, sheet_name="Trades")
    tv["dt"] = pd.to_datetime(tv["Date and time"], errors="coerce")
    ent = tv[tv["Type"].str.contains("Entry")][["dt", "Price USD"]]
    return ent.dropna(subset=["dt"]).assign(dt=lambda d: d["dt"].dt.normalize())


def confronta(ours: list[tuple], tv: pd.DataFrame, tolleranza: int) -> dict:
    od = [o[0] for o in ours]
    td = list(tv["dt"])
    esatti = len(set(od) & set(td))
    entro = sum(1 for t in td if any(abs((t - o).days) <= tolleranza for o in od))
    in_piu = [o for o in ours if not any(abs((o[0] - t).days) <= tolleranza for t in td)]
    mancanti = [t for t in td if not any(abs((t - o).days) <= tolleranza for o in od)]
    return {"nostri": len(ours), "tradingview": len(td), "esatti": esatti,
            f"entro_{tolleranza}_giorni": entro,
            "nostri_in_piu": [str(o[0].date()) for o in in_piu],
            "tradingview_mancanti": [str(t.date()) for t in mancanti]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", type=pathlib.Path, required=True,
                    help="export xlsx dello Strategy Tester")
    ap.add_argument("--tolleranza-giorni", type=int, default=2)
    ap.add_argument("--serie", default="data/raw/BTCUSD_1d.csv")
    ap.add_argument("--da", default="2020-01-03",
                    help="inizio del backtesting range di TradingView")
    ap.add_argument("--a", default="2026-09-15")
    ap.add_argument("--warmup-giorni", type=int, default=400,
                    help="barre caricate PRIMA di --da perche' gli indicatori siano caldi")
    args = ap.parse_args()

    tv = trade_di_tradingview(args.xlsx)
    df = pd.read_csv(args.serie)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")

    # Il "backtesting range" di TradingView dice da quando conta i trade, non da
    # quando esistono gli indicatori: sul grafico la nuvola e' gia' calda perche'
    # lo storico precedente e' caricato. Troncare la serie a --da farebbe partire
    # Ichimoku da NaN per ~78 barre e produrrebbe ingressi mancanti che sembrano
    # divergenze di porting e sono solo riscaldamento.
    inizio = pd.Timestamp(args.da)
    win = df[inizio - pd.Timedelta(days=args.warmup_giorni):args.a]
    disponibile = (win.index[0] < inizio)

    print(f"export: {args.xlsx.name}")
    print(f"serie:  {args.serie} | {win.index[0].date()} → {win.index[-1].date()} "
          f"| {len(win)} barre "
          f"({'warmup ok' if disponibile else 'ATTENZIONE: nessun warmup disponibile'})")
    print(f"TradingView: {len(tv)} ingressi\n")

    esito = {}
    for nome, kw in [("default del Pine", {}), ("preset Conservative", PRESET_CONSERVATIVE)]:
        res = backtest.run_strategy(
            win, SanyakuV55(**kw), costs=cost_table.for_asset("BTC"),
            risk_pct=0.01, initial_capital=100_000.0, max_notional_pct=0.60,
        )
        # solo i trade dentro il backtesting range di TradingView: il warmup
        # serve a scaldare gli indicatori, non a produrre trade da confrontare
        ours = [(pd.Timestamp(t.entry_date).normalize(), t.entry_price, t.tag)
                for t in res.trades if pd.Timestamp(t.entry_date) >= inizio]
        c = confronta(ours, tv, args.tolleranza_giorni)
        esito[nome] = c
        print(f"{nome:22s} ingressi {c['nostri']:3d}  esatti {c['esatti']:2d}/{c['tradingview']}  "
              f"entro {args.tolleranza_giorni}gg {c[f'entro_{args.tolleranza_giorni}_giorni']:2d}/"
              f"{c['tradingview']}  nostri in più {len(c['nostri_in_piu'])}")

    # Scarto fra i feed. Il prezzo del trade di TradingView e' il **fill**, cioe'
    # l'apertura della barra d'ingresso, non la sua chiusura: confrontarlo con il
    # close gonfia lo scarto di un ordine di grandezza (1.40% contro 0.19% di
    # mediana su questo export) e fa sembrare differenza di fonte quella che e'
    # solo la differenza fra due barre.
    scarti = [abs((win["open"].asof(r["dt"]) - r["Price USD"]) / r["Price USD"] * 100)
              for _, r in tv.iterrows()
              if pd.notna(win["open"].asof(r["dt"])) and r["Price USD"]]
    if scarti:
        print(f"\nscarto |fill TradingView - open della stessa barra| su {len(scarti)} ingressi:")
        print(f"  mediana {statistics.median(scarti):.2f}%   max {max(scarti):.2f}%")
        esito["scarto_feed_pct"] = {"n": len(scarti), "mediana": statistics.median(scarti),
                                    "max": max(scarti)}

    OUT.mkdir(exist_ok=True)
    (OUT / "parity.json").write_text(json.dumps(esito, indent=2, default=str))
    print("\nrisultati in results/parity.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
