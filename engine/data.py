"""Caricamento delle serie di prezzo con controlli non negoziabili.

Ogni difetto che `scripts/validate_series.py` cerca nei file grezzi si
ripresenterebbe qui a valle: caricare senza controllare significa scoprire il
problema come un risultato strano invece che come un errore.
"""

from __future__ import annotations

import pathlib

import pandas as pd

RAW = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"

# nome logico -> file. Sei asset eterogenei, un solo set di parametri.
UNIVERSE = {
    "BTC": "BTCUSD_1d.csv",
    "ETH": "ETHUSD_1d.csv",
    "GOLD": "GLD_1d_td.csv",
    "CRUDE": "USO_1d_td.csv",
    "CORN": "CORN_1d_td.csv",
    "EQUITY": "SPY_1d_td.csv",
}

OHLCV = ["open", "high", "low", "close", "volume"]


def load(name_or_path: str) -> pd.DataFrame:
    """Carica una serie per nome logico (``"BTC"``) o per percorso.

    Restituisce un DataFrame indicizzato per data, ordinato, con colonne float.
    Solleva ValueError se la serie ha difetti che falserebbero il backtest.
    """
    path = RAW / UNIVERSE[name_or_path] if name_or_path in UNIVERSE else pathlib.Path(name_or_path)
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    missing = [c for c in OHLCV if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name}: colonne mancanti {missing}")
    df = df[OHLCV].astype(float)

    if df.index.has_duplicates:
        dups = df.index[df.index.duplicated()].tolist()[:3]
        raise ValueError(f"{path.name}: date duplicate, es. {dups}")
    if (df["close"] <= 0).any():
        raise ValueError(f"{path.name}: prezzi non positivi")

    bad = ~((df["low"] <= df[["open", "close"]].min(axis=1)) & (df["high"] >= df[["open", "close"]].max(axis=1)))
    if bad.any():
        raise ValueError(f"{path.name}: {int(bad.sum())} barre con OHLC incoerente")

    return df


def load_universe(names: list[str] | None = None) -> dict[str, pd.DataFrame]:
    """Carica l'universo di lavoro."""
    return {n: load(n) for n in (names or list(UNIVERSE))}


def common_period(series: dict[str, pd.DataFrame]) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Intervallo coperto da tutte le serie.

    Le date **non** vengono allineate su un indice comune: crypto (7 giorni) ed
    ETF (5 giorni) hanno calendari diversi, e forzare un merge inventerebbe
    barre nei weekend o cancellerebbe quelle crypto. Ogni asset viene testato
    sul proprio calendario; solo i rendimenti si aggregano a livello di
    portafoglio.
    """
    return (
        max(df.index[0] for df in series.values()),
        min(df.index[-1] for df in series.values()),
    )
