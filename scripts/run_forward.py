#!/usr/bin/env python3
"""Registra le decisioni di oggi nel registro forward. Da lanciare una volta al giorno.

Non decide niente di suo: esegue il motore del backtest su tutta la storia
disponibile e scrive **l'ultima barra**. Questo è il punto — una seconda
implementazione «per il live» sarebbe il modo più diretto di ritrovarsi a
validare una cosa e a eseguirne un'altra.

Il registro è append-only (`data/forward/decisioni.jsonl`) e ogni riga porta
l'impronta della configurazione: se cambia, si vede.

Uso:
    python3 scripts/run_forward.py                 # registra e segnala anomalie
    python3 scripts/run_forward.py --solo-controlli # solo anomalie, non scrive
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine import costs as cost_table, data, forward, proposals
from engine.strategies import donchian

RADICE = pathlib.Path(__file__).resolve().parent.parent
REGISTRO = RADICE / "data" / "forward" / "decisioni.jsonl"
CODA = RADICE / "data" / "forward" / "proposte.jsonl"

CAPITALE = 100_000.0
RISCHIO = 0.01


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registro", type=pathlib.Path, default=REGISTRO)
    ap.add_argument("--solo-controlli", action="store_true",
                    help="non scrive: legge il registro e segnala le anomalie")
    ap.add_argument("--coda", type=pathlib.Path, default=CODA)
    ap.add_argument("--silenzio-giorni", type=int, default=90)
    args = ap.parse_args()

    if not args.solo_controlli:
        universe = {k: v[v.index >= data.DEFAULT_START]
                    for k, v in data.load_universe().items()}
        decisioni = [
            forward.decide(
                nome, df, donchian.DonchianWithExit(exit_mode="canale"),
                costs=cost_table.for_asset(nome), risk_pct=RISCHIO,
                initial_capital=CAPITALE,
            )
            for nome, df in universe.items()
        ]
        scritte = forward.append(args.registro, decisioni)
        print(f"registro: {args.registro}")
        print(f"decisioni di oggi: {len(decisioni)}  righe nuove scritte: {scritte}\n")
        print(f"{'asset':<10}{'data':<12}{'azione':<9}{'dir':>4}  {'tag':<12}{'close':>12}")
        print("-" * 62)
        for d in decisioni:
            print(f"{d.asset:<10}{d.data:<12}{d.azione:<9}{d.direzione:>4}  "
                  f"{d.tag:<12}{d.close:>12.2f}")

    righe = forward.load(args.registro)
    print(f"\nregistro: {len(righe)} righe")
    problemi = forward.anomalie(righe, silenzio_massimo_giorni=args.silenzio_giorni)
    if problemi:
        print(f"\n{len(problemi)} anomalia/e da guardare:")
        for p in problemi:
            print(f"  - {p}")

        # Le anomalie diventano proposte VUOTE: il sorvegliante sa dire che
        # qualcosa non torna, non cosa cambiare. Nessuna si applica da sola.
        oggi = str(pd.Timestamp.now().date())
        nuove = sum(proposals.proponi(args.coda, p)
                    for p in proposals.da_anomalie(problemi, quando=oggi))
        aperte = proposals.aperte(args.coda)
        print(f"\ncoda proposte: {args.coda}")
        print(f"  {nuove} nuova/e, {len(aperte)} aperta/e in totale. "
              f"Nessuna si applica da sola: vanno compilate e decise a mano.")
        return 1

    print("nessuna anomalia.")
    aperte = proposals.aperte(args.coda)
    if aperte:
        print(f"restano {len(aperte)} proposta/e aperte in {args.coda}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
