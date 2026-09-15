#!/usr/bin/env python3
"""Aggiorna le serie di `data/raw/` con barre fresche, senza riscrivere il passato.

**Il fetch non è automatizzabile oggi, ed è una scelta del progetto, non una
dimenticanza.** `data/README.md` lo dice da prima: i connector MCP non sono
richiamabili da uno script, e non ci sono chiavi API in ambiente. Quindi il
percorso è in due tempi:

1. le serie fresche si chiedono ai connector in sessione e si salvano in
   `data/staging/<ASSET>.csv` (formato dei connector: separatore `;` per Twelve
   Data, `,` per Alpha Vantage, colonna `datetime` o `date`);
2. questo script le fonde, con i controlli che il registro forward richiede.

Il pezzo che conta è il secondo. Scaricare è facile; **decidere cosa fare quando
i dati nuovi contraddicono i vecchi** è la parte che, sbagliata in silenzio,
rende irriproducibile ogni decisione già registrata. Quella logica sta in
`engine/ingest.py` ed è coperta dai test.

Uso:
    python3 scripts/update_data.py                 # fonde tutto ciò che è in staging
    python3 scripts/update_data.py --prova         # dice cosa farebbe, non scrive
"""

from __future__ import annotations

import argparse
import io
import pathlib
import subprocess
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from engine import data, ingest

RADICE = pathlib.Path(__file__).resolve().parent.parent
STAGING = RADICE / "data" / "staging"
RAW = RADICE / "data" / "raw"


def leggi_fresco(path: pathlib.Path) -> pd.DataFrame:
    """Legge un file dei connector, qualunque sia il separatore e il nome della data."""
    testo = path.read_text()
    sep = ";" if testo.splitlines()[0].count(";") > testo.splitlines()[0].count(",") else ","
    df = pd.read_csv(io.StringIO(testo), sep=sep)
    df.columns = [c.strip().lower() for c in df.columns]
    for nome in ("datetime", "date", "timestamp"):
        if nome in df.columns:
            return df.rename(columns={nome: "date"})
    raise ValueError(f"{path.name}: nessuna colonna di data fra datetime/date/timestamp")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staging", type=pathlib.Path, default=STAGING)
    ap.add_argument("--prova", action="store_true", help="non scrive niente")
    args = ap.parse_args()

    if not args.staging.exists() or not any(args.staging.glob("*.csv")):
        print(f"niente da fondere in {args.staging}")
        print("\nLe serie fresche vanno chieste ai connector in sessione e salvate lì,")
        print("un file per asset, con il nome dell'asset (BTC.csv, EQUITY.csv, ...).")
        print("I connector MCP non sono richiamabili da uno script: vedi data/README.md.")
        return 0

    toccati, esiti, fermati = [], [], []
    for f in sorted(args.staging.glob("*.csv")):
        asset = f.stem.upper()
        if asset not in data.FILES:
            print(f"  {asset}: sconosciuto, salto (attesi: {', '.join(sorted(data.FILES))})")
            continue
        destinazione = RAW / data.FILES[asset]
        try:
            esito = ingest.aggiorna(destinazione, leggi_fresco(f), asset=asset,
                                    scrivi_su_disco=not args.prova)
        except ingest.StoriaRiscritta as e:
            fermati.append(str(e))
            continue
        esiti.append(esito)
        if esito.aggiunte:
            toccati.append(destinazione)
        print(f"  {esito}")

    if fermati:
        print("\n" + "=" * 70)
        print("AGGIORNAMENTO FERMO")
        print("=" * 70)
        for m in fermati:
            print(f"\n{m}")
        return 1

    if not toccati:
        print("\nnessuna barra nuova: le serie erano già aggiornate.")
        return 0

    if args.prova:
        print(f"\n[prova] {len(toccati)} serie sarebbero state aggiornate, niente scritto.")
        return 0

    # gate di qualità sulle sole serie toccate. Il progetto lo impone su ogni
    # serie nuova; una serie *estesa* è una serie nuova.
    print(f"\ngate di qualità su {len(toccati)} serie aggiornate:")
    esito = subprocess.run(
        [sys.executable, str(RADICE / "scripts" / "validate_series.py"),
         *[str(p) for p in toccati]],
        capture_output=True, text=True,
    )
    print(esito.stdout.rstrip())
    if esito.returncode != 0:
        print(esito.stderr.rstrip())
        print("\nIl gate ha segnalato qualcosa: le serie sono scritte ma vanno guardate.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
