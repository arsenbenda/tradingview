"""Test delle strategie portate dal Pine.

Il rischio maggiore di un porting è che il regime di timeframe superiore usi la
settimana in corso invece dell'ultima chiusa. È informazione che alla data del
segnale non esiste, e regala alla strategia una capacità predittiva finta.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import pytest

from engine.strategies.sanyaku import SanyakuV55, htf_weekly


@pytest.fixture
def daily() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    n = 400
    close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, n)))
    spread = np.abs(rng.normal(0, 0.01, n)) * close
    df = pd.DataFrame(
        {"open": close, "high": close + spread, "low": close - spread,
         "close": close, "volume": 1.0},
        index=pd.date_range("2022-01-03", periods=n, freq="D"),
    )
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    return df


def test_htf_usa_la_settimana_chiusa_non_quella_in_corso(daily):
    htf = htf_weekly(daily)
    weekly = daily.resample("W").agg({"open": "first", "high": "max", "low": "min",
                                      "close": "last", "volume": "sum"}).dropna()
    # un giorno a metà della terza settimana deve vedere la chiusura della seconda
    giorno = weekly.index[2] - pd.Timedelta(days=3)
    atteso = weekly["close"].iloc[1]
    assert htf.loc[giorno, "htf_close"] == pytest.approx(atteso)
    # e non la chiusura della settimana in cui si trova
    assert htf.loc[giorno, "htf_close"] != pytest.approx(weekly["close"].iloc[2])


@pytest.mark.parametrize("t", [200, 300, 399])
def test_htf_non_cambia_se_il_futuro_sparisce(daily, t):
    piena = htf_weekly(daily)
    tronca = htf_weekly(daily.iloc[: t + 1])
    for col in ("htf_close", "htf_kijun"):
        a, b = piena[col].iloc[t], tronca[col].iloc[t]
        assert (np.isnan(a) and np.isnan(b)) or a == pytest.approx(b), col


def test_sanyaku_non_apre_senza_indicatori_pronti(daily):
    strat = SanyakuV55()
    strat.prepare(daily)
    from engine.backtest import State

    # nelle prime 78 barre Senkou B e la sua proiezione non esistono ancora
    for i in range(0, 70):
        assert strat.entry(State(i=i, cash=100_000.0, equity=100_000.0)) is None


def test_il_cooldown_blocca_e1_ma_non_e4(daily):
    """Entry 4 aggira cooldown e zone lock: e' il default del Pine.

    Il test fissa il comportamento perche' e' rischioso, non perche' sia giusto:
    e' l'unico ingresso che puo' scattare subito dopo un'uscita, ed e' il
    meccanismo con cui in un regime di whipsaw si concatenano le perdite.
    """
    from engine.backtest import State

    idx_kwargs = dict(cash=100_000.0, equity=100_000.0)

    solo_e1 = SanyakuV55(enabled_entries=(1,))
    solo_e1.prepare(daily)
    idx = int(np.flatnonzero(solo_e1.d["e1"] & solo_e1.d["htf_ok"])[0])
    assert solo_e1.entry(State(i=idx, closed_trades=0, **idx_kwargs)) is not None

    solo_e1.prepare(daily)
    bloccato = State(i=idx, closed_trades=1, last_exit_index=idx - 2, **idx_kwargs)
    assert solo_e1.entry(bloccato) is None          # cooldown rispettato

    tutte = SanyakuV55()
    tutte.prepare(daily)
    passa = tutte.entry(State(i=idx, closed_trades=1, last_exit_index=idx - 2, **idx_kwargs))
    assert passa is not None and passa.tag == "E4"   # E4 entra comunque


def test_i_filtri_rispettano_il_contratto(daily):
    """Ogni filtro deve restituire due serie booleane allineate all'indice."""
    from engine import filters

    for nome, fn in filters.CATALOGUE.items():
        allow_long, allow_short = fn(daily)
        assert list(allow_long.index) == list(daily.index), nome
        assert list(allow_short.index) == list(daily.index), nome
        assert allow_long.dtype == bool and allow_short.dtype == bool, nome


def test_la_pendenza_gann_1x1_non_e_raggiungibile(daily):
    """Il prezzo diffonde come radice del tempo, la retta 1x1 cresce come il tempo.

    Normalizzata in ATR per barra, la 1x1 non viene mai attraversata: e' una
    proprieta' della scala, non del mercato. Il test fissa il fatto che rende
    l'angolo inutilizzabile come soglia.
    """
    from engine import filters, indicators as ind

    atr = ind.atr(daily, 14)
    slope = ((daily["close"] - daily["close"].shift(26)) / (26 * atr)).dropna()
    assert slope.abs().max() < 1.0

    allow_long, allow_short = filters.gann_1x1(daily)
    assert not (allow_long | allow_short).any()


def test_la_pausa_dopo_le_perdite_non_e_definitiva():
    """La pausa da perdite consecutive deve scadere, non congelare la strategia.

    Il Pine (righe 133-137) valuta la soglia alla chiusura di un trade e azzera
    il contatore quando arma la pausa. Il porting la valutava a ogni barra senza
    azzerare: raggiunte cinque perdite, ogni barra riarmava ``pause_until``,
    nessun trade poteva aprirsi e quindi il contatore non tornava mai sotto la
    soglia. La strategia restava bloccata fino a fine serie -- dal 67% al 94%
    delle barre a seconda dell'asset, e su CORN dal 2016 in poi.

    Il test fissa il fatto che rende la misura confrontabile con il Pine: dopo
    ``pause_bars`` barre la pausa deve essere finita.
    """
    from engine import backtest, costs, data

    serie = data.load("BTC")
    serie = serie[serie.index >= data.DEFAULT_START]
    strat = SanyakuV55()
    res = backtest.run_strategy(
        serie, strat, costs=costs.for_asset("BTC"),
        risk_pct=0.01, initial_capital=100_000.0, max_notional_pct=0.60,
    )

    # la pausa e' armata al piu' per pause_bars barre oltre l'ultimo trade chiuso
    assert strat.pause_until <= len(serie) - 1 + strat.pause_bars

    # e la strategia resta viva: opera fino in fondo, non si spegne a meta' serie
    ultimo = res.trades[-1].exit_date
    assert (serie.index[-1] - ultimo).days < 400, (
        f"ultimo trade il {ultimo.date()}, serie fino al {serie.index[-1].date()}: "
        "la strategia si e' fermata prima della fine"
    )


# ---------------------------------------------------------------- log forward

def test_il_registro_forward_e_append_only(tmp_path):
    """Una riga già scritta non si riscrive, e riscriverla uguale è un no-op.

    Riscrivere il passato dopo averne visto l'esito è l'unica cosa che questo
    registro esiste per impedire. Se fosse affidato alla buona volontà non
    sarebbe una prova, quindi il codice lo rifiuta.
    """
    from engine import forward

    reg = tmp_path / "decisioni.jsonl"
    d = forward.Decision(data="2026-09-14", asset="BTC", azione="apri", direzione=1,
                         close=100.0, stop=None, quantita=None, tag="L",
                         config="abc", dati="xyz", esecuzione_attesa="apertura successiva")

    assert forward.append(reg, [d]) == 1
    assert forward.append(reg, [d]) == 0          # identica: no-op
    assert len(forward.load(reg)) == 1

    diversa = dataclasses.replace(d, azione="fermo", direzione=0)
    with pytest.raises(forward.RiscritturaRifiutata):
        forward.append(reg, [diversa])
    assert len(forward.load(reg)) == 1            # il rifiuto non sporca il file


def test_il_registro_forward_riproduce_il_passato_giorno_per_giorno(tmp_path):
    """Rieseguire su dati più lunghi deve riprodurre identiche le righe vecchie.

    È la garanzia di assenza di lookahead applicata in avanti: si simula il
    processo quotidiano su una finestra storica, allungando la serie di un
    giorno alla volta. Se una riga già scritta cambiasse, ``append`` lo
    rifiuterebbe — cioè il registro scopre da solo un motore che guarda avanti.
    """
    from engine import costs, data, forward

    serie = data.load("BTC")
    serie = serie[serie.index >= data.DEFAULT_START]
    reg = tmp_path / "decisioni.jsonl"

    for fine in range(len(serie) - 30, len(serie)):
        parziale = serie.iloc[: fine + 1]
        d = forward.decide("BTC", parziale, SanyakuV55(),
                           costs=costs.for_asset("BTC"), risk_pct=0.01,
                           initial_capital=100_000.0, max_notional_pct=0.60)
        forward.append(reg, [d])       # solleva se una riga vecchia cambiasse

    righe = forward.load(reg)
    assert len(righe) == 30
    assert [r["data"] for r in righe] == sorted(r["data"] for r in righe)
    # una sola configurazione per tutte le righe: nessuna ri-ottimizzazione
    assert len({r["config"] for r in righe}) == 1


def test_il_sorvegliante_vede_il_silenzio_e_il_cambio_di_configurazione():
    """I due allarmi che sarebbero serviti a questo progetto.

    Il silenzio è il bug della pausa: la v5.5 aveva smesso di operare su CORN
    nel 2016 e nessuno se n'era accorto. Il cambio di impronta è la regola 6
    resa verificabile invece che promessa.
    """
    from engine import forward

    def riga(data_, azione, config="abc"):
        return {"data": data_, "asset": "BTC", "azione": azione, "direzione": 0,
                "close": 1.0, "stop": None, "quantita": None, "tag": "",
                "config": config, "dati": "x", "esecuzione_attesa": "nessuna"}

    muto = [riga("2026-01-05", "apri")] + [riga(f"2026-0{m}-05", "fermo") for m in range(2, 10)]
    problemi = forward.anomalie(muto, silenzio_massimo_giorni=90)
    assert any("nessuna attività" in p for p in problemi)

    cambiato = [riga("2026-09-01", "apri", "abc"), riga("2026-09-02", "tieni", "DIVERSA")]
    problemi = forward.anomalie(cambiato)
    assert any("configurazione è cambiata" in p for p in problemi)

    sano = [riga("2026-09-13", "apri"), riga("2026-09-14", "tieni")]
    assert not any("nessuna attività" in p or "configurazione" in p
                   for p in forward.anomalie(sano))


def test_la_posizione_aperta_a_fine_serie_non_esce_con_quantita_zero(daily):
    """``Result.open_position`` è una copia, non un riferimento.

    A fine serie il motore chiude d'ufficio la posizione: giusto in backtest,
    dove serve a misurare, sbagliato in avanti, dove la posizione è davvero
    ancora aperta. Se si restituisse il riferimento, quella chiusura lo
    muterebbe subito dopo e una posizione viva uscirebbe con quantità zero —
    cioè il log forward registrerebbe «tieni» di niente.
    """
    from engine import backtest, costs
    from engine.strategies import donchian

    res = backtest.run_strategy(daily, donchian.DonchianWithExit(exit_mode="canale"),
                                costs=costs.for_asset("BTC"), risk_pct=0.01,
                                initial_capital=100_000.0)
    if res.open_position is not None:
        assert res.open_position.qty > 0
        assert res.open_position.exit_date is None


# ------------------------------------------------------------ coda proposte

def test_una_proposta_non_puo_applicarsi_da_sola(tmp_path):
    """Non esiste una funzione che accetti e modifichi: sono due gesti.

    È il vincolo centrale della coda. Un sorvegliante che aggiusta i parametri
    viola la regola 6, rende non validabile ciò che esegue e sbaglia il
    tempismo — taglia l'esposizione dopo la perdita. Qui la diagnosi può
    diventare modifica solo passando da una decisione umana.
    """
    from engine import proposals

    assert not hasattr(proposals, "applica")
    firme = [n for n in dir(proposals) if not n.startswith("_")]
    assert "accetta" in firme and "respingi" in firme


def test_accettare_richiede_di_nominare_l_ipotesi(tmp_path):
    """Regola 4: una modifica accettata e non catalogata falsa il DSR di tutte."""
    from engine import proposals

    coda = tmp_path / "proposte.jsonl"
    p = proposals.Proposta(id="abc123", creata_il="2026-09-15", origine="sorvegliante",
                           innesco="CORN: nessuna attività da 400 giorni",
                           bersaglio="engine/strategies/sanyaku.py",
                           modifica="alzare min_stop_atr su CORN", motivo="stop troppo stretto")
    assert proposals.proponi(coda, p) is True
    assert proposals.proponi(coda, p) is False          # ripetuta: no-op

    with pytest.raises(proposals.ProposteIncoerenti):
        proposals.accetta(coda, "abc123", da="arsen", quando="2026-09-16", ipotesi="")

    assert proposals.stato(coda)["abc123"]["stato"] == "aperta"
    proposals.accetta(coda, "abc123", da="arsen", quando="2026-09-16",
                      ipotesi="stop_floor_per_categoria")
    assert proposals.stato(coda)["abc123"]["stato"] == "accettata"
    assert proposals.stato(coda)["abc123"]["decisione"]["ipotesi"] == "stop_floor_per_categoria"


def test_una_decisione_presa_non_si_sovrascrive(tmp_path):
    """Lo storico è append-only: ripensarci apre una proposta nuova."""
    from engine import proposals

    coda = tmp_path / "proposte.jsonl"
    p = proposals.Proposta(id="x1", creata_il="2026-09-15", origine="sorvegliante",
                           innesco="i", bersaglio="b", modifica="m", motivo="r")
    proposals.proponi(coda, p)
    proposals.respingi(coda, "x1", da="arsen", quando="2026-09-16", motivo="già escluso")

    with pytest.raises(proposals.ProposteIncoerenti):
        proposals.accetta(coda, "x1", da="arsen", quando="2026-09-17", ipotesi="qualcosa")
    with pytest.raises(proposals.ProposteIncoerenti):
        proposals.respingi(coda, "ignoto", da="arsen", quando="2026-09-17", motivo="x")

    assert proposals.stato(coda)["x1"]["stato"] == "respinta"
    assert proposals.aperte(coda) == []


def test_le_proposte_dalle_anomalie_nascono_vuote(tmp_path):
    """Il sorvegliante sa dire che qualcosa non torna, non cosa cambiare.

    Un testo generato che *sembra* una diagnosi è peggio di un campo in bianco,
    perché invita ad accettarlo senza guardarci.
    """
    from engine import proposals

    proposte = proposals.da_anomalie(["CORN: nessuna attività da 400 giorni (dal 2016-05-04)."],
                                     quando="2026-09-15")
    assert len(proposte) == 1
    assert proposte[0].modifica == "(da compilare)"
    assert proposte[0].motivo == "(da compilare)"
    assert "CORN" in proposte[0].innesco
