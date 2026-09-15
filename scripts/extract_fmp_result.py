#!/usr/bin/env python3
"""Estrae un CSV OHLCV da un risultato MCP FMP salvato su disco.

FMP restituisce una lista JSON di barre in ordine decrescente. Questo script la
normalizza nello stesso formato degli altri file in data/raw: ordine crescente,
colonne date,open,high,low,close,volume.

Uso: extract_fmp_result.py <file_tool_result> <out.csv>
"""
import json
import re
import sys


def main():
    src, dst = sys.argv[1], sys.argv[2]
    raw = open(src).read()

    # il file puo' essere il JSON nudo oppure incapsulato in {"result": "..."}
    try:
        blob = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, re.S)
        if not match:
            raise SystemExit(f"{src}: nessun array JSON trovato")
        blob = json.loads(match.group(0))
    if isinstance(blob, dict):
        blob = json.loads(blob["result"]) if isinstance(blob.get("result"), str) else blob.get("data", [])

    rows, dropped = [], 0
    for b in blob:
        try:
            o, h, l, c = float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])
            if not (l <= o <= h and l <= c <= h):
                dropped += 1
                continue
            rows.append((b["date"], o, h, l, c, float(b.get("volume") or 0)))
        except (KeyError, TypeError, ValueError):
            dropped += 1

    rows.sort(key=lambda r: r[0])
    with open(dst, "w") as fh:
        fh.write("date,open,high,low,close,volume\n")
        for r in rows:
            fh.write(",".join(str(x) for x in r) + "\n")
    print(f"{dst}: {len(rows)} barre {rows[0][0]} -> {rows[-1][0]} (scartate {dropped})")


if __name__ == "__main__":
    main()
