"""L'aggiornamento delle serie non deve poter riscrivere il passato."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine import ingest


def serie(date, base=100.0):
    idx = pd.to_datetime(date)
    n = len(idx)
    return pd.DataFrame({
        "open": np.linspace(base, base + n, n),
        "high": np.linspace(base + 1, base + n + 1, n),
        "low": np.linspace(base - 1, base + n - 1, n),
        "close": np.linspace(base, base + n, n),
        "volume": np.full(n, 1000.0),
    }, index=idx).rename_axis("date")


def test_aggiunge_solo_le_barre_nuove():
    vecchia = serie(["2026-09-10", "2026-09-11", "2026-09-12"])
    # il fornitore rimanda anche le vecchie, come fanno tutti
    fresca = pd.concat([vecchia, serie(["2026-09-13", "2026-09-14"], base=103.0)])

    unito, esito = ingest.unisci(vecchia, fresca, asset="BTC")
    assert esito.aggiunte == 2
    assert esito.invariate == 3
    assert esito.prima_nuova == "2026-09-13" and esito.ultima_nuova == "2026-09-14"
    assert len(unito) == 5
    assert list(unito.index) == sorted(unito.index)

    # le righe vecchie sono uscite identiche
    pd.testing.assert_frame_equal(unito.loc[vecchia.index], ingest.normalizza(vecchia),
                                  check_freq=False)

    # rifarlo non aggiunge niente
    _, di_nuovo = ingest.unisci(unito, fresca, asset="BTC")
    assert di_nuovo.aggiunte == 0


def test_una_rettifica_vera_del_passato_ferma_tutto():
    """Il caso che il registro forward non può sopportare.

    Una decisione registrata dipende da tutta la serie che l'ha prodotta. Se una
    barra del passato cambia in silenzio, quella decisione non è più
    riproducibile: il registro smette di essere una prova. Accettare il dato
    nuovo può anche essere giusto, ma non di nascosto.
    """
    vecchia = serie(["2026-09-10", "2026-09-11", "2026-09-12"])
    fresca = vecchia.copy()
    fresca.loc[pd.Timestamp("2026-09-11"), "close"] *= 1.03      # 3%, ben oltre la soglia

    with pytest.raises(ingest.StoriaRiscritta) as e:
        ingest.unisci(vecchia, fresca, asset="GOLD")
    assert "2026-09-11" in str(e.value)
    assert "GOLD" in str(e.value)


def test_una_rettifica_di_arrotondamento_passa_ed_e_registrata():
    """Fermarsi per 0.001% renderebbe il gate inutile a forza di falsi allarmi."""
    vecchia = serie(["2026-09-10", "2026-09-11"])
    fresca = vecchia.copy()
    fresca.loc[pd.Timestamp("2026-09-11"), "close"] *= 1.0002    # 0.02%

    unito, esito = ingest.unisci(vecchia, fresca, asset="ETH")
    assert len(esito.rettifiche_tollerate) == 1
    assert "2026-09-11" in esito.rettifiche_tollerate[0]
    # e la barra in archivio resta quella vecchia: tollerare non vuol dire adottare
    assert unito.loc[pd.Timestamp("2026-09-11"), "close"] == vecchia.loc[pd.Timestamp("2026-09-11"), "close"]


def test_il_volume_non_fa_scattare_il_rifiuto():
    """Viene ripubblicato e corretto molto più dei prezzi, e non entra in nessun
    indicatore del progetto: includerlo bloccherebbe barre con prezzi identici."""
    vecchia = serie(["2026-09-10", "2026-09-11"])
    fresca = vecchia.copy()
    fresca["volume"] *= 3.0

    _, esito = ingest.unisci(vecchia, fresca, asset="CORN")
    assert esito.rettifiche_tollerate == []
    assert esito.invariate == 2


def test_le_colonne_mancanti_sono_un_errore_non_un_nan():
    with pytest.raises(ValueError, match="colonne mancanti"):
        ingest.normalizza(pd.DataFrame({"close": [1.0]}, index=pd.to_datetime(["2026-09-10"])))


def test_la_barra_di_oggi_non_viene_ingerita():
    """Una sessione aperta ha prezzi e volume provvisori.

    Verificato sul campo: Twelve Data restituisce SPY del 2026-09-15 con
    1.179.586 di volume contro i 43.944.500 del giorno prima — il 2,7%, cioe'
    una sessione a meta'. Scriverla significherebbe registrare una decisione su
    una barra che domani sara' diversa, e domani quella differenza verrebbe
    letta come una rettifica del passato: un allarme su un dato che nessuno
    aveva rettificato.
    """
    vecchia = serie(["2026-09-12", "2026-09-13"])
    fresca = pd.concat([vecchia, serie(["2026-09-14", "2026-09-15"], base=110.0)])

    unito, esito = ingest.unisci(vecchia, fresca, asset="EQUITY",
                                 oggi=pd.Timestamp("2026-09-15"))
    assert esito.aggiunte == 1                       # solo il 14
    assert esito.scartate_non_chiuse == ["2026-09-15"]
    assert pd.Timestamp("2026-09-15") not in unito.index
    assert pd.Timestamp("2026-09-14") in unito.index

    # e il giorno dopo quella barra entra, senza essere scambiata per rettifica
    unito2, esito2 = ingest.unisci(unito, fresca, asset="EQUITY",
                                   oggi=pd.Timestamp("2026-09-16"))
    assert esito2.aggiunte == 1
    assert esito2.scartate_non_chiuse == []
    assert pd.Timestamp("2026-09-15") in unito2.index


def test_il_registro_si_rifiuta_di_scrivere_serie_disallineate():
    """Un aggiornamento parziale non deve poter entrare nel registro.

    E' l'incidente tipico di un giro manuale: una chiamata al connector
    fallisce e un asset resta indietro. Le righe resterebbero valide una per
    una, ma il registro no — confrontare una decisione su dati di lunedi' con
    una su dati di giovedi' non vuol dire niente, e nulla nel file direbbe che
    e' successo.
    """
    from engine import forward

    def s(fino):
        idx = pd.date_range("2026-09-01", fino, freq="D")
        return pd.DataFrame({c: np.ones(len(idx)) for c in ingest.COLONNE}, index=idx)

    allineate = {"BTC": s("2026-09-14"), "GOLD": s("2026-09-14")}
    forward.verifica_allineamento(allineate)          # non solleva
    assert set(forward.allineamento(allineate).values()) == {"2026-09-14"}

    storte = {"BTC": s("2026-09-14"), "GOLD": s("2026-09-09")}
    with pytest.raises(forward.SerieDisallineate) as e:
        forward.verifica_allineamento(storte)
    assert "GOLD" in str(e.value) and "2026-09-09" in str(e.value)
