"""Costi per asset, in percentuale del prezzo.

Perché per asset e non globali: `slippage=2` tick in Pine vale 0.00003% su BTC e
0.0999% su CORN — un fattore 3300 dentro lo stesso portafoglio. Un numero unico
non può essere realistico su entrambi, quindi ogni strumento ha il suo.

I valori sono **stime conservative retail**, non misure: commissione da listino
per le crypto spot, zero commissioni sugli ETF come sui broker attuali, e uno
slippage proporzionale alla liquidità dello strumento (SPY sottilissimo, CORN
largo perché è un ETF sottile). Vanno trattati come un'ipotesi dichiarata: il
runner esegue anche uno scenario a costi doppi, e se una strategia sopravvive
solo nello scenario ottimistico non è una strategia.
"""

from __future__ import annotations

from .backtest import Costs

# commissione e slippage per lato
COSTS: dict[str, Costs] = {
    "BTC": Costs(commission=0.0010, slippage=0.0005),
    "ETH": Costs(commission=0.0010, slippage=0.0005),
    "GOLD": Costs(commission=0.0000, slippage=0.0002),
    "CRUDE": Costs(commission=0.0000, slippage=0.0005),
    "CORN": Costs(commission=0.0000, slippage=0.0015),
    "EQUITY": Costs(commission=0.0000, slippage=0.0001),
}

DEFAULT = Costs(commission=0.0005, slippage=0.0010)


def for_asset(name: str, multiplier: float = 1.0) -> Costs:
    """Costi di un asset, opzionalmente moltiplicati per il test di sensibilità."""
    base = COSTS.get(name, DEFAULT)
    return Costs(commission=base.commission * multiplier, slippage=base.slippage * multiplier)
