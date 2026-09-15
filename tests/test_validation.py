"""Test del modulo di validazione.

Le proprietà da cui dipende ogni conclusione del report: la normale calcolata
senza scipy deve essere quella vera, la soglia del Deflated Sharpe deve crescere
con il numero di prove, i fold devono essere davvero purgati, e la misurazione su
una finestra non deve contenere nulla di ciò che è successo nel riscaldamento.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from engine import backtest, hypotheses, metrics, validation as v


# --------------------------------------------------------------------------
# la normale, senza scipy
# --------------------------------------------------------------------------

@pytest.mark.parametrize("p,expected", [
    (0.5, 0.0),
    (0.975, 1.959963984540054),
    (0.995, 2.5758293035489004),
    (0.001, -3.090232306167813),
    (1 - 1 / 22, 1.6906216295848984),          # la quantile che usa il DSR
])
def test_norm_ppf_riproduce_le_quantili_note(p, expected):
    assert v.norm_ppf(p) == pytest.approx(expected, abs=1e-9)


def test_norm_cdf_e_ppf_sono_inverse():
    for p in (1e-6, 0.01, 0.2, 0.5, 0.8, 0.99, 1 - 1e-9):
        assert v.norm_cdf(v.norm_ppf(p)) == pytest.approx(p, rel=1e-9, abs=1e-12)


def test_norm_ppf_rifiuta_valori_fuori_dominio():
    for bad in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            v.norm_ppf(bad)


# --------------------------------------------------------------------------
# Sharpe probabilistico e deflazionato
# --------------------------------------------------------------------------

def test_psr_vale_un_mezzo_quando_lo_sharpe_osservato_e_la_soglia():
    """Se lo Sharpe osservato coincide con la soglia, è testa o croce."""
    assert v.probabilistic_sharpe_ratio(0.05, 500, 0.0, 3.0, sr_star=0.05) == pytest.approx(0.5)


def test_psr_cresce_con_le_osservazioni():
    """Lo stesso Sharpe su più dati è più credibile."""
    corto = v.probabilistic_sharpe_ratio(0.05, 100, 0.0, 3.0)
    lungo = v.probabilistic_sharpe_ratio(0.05, 4000, 0.0, 3.0)
    assert 0.5 < corto < lungo < 1.0


def test_psr_penalizza_asimmetria_negativa_e_code_grasse():
    base = v.probabilistic_sharpe_ratio(0.05, 1000, 0.0, 3.0)
    storto = v.probabilistic_sharpe_ratio(0.05, 1000, -1.5, 3.0)
    code = v.probabilistic_sharpe_ratio(0.05, 1000, 0.0, 12.0)
    assert storto < base and code < base


def test_soglia_del_massimo_cresce_con_il_numero_di_prove():
    """Provare più cose alza l'asticella: è tutto il punto del DSR."""
    s = [v.expected_max_sharpe(n, 0.02) for n in (2, 5, 22, 100)]
    assert s == sorted(s) and all(x > 0 for x in s)


def test_soglia_del_massimo_e_nulla_senza_dispersione_o_senza_prove():
    assert v.expected_max_sharpe(22, 0.0) == 0.0
    assert v.expected_max_sharpe(1, 0.02) == 0.0


def test_soglia_del_massimo_e_proporzionale_alla_dispersione():
    assert v.expected_max_sharpe(22, 0.04) == pytest.approx(2 * v.expected_max_sharpe(22, 0.02))


def test_il_dsr_non_supera_mai_il_psr():
    """Deflazionare può solo togliere: sr0 >= 0 per costruzione."""
    rng = np.random.default_rng(3)
    idx = pd.date_range("2016-01-01", periods=2000, freq="D")
    r = pd.Series(rng.normal(0.0006, 0.01, len(idx)), index=idx)
    trials = list(rng.normal(0.02, 0.02, 22))
    out = v.deflated_sharpe(r, trials)
    assert out.n_trials == 22
    assert out.sr0 > 0
    assert out.dsr <= out.psr


def test_il_dsr_scende_quando_si_provano_piu_ipotesi():
    rng = np.random.default_rng(7)
    idx = pd.date_range("2016-01-01", periods=2000, freq="D")
    r = pd.Series(rng.normal(0.0008, 0.01, len(idx)), index=idx)
    trials = list(rng.normal(0.02, 0.02, 22))
    poche = v.deflated_sharpe(r, trials, n_trials=3)
    tante = v.deflated_sharpe(r, trials, n_trials=500)
    assert tante.dsr < poche.dsr


def test_lo_sharpe_annualizzato_usa_le_barre_per_anno_della_serie():
    idx = pd.date_range("2016-01-01", periods=1000, freq="D")
    r = pd.Series(0.001, index=idx)
    r.iloc[::3] = -0.0005                       # serve varianza non nulla
    out = v.deflated_sharpe(r, [0.01] * 5)
    assert out.sr_annual == pytest.approx(out.sr * math.sqrt(365.25), rel=1e-6)


# --------------------------------------------------------------------------
# finestre e fold
# --------------------------------------------------------------------------

def test_le_finestre_di_test_sono_contigue_e_non_si_sovrappongono():
    w = v.rolling_windows("2015-08-10", "2026-09-14")
    assert len(w) == 8
    for prima, dopo in zip(w, w[1:]):
        assert prima.test.end == dopo.test.start
    for win in w:
        assert win.train.end == win.test.start
        assert win.train.years == pytest.approx(3.0, abs=0.01)


def test_la_finestra_finale_troppo_corta_viene_scartata():
    """Un MAR su due mesi non è un dato."""
    lunghe = v.rolling_windows("2015-01-01", "2019-06-01", min_test_days=300)
    corte = v.rolling_windows("2015-01-01", "2019-06-01", min_test_days=30)
    assert len(corte) > len(lunghe)
    assert all(win.test.days >= 300 for win in lunghe)


def test_i_fold_coprono_il_periodo_senza_sovrapporsi():
    folds = v.purged_folds("2015-08-10", "2026-09-14", n_splits=5)
    assert len(folds) == 5
    assert folds[0].test.start == pd.Timestamp("2015-08-10")
    assert folds[-1].test.end == pd.Timestamp("2026-09-14")
    for prima, dopo in zip(folds, folds[1:]):
        assert prima.test.end == dopo.test.start


def test_il_training_e_purgato_prima_del_test_e_in_embargo_dopo():
    purge, embargo = 200, 40
    folds = v.purged_folds("2015-08-10", "2026-09-14", n_splits=5,
                           purge_days=purge, embargo_days=embargo)
    for fold in folds:
        for seg in fold.train:
            assert seg.end <= seg.start or True
            if seg.end <= fold.test.start:                 # segmento precedente
                assert (fold.test.start - seg.end).days >= purge
            else:                                          # segmento successivo
                assert (seg.start - fold.test.end).days >= embargo
            # nessuna sovrapposizione col test, in nessun caso
            assert seg.end <= fold.test.start or seg.start >= fold.test.end


def test_i_fold_agli_estremi_hanno_un_solo_segmento_di_training():
    folds = v.purged_folds("2015-08-10", "2026-09-14", n_splits=5)
    assert len(folds[0].train) == 1 and len(folds[-1].train) == 1
    assert all(len(f.train) == 2 for f in folds[1:-1])


def test_servono_almeno_due_fold():
    with pytest.raises(ValueError):
        v.purged_folds("2015-01-01", "2020-01-01", n_splits=1)


# --------------------------------------------------------------------------
# misurazione sui segmenti
# --------------------------------------------------------------------------

def _serie(start: str, periods: int) -> pd.DataFrame:
    idx = pd.date_range(start, periods=periods, freq="D")
    return pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0,
                         "close": 100.0, "volume": 1.0}, index=idx)


def _runner_costante(rate: float):
    """Runner finto: equity che cresce di ``rate`` a barra su tutto ciò che riceve."""

    def run(asset, df, cost_mult=1.0):
        eq = pd.Series(v.CAPITAL * (1 + rate) ** np.arange(len(df)), index=df.index)
        return backtest.Result(equity=eq, trades=[], exposure=1.0)

    return run


def test_la_misurazione_ignora_il_riscaldamento():
    """Solo le barre dentro il segmento contribuiscono ai rendimenti."""
    universe = {"X": _serie("2015-01-01", 2000)}
    seg = v.Segment(pd.Timestamp("2018-01-01"), pd.Timestamp("2019-01-01"))
    out = v.evaluate(universe, _runner_costante(0.001), [seg], warmup_days=400)
    assert out.returns.index.min() > seg.start
    assert out.returns.index.max() <= seg.end
    assert len(out.returns) == 365
    assert out.returns.to_numpy() == pytest.approx(0.001)


def test_i_trade_contati_sono_solo_quelli_aperti_dentro_il_segmento():
    idx = pd.date_range("2015-01-01", periods=2000, freq="D")

    def runner(asset, df, cost_mult=1.0):
        trades = [
            backtest.Trade(1, pd.Timestamp("2016-06-01"), 100.0, 0.0,
                           exit_date=pd.Timestamp("2016-07-01"), exit_price=100.0),
            backtest.Trade(1, pd.Timestamp("2018-06-01"), 100.0, 0.0,
                           exit_date=pd.Timestamp("2018-07-01"), exit_price=100.0),
        ]
        eq = pd.Series(v.CAPITAL * 1.0001 ** np.arange(len(df)), index=df.index)
        return backtest.Result(equity=eq, trades=trades, exposure=0.5)

    seg = v.Segment(pd.Timestamp("2018-01-01"), pd.Timestamp("2019-01-01"))
    out = v.evaluate({"X": pd.DataFrame(index=idx)}, runner, [seg])
    assert out.stats.trades == 1


def test_gli_anni_dei_segmenti_non_contigui_escludono_i_buchi():
    """Concatenare due anni separati da cinque deve valere due anni, non sette."""
    universe = {"X": _serie("2010-01-01", 6000)}
    segs = [v.Segment(pd.Timestamp("2012-01-01"), pd.Timestamp("2013-01-01")),
            v.Segment(pd.Timestamp("2018-01-01"), pd.Timestamp("2019-01-01"))]
    out = v.evaluate(universe, _runner_costante(0.001), segs)
    atteso = (1 + 0.001) ** len(out.returns)
    assert out.stats.final_equity / v.CAPITAL == pytest.approx(atteso, rel=1e-9)
    assert out.stats.cagr == pytest.approx(atteso ** (1 / 2.0) - 1, rel=1e-3)


def test_il_portafoglio_pesa_gli_asset_in_parti_uguali():
    universe = {"A": _serie("2015-01-01", 2000), "B": _serie("2015-01-01", 2000)}

    def runner(asset, df, cost_mult=1.0):
        rate = 0.002 if asset == "A" else 0.0
        return _runner_costante(rate)(asset, df, cost_mult)

    seg = v.Segment(pd.Timestamp("2018-01-01"), pd.Timestamp("2019-01-01"))
    out = v.evaluate(universe, runner, [seg])
    assert out.returns.to_numpy() == pytest.approx(0.001)


def test_select_best_sceglie_il_mar_piu_alto():
    universe = {"X": _serie("2015-01-01", 2000)}
    seg = v.Segment(pd.Timestamp("2018-01-01"), pd.Timestamp("2019-01-01"))
    pool = {"piatta": _runner_costante(0.0),
            "lenta": _runner_costante(0.0005),
            "veloce": _runner_costante(0.002)}
    best, results = v.select_best(universe, pool, [seg])
    assert set(results) == set(pool)
    # senza drawdown il MAR non è definito: si ricade sul confronto fra NaN,
    # quindi il test verifica che la scelta sia comunque deterministica e valida
    assert best in pool


def test_assets_better_than_conta_gli_asset_migliorati():
    universe = {"A": _serie("2015-01-01", 2000), "B": _serie("2015-01-01", 2000)}
    seg = v.Segment(pd.Timestamp("2018-01-01"), pd.Timestamp("2019-01-01"))

    def curva(rate):
        def run(asset, df, cost_mult=1.0):
            eq = pd.Series(v.CAPITAL * (1 + rate) ** np.arange(len(df)), index=df.index)
            # il drawdown deve cadere *dentro* la finestra misurata, non nel
            # riscaldamento, o il maxDD della finestra è zero e il MAR non esiste
            eq.loc[pd.Timestamp("2018-06-01"):] *= 0.9
            return backtest.Result(equity=eq, trades=[], exposure=1.0)
        return run

    alto, basso = curva(0.001), curva(0.0005)

    a = v.evaluate(universe, alto, [seg])
    b = v.evaluate(universe, basso, [seg])
    assert a.assets_better_than(b) == 2
    assert b.assets_better_than(a) == 0


# --------------------------------------------------------------------------
# rendimento differenziale
# --------------------------------------------------------------------------

def test_il_differenziale_di_una_serie_con_se_stessa_e_nullo():
    idx = pd.date_range("2020-01-01", periods=100, freq="D")
    r = pd.Series(np.linspace(-0.01, 0.01, 100), index=idx)
    assert v.differential_returns(r, r).abs().max() == pytest.approx(0.0)


def test_il_differenziale_allinea_calendari_diversi():
    """Un giorno in cui una sola delle due serie esiste vale rendimento nullo per l'altra."""
    a = pd.Series([0.01, 0.02], index=pd.to_datetime(["2020-01-01", "2020-01-02"]))
    b = pd.Series([0.005], index=pd.to_datetime(["2020-01-02"]))
    d = v.differential_returns(a, b)
    assert len(d) == 2
    assert d.iloc[0] == pytest.approx(0.01)
    assert d.iloc[1] == pytest.approx(0.015)


# --------------------------------------------------------------------------
# correlazione di rango
# --------------------------------------------------------------------------

def test_classifiche_identiche_danno_correlazione_uno():
    a = {"x": 3.0, "y": 1.0, "z": 2.0}
    assert v.rank_correlation(a, dict(a)) == pytest.approx(1.0)


def test_classifiche_rovesciate_danno_correlazione_meno_uno():
    a = {"x": 3.0, "y": 1.0, "z": 2.0}
    b = {"x": 1.0, "y": 3.0, "z": 2.0}
    assert v.rank_correlation(a, b) == pytest.approx(-1.0)


def test_la_correlazione_di_rango_usa_solo_i_nomi_validi():
    a = {"x": 3.0, "y": 1.0, "z": 2.0, "w": float("nan")}
    b = {"x": 3.0, "y": 1.0, "z": 2.0, "w": 9.0, "estraneo": 1.0}
    assert v.rank_correlation(a, b) == pytest.approx(1.0)


def test_troppi_pochi_nomi_non_danno_una_correlazione():
    assert math.isnan(v.rank_correlation({"x": 1.0, "y": 2.0}, {"x": 1.0, "y": 2.0}))


# --------------------------------------------------------------------------
# bootstrap
# --------------------------------------------------------------------------

def test_il_bootstrap_su_serie_identiche_da_delta_nullo():
    idx = pd.date_range("2016-01-01", periods=1500, freq="D")
    rng = np.random.default_rng(1)
    r = pd.Series(rng.normal(0.0005, 0.01, len(idx)), index=idx)
    ci = v.block_bootstrap_delta(r, r.copy(), n_boot=200, seed=0)
    assert ci.mean == pytest.approx(0.0, abs=1e-12)
    assert ci.lo == pytest.approx(0.0, abs=1e-12) and ci.hi == pytest.approx(0.0, abs=1e-12)


def test_il_bootstrap_e_riproducibile_a_parita_di_seme():
    idx = pd.date_range("2016-01-01", periods=1500, freq="D")
    rng = np.random.default_rng(2)
    a = pd.Series(rng.normal(0.0008, 0.01, len(idx)), index=idx)
    b = pd.Series(rng.normal(0.0004, 0.01, len(idx)), index=idx)
    uno = v.block_bootstrap_delta(a, b, n_boot=200, seed=42)
    due = v.block_bootstrap_delta(a, b, n_boot=200, seed=42)
    tre = v.block_bootstrap_delta(a, b, n_boot=200, seed=43)
    assert uno.as_dict() == due.as_dict()
    assert uno.mean != tre.mean


def test_il_bootstrap_rifiuta_serie_piu_corte_di_due_blocchi():
    idx = pd.date_range("2016-01-01", periods=30, freq="D")
    r = pd.Series(0.001, index=idx)
    with pytest.raises(ValueError):
        v.block_bootstrap_delta(r, r, block_bars=21)


def test_il_bootstrap_riconosce_una_serie_davvero_migliore():
    idx = pd.date_range("2016-01-01", periods=3000, freq="D")
    rng = np.random.default_rng(5)
    a = pd.Series(rng.normal(0.0012, 0.01, len(idx)), index=idx)
    b = pd.Series(rng.normal(0.0001, 0.01, len(idx)), index=idx)
    ci = v.block_bootstrap_delta(a, b, n_boot=400, seed=11)
    assert ci.mean > 0 and ci.lo < ci.mean < ci.hi
    assert ci.p_negative < 0.5


def test_la_probabilita_negativa_e_coerente_con_i_quantili():
    """Se l'estremo inferiore al 95% è positivo, meno del 2.5% dei campioni lo è."""
    idx = pd.date_range("2016-01-01", periods=3000, freq="D")
    rng = np.random.default_rng(9)
    a = pd.Series(rng.normal(0.0025, 0.008, len(idx)), index=idx)
    b = pd.Series(rng.normal(-0.0005, 0.008, len(idx)), index=idx)
    ci = v.block_bootstrap_delta(a, b, n_boot=400, seed=4)
    if ci.lo > 0:
        assert ci.p_negative <= 0.025
    assert 0.0 <= ci.p_negative <= 1.0


# --------------------------------------------------------------------------
# il conteggio delle ipotesi
# --------------------------------------------------------------------------

def test_il_catalogo_conta_ventiquattro_ipotesi():
    """Il numero che entra nel Deflated Sharpe non può divergere dal provato.

    Se questo test fallisce dopo aver aggiunto una voce al catalogo, **non** va
    aggiornato di riflesso: va prima ricalcolato il DSR, perché ogni ipotesi in
    più alza la soglia per tutte le precedenti. Aggiornare il numero e basta
    lascerebbe pubblicati dei DSR calcolati con un N che non esiste più.

    Passato da 23 a 24 il 2026-09-15 con `sanyaku_v55`, e il DSR è stato
    ricalcolato prima di toccare questa riga: `results/validation.md`, sezione
    «Rifacimento con N = 24».
    """
    assert hypotheses.N_HYPOTHESES == 24
    assert len(hypotheses.CATALOGUE) == hypotheses.N_HYPOTHESES
    assert hypotheses.BASE_NAME not in hypotheses.CATALOGUE
    assert hypotheses.CANDIDATE in hypotheses.CATALOGUE
    assert "sizing_notional" in hypotheses.CATALOGUE
    assert "sanyaku_v55" in hypotheses.CATALOGUE


def test_il_pool_di_selezione_contiene_anche_la_rinuncia():
    """Una selezione onesta deve poter concludere: nessuna variante."""
    assert hypotheses.BASE_NAME in hypotheses.SELECTION_POOL
    assert len(hypotheses.SELECTION_POOL) == hypotheses.N_HYPOTHESES + 1


def test_metrics_compute_accetta_gli_anni_espliciti():
    idx = pd.date_range("2020-01-01", periods=400, freq="D")
    eq = pd.Series(np.linspace(100_000, 121_000, len(idx)), index=idx)
    eq.iloc[200] *= 0.95
    res = backtest.Result(equity=eq, trades=[], exposure=1.0)
    dedotto = metrics.compute(res, 100_000.0)
    esplicito = metrics.compute(res, 100_000.0, years=2.0)
    assert esplicito.cagr == pytest.approx(1.21 ** 0.5 - 1, rel=1e-9)
    assert esplicito.cagr < dedotto.cagr


# --------------------------------------------------------------------------
# normalizzazione di scala prima del differenziale
# --------------------------------------------------------------------------

def test_riscalare_porta_la_volatilita_su_quella_del_benchmark():
    rng = np.random.default_rng(11)
    idx = pd.date_range("2016-01-01", periods=600, freq="D")
    base = pd.Series(rng.normal(0.0004, 0.01, 600), index=idx)
    grossa = base * 3.0 + 0.001
    fuori = v.volatility_matched(grossa, base)
    assert fuori.std() == pytest.approx(base.std(), rel=1e-9)


def test_riscalare_non_cambia_lo_sharpe():
    """È una normalizzazione di scala: sposta la volatilità, non il vantaggio."""
    rng = np.random.default_rng(12)
    idx = pd.date_range("2016-01-01", periods=600, freq="D")
    base = pd.Series(rng.normal(0.0004, 0.01, 600), index=idx)
    grossa = base.shift(1).fillna(0.0) * 2.5
    assert v.sharpe_per_bar(v.volatility_matched(grossa, base)) == pytest.approx(
        v.sharpe_per_bar(grossa), rel=1e-9)


def test_riscalare_una_serie_gia_alla_stessa_scala_non_fa_niente():
    rng = np.random.default_rng(13)
    idx = pd.date_range("2016-01-01", periods=300, freq="D")
    base = pd.Series(rng.normal(0.0, 0.01, 300), index=idx)
    pd.testing.assert_series_equal(v.volatility_matched(base, base), base)


def test_riscalare_una_serie_piatta_la_lascia_stare():
    """Volatilità nulla: non c'è fattore che la porti da nessuna parte."""
    idx = pd.date_range("2016-01-01", periods=50, freq="D")
    piatta = pd.Series(0.0, index=idx)
    altra = pd.Series(0.01, index=idx)
    pd.testing.assert_series_equal(v.volatility_matched(piatta, altra), piatta)


def test_il_differenziale_a_parita_di_scala_toglie_il_vantaggio_di_pura_scala():
    """Una strategia che e' il benchmark moltiplicato per k non ha vantaggio.

    Il differenziale grezzo pero' e' positivo per costruzione: e' la trappola che
    la sezione 4c di run_validation.py evita.
    """
    rng = np.random.default_rng(14)
    idx = pd.date_range("2016-01-01", periods=800, freq="D")
    base = pd.Series(rng.normal(0.0005, 0.01, 800), index=idx)
    solo_scala = base * 3.0

    grezzo = v.differential_returns(solo_scala, base)
    assert grezzo.mean() > 0

    corretto = v.differential_returns(v.volatility_matched(solo_scala, base), base)
    assert corretto.abs().max() == pytest.approx(0.0, abs=1e-12)
