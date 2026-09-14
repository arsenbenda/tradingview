#!/usr/bin/env python3
"""Estrae un CSV pulito da un file di risultato MCP Alpha Vantage.

I risultati MCP troppo grandi per il contesto vengono salvati su disco dal
client come JSON ({"result": "<csv>"} oppure una busta di preview con
sample_data/data_url). Questo script normalizza: ordine cronologico
crescente, header canonico, righe non valide scartate.

Uso: extract_av_result.py <file_tool_result.json> <out.csv> [--ohlc|--close]
"""
import json
import sys


def load_csv_text(path):
    with open(path) as fh:
        blob = json.load(fh)
    if isinstance(blob, dict):
        for key in ("result", "sample_data"):
            if isinstance(blob.get(key), str):
                return blob[key], blob.get("preview", False)
    raise SystemExit(f"{path}: nessun campo CSV riconosciuto")


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "--ohlc"

    text, is_preview = load_csv_text(src)
    if is_preview:
        print(f"ATTENZIONE: {src} e' una preview troncata, non i dati completi")

    lines = [ln for ln in text.splitlines() if ln.strip()]
    rows = [ln.split(",") for ln in lines[1:]]

    out, dropped = [], 0
    for r in rows:
        try:
            if mode == "--close":
                date, close = r[0], float(r[1])
                rec = (date, close)
            else:
                date = r[0]
                o, h, l, c = (float(x) for x in r[1:5])
                v = float(r[5]) if len(r) > 5 else 0.0
                # barre piatte a volume nullo = quotazione illiquida, non un bar
                if o == h == l == c and v == 0.0:
                    dropped += 1
                    continue
                if not (l <= o <= h and l <= c <= h):
                    dropped += 1
                    continue
                rec = (date, o, h, l, c, v)
        except (ValueError, IndexError):
            dropped += 1
            continue
        out.append(rec)

    out.sort(key=lambda x: x[0])
    header = "date,close" if mode == "--close" else "date,open,high,low,close,volume"
    with open(dst, "w") as fh:
        fh.write(header + "\n")
        for rec in out:
            fh.write(",".join(str(x) for x in rec) + "\n")

    print(f"{dst}: {len(out)} barre {out[0][0]} -> {out[-1][0]} (scartate {dropped})")


if __name__ == "__main__":
    main()
