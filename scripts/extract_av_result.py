#!/usr/bin/env python3
"""Estrae un CSV pulito da un file di risultato MCP Alpha Vantage.

I risultati MCP troppo grandi per il contesto vengono salvati su disco dal
client come JSON ({"result": "<csv>"} oppure una busta di preview con
sample_data/data_url). Questo script normalizza: ordine cronologico
crescente, header canonico, righe non valide scartate.

Il separatore viene rilevato dall'header: virgola per Alpha Vantage, punto e
virgola per Twelve Data.

Le date ripetute vengono collassate, ma **solo se le due righe descrivono la
stessa barra**: vedi `dedupe`. Su EEM l'API ha restituito ogni giorno di
contrattazione dal 2013 al 2021 due volte, con differenze di puro arrotondamento
(divergenza massima sul close 0.088%, su 56 giorni su 3.445). Collassarle è
corretto; collassare due barre davvero diverse sarebbe scegliere un prezzo fra
due a caso, quindi in quel caso lo script si ferma.

Uso: extract_av_result.py <file_tool_result.json> <out.csv> [--ohlc|--close]
"""
import json
import sys

#: divergenza massima tollerata fra due righe con la stessa data.
#: Sopra questa soglia non sono la stessa barra arrotondata in due modi, sono
#: due barre diverse, e nessuna delle due ha titolo per prevalere sull'altra.
DUP_TOLERANCE = 0.005


def load_csv_text(path):
    with open(path) as fh:
        blob = json.load(fh)
    if isinstance(blob, dict):
        for key in ("result", "sample_data"):
            if isinstance(blob.get(key), str):
                return blob[key], blob.get("preview", False)
    raise SystemExit(f"{path}: nessun campo CSV riconosciuto")


def dedupe(rows, src="?"):
    """Collassa le date ripetute, se le righe ripetute sono la stessa barra.

    L'API può restituire due pagine sovrapposte: la stessa barra arriva due
    volte, con differenze di arrotondamento sull'ultima cifra. Tenerle entrambe
    romperebbe il caricamento (``engine.data.load`` rifiuta le date duplicate) e
    falserebbe ogni conteggio di barre, quindi ogni finestra degli indicatori.

    Ma collassare **non** è sempre lecito: se due righe con la stessa data
    portano prezzi diversi oltre la tolleranza, tenerne una significa sceglierne
    una a caso fra due fonti che non concordano, ed è il modo in cui si ottiene
    un backtest plausibile e sbagliato. In quel caso lo script si ferma e dice
    quali date, perché il problema va risolto alla fonte.

    Restituisce ``(righe, quante_date_collassate)``.
    """
    per_data = {}
    for r in rows:
        per_data.setdefault(r[0], []).append(r)

    divergenti = []
    for data, gruppo in per_data.items():
        if len(gruppo) == 1:
            continue
        for campo in range(1, len(gruppo[0])):
            valori = [g[campo] for g in gruppo]
            minimo, massimo = min(valori), max(valori)
            # il volume può differire fra venue senza che i prezzi differiscano:
            # non è un prezzo, e nessuna decisione del motore lo guarda
            e_volume = campo == 5
            if not e_volume and minimo > 0 and (massimo - minimo) / minimo > DUP_TOLERANCE:
                divergenti.append((data, minimo, massimo))
                break

    if divergenti:
        print(f"{src}: {len(divergenti)} date ripetute con prezzi DIVERSI oltre "
              f"{DUP_TOLERANCE:.1%} — non sono la stessa barra, risolvere alla fonte.")
        for data, lo, hi in divergenti[:5]:
            print(f"    {data}: da {lo} a {hi}")
        raise SystemExit(1)

    collassate = sum(1 for g in per_data.values() if len(g) > 1)
    return [g[0] for g in per_data.values()], collassate


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "--ohlc"

    text, is_preview = load_csv_text(src)
    if is_preview:
        print(f"ATTENZIONE: {src} e' una preview troncata, non i dati completi")

    lines = [ln for ln in text.splitlines() if ln.strip()]
    # Alpha Vantage separa con virgola, Twelve Data con punto e virgola
    sep = ";" if lines[0].count(";") > lines[0].count(",") else ","
    rows = [ln.split(sep) for ln in lines[1:]]

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
    out, collassate = dedupe(out, src)
    header = "date,close" if mode == "--close" else "date,open,high,low,close,volume"
    with open(dst, "w") as fh:
        fh.write(header + "\n")
        for rec in out:
            fh.write(",".join(str(x) for x in rec) + "\n")

    nota = f", collassate {collassate} date ripetute" if collassate else ""
    print(f"{dst}: {len(out)} barre {out[0][0]} -> {out[-1][0]} (scartate {dropped}{nota})")


if __name__ == "__main__":
    main()
