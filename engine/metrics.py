"""Metriche di performance.

L'annualizzazione non è una costante: le crypto hanno 365 barre l'anno, gli ETF
circa 252. Usare 252 su BTC gonfia lo Sharpe di circa il 20%, quindi il fattore
viene dedotto dalla serie invece che assunto.

Il profit factor è riportato, non inseguito: come discusso, su questa famiglia di
strategie un PF alto convive con drawdown profondi, e la metrica primaria è il
MAR (CAGR / max drawdown).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from .backtest import Result


def bars_per_year(index: pd.DatetimeIndex) -> float:
    """Dedotto dalla spaziatura mediana delle barre."""
    if len(index) < 3:
        return 252.0
    step_days = np.median(np.diff(index.values).astype("timedelta64[D]").astype(float))
    return 365.25 / max(step_days, 1e-9)


@dataclass
class Stats:
    trades: int
    cagr: float
    max_dd: float
    mar: float
    sharpe: float
    sortino: float
    profit_factor: float
    win_rate: float
    avg_r: float
    exposure: float
    final_equity: float

    def as_dict(self) -> dict:
        return asdict(self)


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float(((peak - equity) / peak).max())


def compute(result: Result, initial_capital: float = 100_000.0,
            years: float | None = None) -> Stats:
    """Statistiche di una curva di equity.

    ``years`` serve per le curve **non contigue** prodotte dalla validazione:
    quando i segmenti di un fold purgato vengono concatenati, la distanza fra la
    prima e l'ultima data include anche i buchi, e dedurre da lì gli anni
    trascorsi gonfierebbe il denominatore del CAGR. Chi conosce la durata vera
    la passa; tutti gli altri non cambiano comportamento.
    """
    eq = result.equity
    closed = [t for t in result.trades if not t.is_open]

    if years is None:
        years = (eq.index[-1] - eq.index[0]).days / 365.25 if len(eq) > 1 else 0.0
    total_return = eq.iloc[-1] / initial_capital
    cagr = total_return ** (1 / years) - 1 if years > 0 and total_return > 0 else float("nan")

    rets = eq.pct_change().dropna()
    ppy = bars_per_year(eq.index)
    vol = rets.std()
    sharpe = float(rets.mean() / vol * np.sqrt(ppy)) if vol > 0 else float("nan")
    downside = rets[rets < 0].std()
    sortino = float(rets.mean() / downside * np.sqrt(ppy)) if downside > 0 else float("nan")

    dd = max_drawdown(eq)
    wins = [t.pnl for t in closed if t.pnl > 0]
    losses = [-t.pnl for t in closed if t.pnl <= 0]
    gross_win, gross_loss = sum(wins), sum(losses)

    return Stats(
        trades=len(closed),
        cagr=cagr,
        max_dd=dd,
        mar=cagr / dd if dd > 0 and np.isfinite(cagr) else float("nan"),
        sharpe=sharpe,
        sortino=sortino,
        profit_factor=gross_win / gross_loss if gross_loss > 0 else float("inf"),
        win_rate=len(wins) / len(closed) if closed else float("nan"),
        avg_r=float(np.mean([t.r_multiple for t in closed])) if closed else float("nan"),
        exposure=result.exposure,
        final_equity=float(eq.iloc[-1]),
    )


def portfolio_equity(results: dict[str, Result], initial_capital: float = 100_000.0) -> pd.Series:
    """Aggrega i risultati per asset in un'unica curva.

    Gli asset hanno calendari diversi (crypto 7 giorni, ETF 5), quindi si
    aggregano i **rendimenti** su un indice unione, con rendimento nullo nei
    giorni in cui un mercato è chiuso. Capitale diviso in parti uguali: senza
    una regola di allocazione dichiarata, qualunque peso diverso sarebbe una
    scelta presa guardando i risultati.
    """
    per_asset = []
    for name, res in results.items():
        r = res.equity.pct_change()
        r.name = name
        per_asset.append(r)

    frame = pd.concat(per_asset, axis=1).sort_index()
    combined = frame.fillna(0.0).mean(axis=1)
    return initial_capital * (1 + combined).cumprod()
