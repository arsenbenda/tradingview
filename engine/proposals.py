"""Coda delle proposte: dove il sorvegliante può scrivere, e non altrove.

`forward.anomalie()` segnala; non corregge. Questo modulo è il solo canale
attraverso cui una diagnosi può diventare una modifica, e serve a rendere quel
passaggio **lento e visibile** invece che automatico.

La ragione è la regola 6. Un sorvegliante che aggiusta i parametri quando vede un
drawdown ha tre difetti che si sommano: viola quella regola, rende non validabile
ciò che esegue (ogni aggiustamento è un'ipotesi non contata, e il Deflated Sharpe
smette di proteggere da qualcosa), e sbaglia il tempismo nel modo peggiore —
taglia l'esposizione dopo la perdita, cioè spesso subito prima del recupero.

L'asimmetria è il criterio di tutto il file: **fermare fallisce verso il non fare
niente, aggiustare fallisce verso il fare qualcosa che nessuno ha validato.**

Tre vincoli, tutti applicati dal codice e non dalla buona volontà:

1. **Nessuna proposta si applica da sola.** Non esiste una funzione che accetti e
   modifichi. ``accetta()`` scrive un evento; applicare la modifica resta un
   gesto umano, separato e successivo.
2. **Accettare richiede di nominare l'ipotesi.** La regola 4 dice che ogni
   ipotesi provata va contata: qui accettare senza indicare la voce che entrerà
   in ``hypotheses.CATALOGUE`` è un errore, non una svista.
3. **Lo storico non si riscrive.** Il file è un registro di eventi in append: lo
   stato di una proposta si ottiene ripercorrendoli. Una proposta respinta e poi
   riproposta lascia entrambe le tracce, che è il punto — la sequenza delle
   decisioni è il dato più informativo quando si guarda indietro.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
from dataclasses import dataclass, field
from typing import Literal

STATI = ("aperta", "accettata", "respinta")
Stato = Literal["aperta", "accettata", "respinta"]


class ProposteIncoerenti(RuntimeError):
    """Una transizione che il registro non permette."""


@dataclass(frozen=True)
class Proposta:
    """Una modifica suggerita. Non applicata: suggerita."""

    id: str
    creata_il: str
    origine: str          # chi l'ha scritta: "sorvegliante", "arsen", ...
    innesco: str          # l'anomalia che l'ha motivata, verbatim
    bersaglio: str        # cosa toccherebbe: file, funzione, parametro
    modifica: str         # cosa farebbe, in chiaro
    motivo: str           # perché dovrebbe migliorare le cose

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def nuovo_id(creata_il: str, bersaglio: str, modifica: str) -> str:
    grezzo = f"{creata_il}|{bersaglio}|{modifica}"
    return hashlib.sha256(grezzo.encode()).hexdigest()[:12]


def _eventi(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(r) for r in path.read_text().splitlines() if r.strip()]


def _scrivi(path: pathlib.Path, evento: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(evento, sort_keys=True, ensure_ascii=False) + "\n")


def proponi(path: pathlib.Path, p: Proposta) -> bool:
    """Registra una proposta. Ripeterla identica è un no-op.

    Il sorvegliante gira ogni giorno e vedrà la stessa anomalia ogni giorno:
    senza questo, la coda si riempirebbe di copie della stessa cosa e smetterebbe
    di essere leggibile, che è il modo in cui un registro muore.
    """
    if any(e["tipo"] == "creata" and e["proposta"]["id"] == p.id for e in _eventi(path)):
        return False
    _scrivi(path, {"tipo": "creata", "quando": p.creata_il, "proposta": p.as_dict()})
    return True


def accetta(path: pathlib.Path, id_: str, *, da: str, quando: str,
            ipotesi: str, nota: str = "") -> None:
    """Accetta una proposta. **Non applica niente.**

    ``ipotesi`` è il nome della voce che la modifica avrà in
    ``hypotheses.CATALOGUE``. È obbligatorio perché la regola 4 non ammette
    modifiche non contate: una variante accettata e non catalogata è
    esattamente un'ipotesi provata di nascosto, e il Deflated Sharpe di tutte le
    altre diventerebbe una sottostima.
    """
    if not ipotesi.strip():
        raise ProposteIncoerenti(
            "accettare richiede il nome dell'ipotesi che entrerà nel catalogo "
            "(regola 4): una modifica non contata falsa il DSR di tutte le altre."
        )
    _transizione(path, id_, "accettata", da=da, quando=quando,
                 extra={"ipotesi": ipotesi, "nota": nota})


def respingi(path: pathlib.Path, id_: str, *, da: str, quando: str, motivo: str) -> None:
    """Respinge una proposta. Il motivo è obbligatorio.

    Serve a chi guarderà indietro: una coda di rifiuti senza ragioni non permette
    di distinguere «già provato e non funziona» da «non ne ho avuto tempo».
    """
    if not motivo.strip():
        raise ProposteIncoerenti("respingere richiede un motivo scritto")
    _transizione(path, id_, "respinta", da=da, quando=quando, extra={"motivo": motivo})


def _transizione(path: pathlib.Path, id_: str, nuovo: Stato, *, da: str,
                 quando: str, extra: dict) -> None:
    corrente = stato(path)
    if id_ not in corrente:
        raise ProposteIncoerenti(f"proposta {id_} inesistente")
    if corrente[id_]["stato"] != "aperta":
        raise ProposteIncoerenti(
            f"proposta {id_} è già '{corrente[id_]['stato']}': una decisione presa non "
            "si sovrascrive. Per tornarci sopra si apre una proposta nuova, così "
            "resta la traccia di entrambe."
        )
    _scrivi(path, {"tipo": nuovo, "quando": quando, "id": id_, "da": da, **extra})


def stato(path: pathlib.Path) -> dict[str, dict]:
    """Stato corrente di ogni proposta, ricostruito dagli eventi."""
    out: dict[str, dict] = {}
    for e in _eventi(path):
        if e["tipo"] == "creata":
            out[e["proposta"]["id"]] = {"proposta": e["proposta"], "stato": "aperta",
                                        "decisione": None}
        elif e["tipo"] in ("accettata", "respinta") and e["id"] in out:
            out[e["id"]]["stato"] = e["tipo"]
            out[e["id"]]["decisione"] = {k: v for k, v in e.items() if k != "tipo"}
    return out


def aperte(path: pathlib.Path) -> list[dict]:
    return [v for v in stato(path).values() if v["stato"] == "aperta"]


def da_anomalie(anomalie: list[str], *, quando: str,
                origine: str = "sorvegliante") -> list[Proposta]:
    """Trasforma le anomalie in proposte *vuote*, da compilare a mano.

    Deliberatamente non prova a indovinare la correzione. Il sorvegliante sa
    dire che qualcosa non torna; non sa dire cosa cambiare, e un testo generato
    che *sembra* una diagnosi è peggio di un campo lasciato in bianco, perché
    invita ad accettarlo senza guardarci.
    """
    out = []
    for a in anomalie:
        bersaglio = a.split(":")[0].strip()
        p = Proposta(id=nuovo_id(quando, bersaglio, a), creata_il=quando,
                     origine=origine, innesco=a, bersaglio=bersaglio,
                     modifica="(da compilare)", motivo="(da compilare)")
        out.append(p)
    return out
