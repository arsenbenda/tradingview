#!/usr/bin/env python3
"""Scarica OHLCV daily completo da Binance.US (endpoint pubblico, nessuna chiave).

Serve come percorso riproducibile e come controllo incrociato sui dati crypto
di Alpha Vantage: due fonti indipendenti sugli stessi bar. Binance.US parte da
settembre 2019, quindi copre meno storia di Alpha Vantage ma permette di
verificare che le due serie coincidano nel periodo comune.

Uso: fetch_binanceus.py BTCUSD ETHUSD [...]   -> data/raw/<SYM>_1d_binanceus.csv
"""
import json
import pathlib
import subprocess
import sys
import time

API = "https://api.binance.us/api/v3/klines"
OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"


def fetch_page(symbol, start_ms):
    url = f"{API}?symbol={symbol}&interval=1d&limit=1000&startTime={start_ms}"
    # curl invece di urllib: rispetta la configurazione proxy/CA dell'ambiente
    res = subprocess.run(
        ["curl", "-sS", "--max-time", "45", "--retry", "3", "--retry-delay", "2", url],
        capture_output=True, text=True, check=True,
    )
    return json.loads(res.stdout)


def fetch_symbol(symbol):
    rows, cursor = [], 1_500_000_000_000  # ~luglio 2017, prima dell'apertura di Binance.US
    while True:
        page = fetch_page(symbol, cursor)
        if not page:
            break
        rows.extend(page)
        last_open = page[-1][0]
        if len(page) < 1000:
            break
        cursor = last_open + 86_400_000
        time.sleep(0.3)

    seen, out = set(), []
    for k in rows:
        day = time.strftime("%Y-%m-%d", time.gmtime(k[0] / 1000))
        if day in seen:
            continue
        seen.add(day)
        out.append((day, k[1], k[2], k[3], k[4], k[5]))
    out.sort()

    dst = OUT / f"{symbol}_1d_binanceus.csv"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w") as fh:
        fh.write("date,open,high,low,close,volume\n")
        for rec in out:
            fh.write(",".join(rec) + "\n")
    print(f"{dst.name}: {len(out)} barre {out[0][0]} -> {out[-1][0]}")


if __name__ == "__main__":
    for sym in sys.argv[1:] or ["BTCUSD", "ETHUSD"]:
        fetch_symbol(sym)
