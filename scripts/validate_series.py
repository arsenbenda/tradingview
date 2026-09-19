#!/usr/bin/env python3
"""Gate di qualita' sulle serie in data/raw.

Controlla i difetti che rovinano un backtest senza dare errore:

  duplicati        stessa data due volte
  barre copiate    OHLCV identico a quello precedente — difetto osservato sui
                   futures indice di FMP, che nei festivi ripetono la barra
                   invece di ometterla; falsa i conteggi di barre (le finestre
                   temporali Ichimoku) e gonfia il campione dell'ATR.
                   **Oltre SOGLIA_RIPETUTE la serie non e' utilizzabile**, non
                   solo sospetta: vedi sotto
  OHLC incoerente  low > open/close oppure high < open/close
  buchi            giorni di calendario mancanti oltre il weekend
  gap anomali      |open - close precedente| oltre soglia, indizio di splice di
                   roll su una serie continua non aggiustata
  prezzi non validi  zero o negativi (il log-price diventa impossibile)

Perche' le barre ripetute sono un difetto **bloccante** e non un avviso: una
quotazione ferma per giorni non e' un mercato che non si muove, e' una serie che
non viene aggiornata. L'ATR misurato su quelle barre collassa verso zero, lo stop
a 2xATR diventa minuscolo, e il sizing — che e' rischio diviso distanza dello
stop — si gonfia di conseguenza. Quando il prezzo infine si muove, il trade
vince per un R-multiple enorme. Non e' un vantaggio, e' un artefatto.

Misurato sul campo il 2026-09-16 (`results/futures_50y_2.md`): MILK e MILKWET,
con il 58% e l'11% di barre ripetute, producevano da soli il 110% del PnL di un
portafoglio di 35 futures, con R-multiple fra 15 e 40. Tolto il migliore dei
due, il test pre-registrato passava da superato a fallito. Quel controllo
esisteva gia' qui e veniva solo stampato: da allora e' una soglia.

Uso: validate_series.py [file...]   (default: tutti i data/raw/*.csv)
     validate_series.py --solo-bloccanti [file...]   (elenca solo le inutilizzabili)

Uso da codice, per filtrare **prima** di calcolare un risultato:

    from validate_series import utilizzabile
    if not utilizzabile(path)[0]:
        continue
"""
import csv
import datetime as dt
import glob
import statistics
import sys

GAP_ALERT_PCT = 10.0

#: frazione massima di barre identiche alla precedente perche' una serie sia
#: utilizzabile. Cinque per cento e' gia' molto: su un mercato liquido le barre
#: ripetute sono i festivi non omessi, che stanno sotto l'uno per cento.
SOGLIA_RIPETUTE = 0.05
# un ponte festivo su un mercato a 5 giorni arriva a 4 giorni di calendario
# (venerdi' -> martedi'); oltre i 6 non e' piu' un festivo
HOLE_ALERT_DAYS = 6


def conta_ripetute(rows):
    """Barre il cui OHLCV e' identico alla precedente."""
    return sum(
        1 for i in range(1, len(rows))
        if all(rows[i][k] == rows[i - 1][k] for k in ("open", "high", "low", "close", "volume"))
    )


def utilizzabile(path):
    """``(True, "")`` se la serie puo' entrare in un backtest, altrimenti il perche'.

    Da chiamare **prima** di calcolare qualunque rendimento. Un'esclusione decisa
    dopo aver visto quali serie salvano il risultato non e' un gate di qualita',
    e' una selezione.
    """
    esito = check(path)
    if len(esito) < 3:
        return False, "serie senza OHLC"
    _, _, bloccanti = esito
    return (not bloccanti), "; ".join(bloccanti)


def check(path, weekly=False):
    rows = list(csv.DictReader(open(path)))
    if not rows or "open" not in rows[0]:
        return f"{path}: serie senza OHLC, salta", 0, ["serie senza OHLC"]

    problems, bloccanti = [], []
    dates = [dt.date.fromisoformat(r["date"]) for r in rows]

    dups = len(dates) - len(set(dates))
    if dups:
        problems.append(f"{dups} date duplicate")

    copied = conta_ripetute(rows)
    quota = copied / len(rows) if rows else 0.0
    if copied:
        problems.append(f"{copied} barre copiate dalla precedente ({quota:.1%})")
    if quota > SOGLIA_RIPETUTE:
        bloccanti.append(f"barre ripetute {quota:.1%} oltre la soglia del {SOGLIA_RIPETUTE:.0%}")

    bad_ohlc = sum(
        1 for r in rows
        if not (float(r["low"]) <= float(r["open"]) <= float(r["high"])
                and float(r["low"]) <= float(r["close"]) <= float(r["high"]))
    )
    if bad_ohlc:
        problems.append(f"{bad_ohlc} barre con OHLC incoerente")

    nonpos = sum(1 for r in rows if float(r["close"]) <= 0)
    if nonpos:
        problems.append(f"{nonpos} prezzi non positivi")
        bloccanti.append(f"{nonpos} prezzi non positivi")

    gaps = [
        (dates[i - 1], dates[i])
        for i in range(1, len(dates))
        if (dates[i] - dates[i - 1]).days > (11 if weekly else HOLE_ALERT_DAYS)
    ]
    if gaps:
        problems.append(f"{len(gaps)} interruzioni sospette (prima: {gaps[0][0]}->{gaps[0][1]})")

    jumps = []
    for i in range(1, len(rows)):
        prev_close = float(rows[i - 1]["close"])
        if prev_close > 0:
            pct = abs(float(rows[i]["open"]) - prev_close) / prev_close * 100
            if pct > GAP_ALERT_PCT:
                jumps.append((rows[i]["date"], pct))
    if jumps:
        worst = max(jumps, key=lambda x: x[1])
        problems.append(f"{len(jumps)} gap oltre {GAP_ALERT_PCT}% (max {worst[1]:.0f}% il {worst[0]})")

    span = (dates[-1] - dates[0]).days + 1
    head = f"{path.split('/')[-1]:26s} {len(rows):5d} barre  {dates[0]} -> {dates[-1]}  copertura {len(rows)/span:5.1%}"
    coda = ""
    if bloccanti:
        coda += "\n    NON UTILIZZABILE: " + "; ".join(bloccanti)
    if problems:
        coda += "\n    ATTENZIONE: " + "; ".join(problems)
    return head + (coda or "\n    ok"), len(problems), bloccanti


def main():
    argv = [a for a in sys.argv[1:] if a != "--solo-bloccanti"]
    solo_bloccanti = "--solo-bloccanti" in sys.argv[1:]
    files = argv or sorted(glob.glob("data/raw/*.csv"))
    total = inutilizzabili = 0
    for f in files:
        line, n, bloccanti = check(f, weekly="_1w" in f)
        total += n
        inutilizzabili += bool(bloccanti)
        if bloccanti or not solo_bloccanti:
            print(line)
    print(f"\n{len(files)} file controllati, {total} anomalie segnalate, "
          f"{inutilizzabili} serie NON UTILIZZABILI")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
