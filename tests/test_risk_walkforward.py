"""Il runner che valida il rischio per trade fuori campione.

Non ricontrolla la macchina di walk-forward — quella ha i suoi test in
`test_validation.py`. Controlla le tre cose che questo runner aggiunge e che, se
sbagliate, produrrebbero un risultato plausibile e falso: che la griglia contenga
il riferimento contro cui si confronta, che il rischio arrivi davvero al motore,
e che sopra una certa soglia sia il tetto sul capitale a decidere la dimensione —
che è il motivo per cui il parametro non misura piu' il rischio.
"""

import importlib.util
import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "run_risk_walkforward", ROOT / "scripts" / "run_risk_walkforward.py")
rwf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rwf)


def serie_con_breakout():
    """Plateau, rottura del canale, trend, ritracciamento: un trade pulito.

    L'ingresso Donchian confronta il close con il massimo dei ``high`` delle 55
    barre precedenti, quindi una retta inclinata non rompe mai nulla: serve un
    plateau che fissi il canale e un salto che lo superi.
    """
    c = [100.0] * 80 + [106.0]
    for _ in range(120):
        c.append(c[-1] * 1.01)
    for _ in range(80):
        c.append(c[-1] * 0.99)
    c = np.array(c)
    idx = pd.date_range("2015-01-01", periods=len(c), freq="D")
    return pd.DataFrame({"open": c, "high": c * 1.015, "low": c * 0.985,
                         "close": c, "volume": 1000.0}, index=idx)


def quantita_massima(rischio: float) -> float:
    res = rwf.runner_per_rischio(rischio, False)("EQUITY", serie_con_breakout())
    assert res.trades, f"nessun trade a rischio {rischio}%"
    return max(t.initial_qty for t in res.trades)


def test_il_riferimento_e_dentro_la_griglia():
    # il confronto e' "scelto contro non scelto": se l'1% non fosse fra i
    # candidati, il delta misurerebbe due cose diverse
    assert rwf.RIFERIMENTO in rwf.GRIGLIA


def test_la_griglia_e_crescente_e_senza_duplicati():
    assert list(rwf.GRIGLIA) == sorted(set(rwf.GRIGLIA))


def test_nomi_distinti_per_ogni_rischio():
    nomi = [rwf.nome(r) for r in rwf.GRIGLIA]
    assert len(set(nomi)) == len(nomi)


def test_finche_decide_l_atr_la_quantita_e_proporzionale_al_rischio():
    assert quantita_massima(2.0) == pytest.approx(2 * quantita_massima(1.0), rel=1e-6)
    assert quantita_massima(4.0) == pytest.approx(4 * quantita_massima(1.0), rel=1e-6)


def test_sopra_una_soglia_decide_il_tetto_sul_capitale_non_l_atr():
    """Oltre una certa soglia ``risk_pct`` non regola piu' il rischio.

    E' l'osservazione su cui poggia `results/risk_walkforward.md`: la dimensione
    diventa ``cash / fill``, quindi raddoppiare il rischio non cambia nulla e il
    sizing proporzionale all'ATR e' di fatto spento.
    """
    assert quantita_massima(16.0) == pytest.approx(quantita_massima(8.0), rel=1e-9)
    assert quantita_massima(8.0) < 4 * quantita_massima(2.0)


def test_la_distribuzione_ignora_i_non_finiti():
    d = rwf.distribuzione([1.0, 3.0, float("nan"), float("inf")])
    assert d["n"] == 2
    assert d["media"] == pytest.approx(2.0)
    assert d["positivi"] == 2


def test_la_distribuzione_di_niente_e_vuota():
    assert rwf.distribuzione([float("nan")]) == {}
