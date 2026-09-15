"""Registro forward: cosa la strategia ha deciso, prima di sapere com'è andata.

Undici anni di dati e ventiquattro ipotesi non contengono più l'informazione per
distinguere un vantaggio di 0.28 di Sharpe da zero, e *nessun* holdout ritagliato
da questo campione è pulito — è stato guardato tutto, più volte. L'unico
out-of-sample vero è il tempo che passa.

Questo modulo lo trasforma da attesa passiva in un archivio che si accumula. Ogni
giorno registra **la decisione e i suoi ingressi**, non l'esito: il segnale
deciso alla chiusura di oggi, lo stop, la quantità, e l'impronta della
configurazione che l'ha prodotto. L'esito arriva dopo, e non può essere
retrodatato.

Tre proprietà lo rendono una prova invece che un diario.

**Append-only.** Una data già scritta non si riscrive. Riscrivere il passato dopo
averne visto l'esito è esattamente ciò che questo file esiste per impedire, e il
codice lo rifiuta invece di affidarlo alla buona volontà.

**Riproducibile all'indietro.** Rieseguire domani su dati più lunghi deve
riprodurre *identiche* le righe di ieri. È la garanzia di assenza di lookahead
già coperta dai test, applicata in avanti: se una riga vecchia cambia, il motore
sta guardando il futuro, e il log lo scopre da solo.

**Firmata.** Ogni riga porta l'impronta della configurazione. La regola 6 dice di
non ri-ottimizzare i parametri; qui smette di essere una promessa e diventa una
cosa verificabile: se l'impronta cambia fra due righe, qualcuno ha cambiato i
parametri, e si vede.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import pathlib
from dataclasses import dataclass
from typing import Any

import pandas as pd

from . import backtest


def _jsonable(x: Any) -> Any:
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in sorted(x.items())}
    return str(x)


def config_fingerprint(strategy: backtest.Strategy, **esecuzione: Any) -> str:
    """Impronta stabile di *cosa* ha deciso: strategia, parametri, esecuzione.

    Include tutto ciò che può cambiare una decisione senza cambiare i dati. Due
    righe con impronte diverse non sono confrontabili fra loro, ed è il punto:
    la validazione vale per una configurazione, non per un nome.
    """
    # Solo i parametri del **costruttore**: `vars()` conterrebbe anche lo stato
    # che `prepare()` e il ciclo del backtest scrivono sull'oggetto (la posizione
    # in corso, il contatore delle perdite, la zona bloccata), che cambia a ogni
    # esecuzione. Un'impronta che includesse quello cambierebbe ogni giorno e
    # segnalerebbe una ri-ottimizzazione che non c'è stata — rendendo l'allarme
    # inutile proprio perché suona sempre. Leggerla dalla firma di `__init__` la
    # tiene allineata da sola quando si aggiunge un parametro.
    firma = inspect.signature(type(strategy).__init__).parameters
    nomi = [n for n in firma if n != "self"]
    corpo = {
        "strategia": type(strategy).__name__,
        "parametri": _jsonable({n: getattr(strategy, n) for n in nomi
                                if hasattr(strategy, n)}),
        "esecuzione": _jsonable(esecuzione),
    }
    testo = json.dumps(corpo, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(testo.encode()).hexdigest()[:16]


def data_fingerprint(df: pd.DataFrame) -> str:
    """Impronta delle barre usate. Se la storia viene riscritta, si vede."""
    ultime = df.tail(200)
    testo = ultime.to_csv(float_format="%.8f")
    return hashlib.sha256(testo.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Decision:
    """Una riga del registro: un asset, un giorno, una decisione."""

    data: str               # la barra alla cui chiusura si decide
    asset: str
    azione: str             # "apri" | "chiudi" | "tieni" | "fermo"
    direzione: int          # +1 long, -1 short, 0 nessuna posizione
    close: float            # chiusura della barra di decisione
    stop: float | None      # livello di stop, se c'è una posizione o un'apertura
    quantita: float | None
    tag: str                # quale meccanismo ha deciso (E1..E5, canale, ...)
    config: str             # impronta della configurazione
    dati: str               # impronta delle barre
    esecuzione_attesa: str  # quando si esegue: "apertura successiva"

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def decide(asset: str, df: pd.DataFrame, strategy: backtest.Strategy,
           **esecuzione: Any) -> Decision:
    """Cosa fa la strategia alla chiusura dell'**ultima barra** di ``df``.

    Non è una simulazione a parte: è lo stesso motore del backtest, eseguito su
    tutta la storia disponibile, di cui si legge solo l'ultima barra. Deve essere
    così — una seconda implementazione «per il live» è il modo più diretto di
    ritrovarsi a validare una cosa e a eseguirne un'altra.
    """
    res = backtest.run_strategy(df, strategy, **esecuzione)
    ultima = df.index[-1]
    cfg = config_fingerprint(strategy, **{k: v for k, v in esecuzione.items()
                                          if k != "costs"} | {"costs": str(esecuzione.get("costs"))})

    if res.pending is not None:
        p = res.pending
        return Decision(data=str(ultima.date()), asset=asset, azione="apri",
                        direzione=p.direction, close=float(df["close"].iloc[-1]),
                        stop=None, quantita=None, tag=p.tag, config=cfg,
                        dati=data_fingerprint(df),
                        esecuzione_attesa="apertura successiva")

    aperta = res.open_position
    if aperta is not None:
        return Decision(data=str(ultima.date()), asset=asset, azione="tieni",
                        direzione=aperta.direction, close=float(df["close"].iloc[-1]),
                        stop=None, quantita=float(aperta.qty), tag=aperta.tag,
                        config=cfg, dati=data_fingerprint(df),
                        esecuzione_attesa="nessuna")

    chiusi_oggi = [t for t in res.trades
                   if t.exit_date is not None and pd.Timestamp(t.exit_date) == ultima
                   and t.exit_reason != "fine serie"]
    if chiusi_oggi:
        t = chiusi_oggi[-1]
        return Decision(data=str(ultima.date()), asset=asset, azione="chiudi",
                        direzione=0, close=float(df["close"].iloc[-1]), stop=None,
                        quantita=None, tag=t.exit_reason, config=cfg,
                        dati=data_fingerprint(df), esecuzione_attesa="nessuna")

    return Decision(data=str(ultima.date()), asset=asset, azione="fermo", direzione=0,
                    close=float(df["close"].iloc[-1]), stop=None, quantita=None,
                    tag="", config=cfg, dati=data_fingerprint(df),
                    esecuzione_attesa="nessuna")


# ---------------------------------------------------------------- persistenza

class RiscritturaRifiutata(RuntimeError):
    """Tentativo di cambiare una riga già scritta. Il registro è append-only."""


def load(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(r) for r in path.read_text().splitlines() if r.strip()]


def append(path: pathlib.Path, decisioni: list[Decision]) -> int:
    """Aggiunge righe nuove. Rifiuta di cambiarne una già scritta.

    Riscrivere una riga identica è un no-op silenzioso: rieseguire lo stesso
    giorno due volte è normale e non deve rompere niente. Riscriverla **diversa**
    è un errore, e va sollevato invece che assorbito: o il motore non è
    deterministico, o i dati storici sono cambiati sotto, e in entrambi i casi il
    registro ha smesso di essere una prova.
    """
    esistenti = {(r["data"], r["asset"]): r for r in load(path)}
    nuove = []
    for d in decisioni:
        chiave = (d.data, d.asset)
        vecchia = esistenti.get(chiave)
        if vecchia is None:
            nuove.append(d)
        elif vecchia != d.as_dict():
            diff = [k for k in d.as_dict() if vecchia.get(k) != d.as_dict()[k]]
            raise RiscritturaRifiutata(
                f"{d.asset} {d.data}: la riga esiste già ed è diversa (campi: {', '.join(diff)}). "
                "Il registro è append-only: o il motore non è deterministico, "
                "o i dati storici sono stati riscritti."
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for d in nuove:
            f.write(json.dumps(d.as_dict(), sort_keys=True) + "\n")
    return len(nuove)


# ---------------------------------------------------------------- sorveglianza

def anomalie(righe: list[dict], *, silenzio_massimo_giorni: int = 90) -> list[str]:
    """Condizioni che meritano un'occhiata umana. Nessuna cambia una decisione.

    Sono di sola lettura per costruzione: dicono *guarda qui*, non *fai questo*.
    Un sorvegliante che aggiusta i parametri quando vede un drawdown viola la
    regola 6 e rende non validabile ciò che esegue; uno che segnala e al massimo
    ferma, no.

    Il primo controllo è quello che sarebbe servito: la v5.5 aveva smesso di
    operare su CORN nel 2016 e su BTC nel 2018, e nessuno se n'era accorto per
    undici anni di backtest, ventiquattro ipotesi e novantotto test.
    """
    out: list[str] = []
    if not righe:
        return out

    df = pd.DataFrame(righe)
    df["data"] = pd.to_datetime(df["data"])
    ultimo_giorno = df["data"].max()

    for asset, g in df.groupby("asset"):
        g = g.sort_values("data")
        attivi = g[g["azione"].isin(["apri", "tieni", "chiudi"])]
        if attivi.empty:
            silenzio = (ultimo_giorno - g["data"].min()).days
            quando = "dall'inizio del registro"
        else:
            silenzio = (ultimo_giorno - attivi["data"].max()).days
            quando = f"dal {attivi['data'].max().date()}"
        if silenzio > silenzio_massimo_giorni:
            out.append(f"{asset}: nessuna attività da {silenzio} giorni ({quando}). "
                       f"Verificare che il silenzio sia una scelta e non un blocco.")

        impronte = g["config"].unique()
        if len(impronte) > 1:
            out.append(f"{asset}: la configurazione è cambiata {len(impronte) - 1} volta/e "
                       f"nel registro. La regola 6 vieta la ri-ottimizzazione periodica: "
                       f"le righe con impronte diverse non sono confrontabili fra loro.")

    scarto = (pd.Timestamp.now().normalize() - ultimo_giorno).days
    if scarto > 5:
        out.append(f"registro fermo da {scarto} giorni (ultima riga {ultimo_giorno.date()}): "
                   f"il processo che lo alimenta potrebbe non girare più.")
    return out
