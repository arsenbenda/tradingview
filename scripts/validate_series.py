#!/usr/bin/env python3
"""Gate di qualita' sulle serie in data/raw.

Controlla i difetti che rovinano un backtest senza dare errore:

  duplicati        stessa data due volte
  barre copiate    OHLCV identico a quello precedente — difetto osservato sui
                   futures indice di FMP, che nei festivi ripetono la barra
                   invece di ometterla; falsa i conteggi di barre (le finestre
                   temporali Ichimoku) e gonfia il campione dell'ATR
  OHLC incoerente  low > open/close oppure high < open/close
  buchi            giorni di calendario mancanti oltre il weekend
  gap anomali      |open - close precedente| oltre soglia, indizio di splice di
                   roll su una serie continua non aggiustata
  prezzi non validi  zero o negativi (il log-price diventa impossibile)

Uso: validate_series.py [file...]   (default: tutti i data/raw/*.csv)
"""
import csv
import datetime as dt
import glob
import statistics
import sys

GAP_ALERT_PCT = 10.0
# un ponte festivo su un mercato a 5 giorni arriva a 4 giorni di calendario
# (venerdi' -> martedi'); oltre i 6 non e' piu' un festivo
HOLE_ALERT_DAYS = 6


def check(path, weekly=False):
    rows = list(csv.DictReader(open(path)))
    if not rows or "open" not in rows[0]:
        return f"{path}: serie senza OHLC, salta", 0

    problems = []
    dates = [dt.date.fromisoformat(r["date"]) for r in rows]

    dups = len(dates) - len(set(dates))
    if dups:
        problems.append(f"{dups} date duplicate")

    copied = sum(
        1 for i in range(1, len(rows))
        if all(rows[i][k] == rows[i - 1][k] for k in ("open", "high", "low", "close", "volume"))
    )
    if copied:
        problems.append(f"{copied} barre copiate dalla precedente")

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
    return head + ("\n    ATTENZIONE: " + "; ".join(problems) if problems else "\n    ok"), len(problems)


def main():
    files = sys.argv[1:] or sorted(glob.glob("data/raw/*.csv"))
    total = 0
    for f in files:
        line, n = check(f, weekly="_1w" in f)
        total += n
        print(line)
    print(f"\n{len(files)} file controllati, {total} anomalie segnalate")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
