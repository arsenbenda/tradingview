#!/usr/bin/env python3
"""Il giro settimanale: cosa chiedere ai connector, e cosa farne.

Il registro forward vale solo se viene alimentato con regolarità, e
l'alimentazione è manuale: i connector MCP non sono richiamabili da uno script e
non ci sono chiavi API in ambiente (`data/README.md`). Una procedura manuale che
va ricordata a memoria viene saltata, quindi questa la dice.

Due tempi:

    python3 scripts/settimana.py              # cosa chiedere, asset per asset
    # [si incollano le risposte in data/staging/<ASSET>.csv]
    python3 scripts/settimana.py --fondi      # fonde, valida, registra, controlla

Il manifesto delle fonti sta qui dentro apposta. `data/README.md` impone **una
sola famiglia di fonti per backtest**, e il progetto ha già pagato cara la
violazione di quella regola — futures ed ETF con convenzioni orarie diverse,
correlazione dei rendimenti 0.88 con volatilità identiche. Scritto nel codice,
il fornitore di un asset non cambia per distrazione in una mattina di fretta.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine import data, forward

RADICE = pathlib.Path(__file__).resolve().parent.parent
STAGING = RADICE / "data" / "staging"

#: asset → (simbolo da chiedere, connector). Non si cambia senza cambiare
#: `data/README.md` e senza rifare i numeri: la fonte è parte del dato.
FONTI = {
    "BTC":    ("BTC/USD", "Alpha Vantage"),
    "ETH":    ("ETH/USD", "Alpha Vantage"),
    "GOLD":   ("GLD",     "Twelve Data"),
    "CRUDE":  ("USO",     "Twelve Data"),
    "CORN":   ("CORN",    "Twelve Data"),
    "EQUITY": ("SPY",     "Twelve Data"),
}


def da_chiedere() -> list[tuple[str, str, str, str]]:
    """Per ogni asset: simbolo, connector, da quale data, quanti giorni di ritardo."""
    universe = data.load_universe()
    oggi = pd.Timestamp.now().normalize()
    righe = []
    for asset, (simbolo, connector) in FONTI.items():
        ultima = universe[asset].index[-1]
        # si riparte da qualche giorno prima dell'ultima barra: il sovrapposto
        # serve a far vedere a `ingest` se il fornitore ha rettificato qualcosa
        da = (ultima - pd.Timedelta(days=5)).date()
        righe.append((asset, f"{simbolo} ({connector})", str(da), (oggi - ultima).days))
    return righe


def fase_richieste() -> int:
    righe = da_chiedere()
    print("Chiedere ai connector, in sessione, e salvare in data/staging/<ASSET>.csv:\n")
    print(f"{'asset':<9}{'simbolo (connector)':<28}{'da':<13}{'ritardo':>8}")
    print("-" * 60)
    for asset, simbolo, da, ritardo in righe:
        nota = "  <-- aggiornato" if ritardo <= 3 else ""
        print(f"{asset:<9}{simbolo:<28}{da:<13}{ritardo:>5} gg{nota}")
    print(f"\nLe richieste partono 5 giorni prima dell'ultima barra: il tratto")
    print(f"sovrapposto e' quello che fa vedere a ingest se il fornitore ha")
    print(f"rettificato qualcosa. Senza, una rettifica passerebbe inosservata.\n")
    print(f"Poi: python3 scripts/settimana.py --fondi")
    return 0


def fase_fusione(prova: bool) -> int:
    py = sys.executable
    passi = [
        ("aggiornamento delle serie",
         [py, str(RADICE / "scripts" / "update_data.py")] + (["--prova"] if prova else [])),
    ]
    for titolo, cmd in passi:
        print(f"=== {titolo} ===")
        esito = subprocess.run(cmd, text=True)
        if esito.returncode != 0:
            print(f"\nfermo su '{titolo}'. Niente e' stato registrato.")
            return 1

    if prova:
        print("\n[prova] mi fermo qui: il registro si scrive solo sul giro vero.")
        return 0

    print("\n=== controllo di allineamento ===")
    universe = {k: v[v.index >= data.DEFAULT_START] for k, v in data.load_universe().items()}
    try:
        forward.verifica_allineamento(universe)
    except forward.SerieDisallineate as e:
        print(f"{e}\n\nNiente e' stato registrato.")
        return 1
    print(f"tutte le serie al {forward.allineamento(universe)['BTC']}.")

    print("\n=== registro forward ===")
    return subprocess.run([py, str(RADICE / "scripts" / "run_forward.py")], text=True).returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fondi", action="store_true",
                    help="fonde quanto sta in data/staging/, poi registra")
    ap.add_argument("--prova", action="store_true", help="non scrive niente")
    args = ap.parse_args()
    return fase_fusione(args.prova) if args.fondi else fase_richieste()


if __name__ == "__main__":
    raise SystemExit(main())
