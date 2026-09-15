"""Caricamento delle serie di prezzo con controlli non negoziabili.

Ogni difetto che `scripts/validate_series.py` cerca nei file grezzi si
ripresenterebbe qui a valle: caricare senza controllare significa scoprire il
problema come un risultato strano invece che come un errore.
"""

from __future__ import annotations

import pathlib

import pandas as pd

RAW = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"

# nome logico -> file. Un solo set di parametri su tutti, sempre.
FILES = {
    # crypto — Alpha Vantage
    "BTC": "BTCUSD_1d.csv",
    "ETH": "ETHUSD_1d.csv",
    # azionario — Twelve Data
    "EQUITY": "SPY_1d_td.csv",
    "EQUITY_INTL": "EFA_1d_td.csv",
    "EQUITY_EM": "VWO_1d_td.csv",
    # obbligazionario
    "BOND_LONG": "TLT_1d_td.csv",
    "BOND_HY": "HYG_1d_td.csv",
    # valute
    "USD": "UUP_1d_td.csv",
    "JPY": "FXY_1d_td.csv",
    # materie prime
    "GOLD": "GLD_1d_td.csv",
    "SILVER": "SLV_1d_td.csv",
    "CRUDE": "USO_1d_td.csv",
    "NATGAS": "UNG_1d_td.csv",
    "CORN": "CORN_1d_td.csv",
    # immobiliare
    "REIT": "VNQ_1d_td.csv",
}

#: i sei asset su cui sono stati prodotti tutti i risultati fino al 2026-09-15.
#:
#: Resta il default di ``load_universe`` per una ragione sola: ogni numero in
#: ``results/`` è stato calcolato su questi sei, e un default che cambia
#: renderebbe irriproducibili report già scritti e già commessi. Chi vuole
#: l'universo allargato lo chiede per nome.
CORE = ("BTC", "ETH", "GOLD", "CRUDE", "CORN", "EQUITY")

#: i quindici strumenti dichiarati in ``data/universe_declaration.md``.
#:
#: Cinque settori più l'immobiliare, con obbligazionario e valute che ai sei
#: mancavano del tutto. La lista è congelata: uno strumento esce solo per un
#: difetto dei dati, documentato. Non esce perché rende poco — quattro dei sei
#: originali rendono quasi nulla da soli, e il portafoglio batte comunque il
#: migliore di loro.
EXTENDED = CORE + ("EQUITY_INTL", "EQUITY_EM", "BOND_LONG", "BOND_HY",
                   "USD", "JPY", "SILVER", "NATGAS", "REIT")

OHLCV = ["open", "high", "low", "close", "volume"]

#: inizio del periodo di lavoro, comune a tutto l'universo.
#:
#: È la prima barra di ETH, lo strumento con meno storia: GLD, USO e SPY
#: partono dal 2006, CORN dal 2010, BTC dal 2013. Sta qui e non dentro i runner
#: perché ogni script che la ridichiara è uno script che un giorno userà una
#: data diversa dagli altri, e due backtest su periodi diversi non sono
#: confrontabili — che è l'unica cosa che questo progetto fa.
#:
#: Aggiungere uno strumento **non** obbliga a spostarla in avanti: chi quota
#: dopo contribuisce dalla sua prima barra, ed è escluso dal denominatore del
#: portafoglio prima di allora (``metrics.equal_weight_returns``). Va spostata
#: solo se si toglie ETH o si aggiunge qualcosa con ancora meno storia.
DEFAULT_START = "2015-08-08"


def load(name_or_path: str) -> pd.DataFrame:
    """Carica una serie per nome logico (``"BTC"``) o per percorso.

    Restituisce un DataFrame indicizzato per data, ordinato, con colonne float.
    Solleva ValueError se la serie ha difetti che falserebbero il backtest.
    """
    path = RAW / FILES[name_or_path] if name_or_path in FILES else pathlib.Path(name_or_path)
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


def load_universe(names: "list[str] | tuple[str, ...] | None" = None) -> dict[str, pd.DataFrame]:
    """Carica un universo. Default: i sei di ``CORE``, per non spostare i risultati già pubblicati."""
    return {n: load(n) for n in (names or CORE)}


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
