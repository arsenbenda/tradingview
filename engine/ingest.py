"""Aggiornamento delle serie: aggiungere barre nuove senza riscrivere le vecchie.

Il registro forward vale solo se le righe di ieri restano quelle di ieri, e una
riga dipende da tutta la serie che l'ha prodotta: se un fornitore rettifica in
silenzio una barra del 2021, la decisione di ieri non è più riproducibile e il
registro smette di essere una prova. Il controllo sta qui, all'ingresso, perché è
l'ultimo punto in cui si può ancora rifiutare.

La parte fragile di un aggiornamento quotidiano non è scaricare — è **decidere
cosa fare quando i nuovi dati contraddicono i vecchi**. Tre regole:

1. **Le barre nuove si aggiungono, le vecchie non si toccano.** Una data già
   presente viene confrontata, non sovrascritta.
2. **Una rettifica minuscola si accetta e si registra**, perché è arrotondamento:
   le fonti ripubblicano gli stessi prezzi con decimali diversi, e fermare
   l'aggiornamento per 0.001% renderebbe il gate inutile a forza di falsi
   allarmi.
3. **Una rettifica vera si rifiuta.** Non perché il nuovo dato sia sbagliato —
   può darsi che sia quello giusto — ma perché accettarlo in silenzio cambia
   retroattivamente decisioni già registrate. Va guardato da una persona.
4. **La barra di oggi non si ingerisce.** Una sessione ancora aperta ha prezzi e
   volume provvisori: Twelve Data restituisce SPY del 2026-09-15 con 1.179.586 di
   volume contro i 43.944.500 del giorno prima, cioè il 2,7% — una giornata a
   metà. Scriverla significherebbe registrare una decisione su una barra che
   domani sarà diversa, e domani quella differenza verrebbe letta come una
   rettifica del passato: un allarme su un dato che nessuno aveva rettificato.

Le stesse soglie di `scripts/extract_av_result.py`, che risolve questo problema
per i duplicati dentro una singola risposta: qui è lo stesso problema fra due
scaricamenti successivi.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

import pandas as pd

COLONNE = ["open", "high", "low", "close", "volume"]

#: Divergenza relativa massima su un prezzo perché due righe con la stessa data
#: siano "la stessa barra arrotondata in due modi". Uguale alla tolleranza di
#: `extract_av_result.py`: lo stesso giudizio non può avere due soglie.
TOLLERANZA_RETTIFICA = 0.005


class BarraNonChiusa(RuntimeError):
    """Si è tentato di ingerire una barra ancora in formazione."""


class StoriaRiscritta(RuntimeError):
    """Il fornitore ha cambiato una barra già in archivio, oltre la tolleranza."""


@dataclass
class Esito:
    asset: str
    aggiunte: int = 0
    invariate: int = 0
    scartate_non_chiuse: list[str] = field(default_factory=list)
    rettifiche_tollerate: list[str] = field(default_factory=list)
    prima_nuova: str | None = None
    ultima_nuova: str | None = None

    def __str__(self) -> str:
        coda = ""
        if self.prima_nuova:
            coda = f" ({self.prima_nuova} → {self.ultima_nuova})"
        r = f", {len(self.rettifiche_tollerate)} rettifiche di arrotondamento" \
            if self.rettifiche_tollerate else ""
        nc = f", scartate {len(self.scartate_non_chiuse)} non chiuse" \
            if self.scartate_non_chiuse else ""
        return f"{self.asset}: +{self.aggiunte} barre{coda}{r}{nc}"


def normalizza(df: pd.DataFrame) -> pd.DataFrame:
    """Header canonico, indice di date crescente, una riga per data."""
    d = df.copy()
    d.columns = [c.strip().lower() for c in d.columns]
    if "date" in d.columns:
        d = d.set_index("date")
    d.index = pd.to_datetime(d.index).normalize()
    d.index.name = "date"
    mancanti = [c for c in COLONNE if c not in d.columns]
    if mancanti:
        raise ValueError(f"colonne mancanti: {', '.join(mancanti)}")
    return d[COLONNE].astype(float).sort_index()


def _confronta(vecchia: pd.Series, nuova: pd.Series) -> float:
    """Divergenza relativa massima fra due barre, sui soli prezzi.

    Il volume è escluso di proposito: viene ripubblicato e corretto molto più
    dei prezzi, non entra in nessun indicatore del progetto, e includerlo
    farebbe scattare il rifiuto su barre i cui prezzi sono identici.
    """
    scarti = []
    for c in ("open", "high", "low", "close"):
        v, n = vecchia[c], nuova[c]
        if v:
            scarti.append(abs(n - v) / abs(v))
    return max(scarti) if scarti else 0.0


def unisci(esistente: pd.DataFrame, fresco: pd.DataFrame, *, asset: str,
           tolleranza: float = TOLLERANZA_RETTIFICA,
           oggi: pd.Timestamp | None = None) -> tuple[pd.DataFrame, Esito]:
    """Fonde le barre fresche in quelle in archivio. Non riscrive mai il passato."""
    vecchio, nuovo = normalizza(esistente), normalizza(fresco)
    esito = Esito(asset=asset)

    # Barre di oggi e oltre: in formazione. Scartarle costa un giorno di ritardo;
    # ingerirle costa la riproducibilita' di ogni decisione presa su di esse.
    limite = pd.Timestamp.now().normalize() if oggi is None else pd.Timestamp(oggi).normalize()
    non_chiuse = nuovo.index[nuovo.index >= limite]
    if len(non_chiuse):
        esito.scartate_non_chiuse = [str(d.date()) for d in non_chiuse]
        nuovo = nuovo.loc[nuovo.index < limite]

    comuni = vecchio.index.intersection(nuovo.index)
    gravi = []
    for d in comuni:
        scarto = _confronta(vecchio.loc[d], nuovo.loc[d])
        if scarto <= 1e-9:
            esito.invariate += 1
        elif scarto <= tolleranza:
            esito.rettifiche_tollerate.append(f"{d.date()} ({scarto:.4%})")
            esito.invariate += 1
        else:
            gravi.append(f"{d.date()}: scarto {scarto:.2%}")

    if gravi:
        raise StoriaRiscritta(
            f"{asset}: il fornitore ha cambiato {len(gravi)} barra/e già in archivio "
            f"oltre il {tolleranza:.1%}:\n  " + "\n  ".join(gravi[:10]) +
            ("\n  ..." if len(gravi) > 10 else "") +
            "\n\nL'aggiornamento è fermo. Non perché il dato nuovo sia sbagliato, ma "
            "perché accettarlo cambierebbe retroattivamente decisioni già registrate "
            "in data/forward/: va guardato da una persona."
        )

    solo_nuove = nuovo.index.difference(vecchio.index)
    esito.aggiunte = len(solo_nuove)
    if esito.aggiunte:
        esito.prima_nuova = str(solo_nuove.min().date())
        esito.ultima_nuova = str(solo_nuove.max().date())

    unito = pd.concat([vecchio, nuovo.loc[solo_nuove]]).sort_index()
    return unito, esito


def scrivi(path: pathlib.Path, df: pd.DataFrame) -> None:
    """Scrive nel formato canonico di `data/raw/`."""
    fuori = df.copy()
    fuori.index.name = "date"
    fuori.to_csv(path, date_format="%Y-%m-%d")


def aggiorna(path: pathlib.Path, fresco: pd.DataFrame, *, asset: str,
             scrivi_su_disco: bool = True) -> Esito:
    """Legge, fonde, riscrive. Solleva invece di sovrascrivere il passato."""
    esistente = pd.read_csv(path)
    unito, esito = unisci(esistente, fresco, asset=asset)
    if scrivi_su_disco and esito.aggiunte:
        scrivi(path, unito)
    return esito
