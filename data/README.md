# Dati: fonti, difetti trovati, e cosa usare

Stato al 2026-09-15, dopo il collegamento dei connector Twelve Data e FMP.
L'universo a 6 asset eterogenei è **completo e verificato**.

## Universo di lavoro

| Asset | File | Fonte | Barre | Da |
|---|---|---|---|---|
| BTC/USD | `BTCUSD_1d.csv` | Alpha Vantage | 4.887 | 2013-04-28 |
| ETH/USD | `ETHUSD_1d.csv` | Alpha Vantage | 4.056 | 2015-08-08 |
| Oro (GLD) | `GLD_1d_td.csv` | Twelve Data | 5.000 | 2006-10-26 |
| Petrolio (USO) | `USO_1d_td.csv` | Twelve Data | 5.000 | 2006-10-26 |
| Mais (CORN) | `CORN_1d_td.csv` | Twelve Data | 4.091 | 2010-06-09 |
| Azionario (SPY) | `SPY_1d_td.csv` | Twelve Data | 5.000 | 2006-10-26 |

Tutti con OHLCV daily. Periodo comune a tutti e sei: **2015-08-08 → oggi**, circa
11 anni; escludendo ETH si arriva al 2013.

Riferimenti aggiuntivi, non per il backtest: `GC_1d_fmp.csv` (oro futures FMP,
5.000 barre dal 2007-06-21), `GLD_1w.csv` (weekly, AV), `*_binanceus.csv`
(**scartati**, vedi sotto), `WTI_spot_1d_CLOSEONLY.csv` (solo close, inutile per
Ichimoku).

## Tre difetti trovati, tutti silenziosi

Nessuno di questi produce un errore: ognuno produce un backtest plausibile e
sbagliato.

### 1. Binance.US ha un buco di 19 mesi — fonte scartata

`2023-07-14 → 2025-02-19`: nessuna barra, e alla ripresa un salto del **284%**
sul BTC. Corrisponde alla sospensione delle coppie USD su Binance.US dopo la
perdita dei canali bancari. Una serie del genere, usata come primaria, avrebbe
fatto operare la strategia su una continuità inesistente e prodotto un singolo
trade fittizio da tripla cifra. I file restano nel repo solo come promemoria del
perché la fonte è stata esclusa.

### 2. FMP duplica le barre nei festivi

Su `ESUSD` (E-mini S&P) il 2022-02-21 (Presidents' Day) e il 2022-01-17 (MLK)
hanno OHLCV **identico al giorno adiacente**, invece di essere omessi. Falsa due
cose in modo diretto: i conteggi di barre — quindi tutte le finestre temporali
Ichimoku, che nel Pine attuale lavorano su `bar_index` — e il campione dell'ATR,
che regge stop e sizing. L'oro FMP non ha il difetto (0 barre copiate su 5.000):
è specifico dei futures indice.

### 3. Futures ed ETF non hanno lo stesso bar "daily"

Correlazione dei rendimenti log giornalieri fra oro futures (FMP) e GLD (Twelve
Data), 4.838 giorni comuni: **0.8814**. Le volatilità annualizzate coincidono
(18.5% vs 18.2%), quindi non è un problema di scala: i due bar chiudono a orari
diversi (sessione CME ~17:00 ET contro chiusura NYSE 16:00 ET) e misurano
finestre di 24 ore sfalsate.

Per confronto, sullo stesso test BTC fra Alpha Vantage e Twelve Data dà
**+0.9912** same-day, e −0.03 / −0.05 con uno shift di ±1 giorno: convenzione
identica, allineamento corretto.

**Regola che ne segue: una sola famiglia di fonti per backtest.** Mescolare
futures FMP ed ETF Twelve Data in un portafoglio fabbrica lead-lag inesistenti e
falsa qualsiasi timing di segnale cross-asset. Resta un disallineamento
inevitabile e reale fra crypto (bar che chiude a 00:00 UTC) ed ETF (20:00/21:00
UTC): non è un difetto dei dati, è una proprietà dei mercati, e va tenuta
presente quando si aggregano i rendimenti a livello di portafoglio.

## Gate di qualità

`scripts/validate_series.py` va eseguito su ogni serie prima di usarla. Controlla
date duplicate, barre copiate dalla precedente, OHLC incoerente
(`low <= open,close <= high`), prezzi non positivi, interruzioni oltre il ponte
festivo, e gap `|open − close precedente|` oltre il 10%.

Esito attuale sull'universo di lavoro: le sei serie passano. Restano segnalati,
e sono **eventi di mercato reali, non difetti**: 9 gap oltre il 10% su USO nel
2020 (crollo del petrolio, massimo 22% il 2020-03-09), un gap del 12% su CORN
nel 2010 (illiquidità dei primi mesi dell'ETF), un gap del 10% su SPY il
2020-03-16.

## Perimetro delle fonti

### Twelve Data — fonte primaria per tutto ciò che non è crypto
800 crediti/giorno, 8/minuto. Storia daily completa dalla prima quotazione;
`outputsize` massimo 5.000 barre per chiamata, si pagina con
`start_date`/`end_date`. **Gli indici non sono coperti** (SPX, DJI, NDX): si usa
l'ETF proxy, che è comunque la scelta giusta perché l'ETF **è** la serie
tradabile e il costo del roll è già incorporato.

### Alpha Vantage — solo crypto
Verificato endpoint per endpoint: `DIGITAL_CURRENCY_DAILY` e
`TIME_SERIES_WEEKLY` sono liberi con storia completa e OHLCV. Sono premium
`TIME_SERIES_DAILY outputsize=full`, `TIME_SERIES_DAILY_ADJUSTED` e
`INDEX_DATA`. `FX_DAILY` rifiuta `XAU/USD`. Le commodities sono libere ma **solo
close**, e le agricole solo monthly. Per le crypto è la fonte migliore: più
storia di Twelve Data (BTC dal 2013 contro 2017) e convenzione allineata.

### FMP — solo riferimento
40 simboli futures con OHLCV dal 1998, ma su questo piano le autorizzazioni sono
**per simbolo**: `GCUSD` ed `ESUSD` passano, `CLUSD` e `ZCUSX` rispondono
`ACCESS DENIED`. Massimo 5.000 barre per chiamata. Con il difetto dei festivi e
la convenzione oraria diversa, resta utile solo per confronti, non come fonte di
un backtest.

### Non utilizzabili
Bigdata.com `market_tearsheet` (snapshot con variazioni %, non serie storica),
Crypto.com (crypto, già coperto meglio), Binance globale 451 da questo
container, Yahoo 429, stooq nessuna risposta, CryptoCompare/EODHD/TwelveData
REST/FMP REST richiedono chiave.

## Riproducibilità

- `scripts/extract_av_result.py <tool_result> <out.csv> [--ohlc|--close]` —
  normalizza i risultati MCP salvati su disco (Alpha Vantage e Twelve Data, il
  separatore è rilevato dall'header): ordine crescente, scarto delle barre
  piatte a volume nullo e di quelle con OHLC incoerente.
- `scripts/extract_fmp_result.py <tool_result> <out.csv>` — stessa cosa per il
  JSON di FMP.
- `scripts/fetch_binanceus.py` — resta per riferimento storico; la fonte è
  scartata.
- `scripts/validate_series.py` — il gate, da eseguire sempre.

I connector MCP non sono richiamabili da uno script: le serie vengono richieste
in sessione e i risultati grandi, salvati automaticamente su disco, vengono
normalizzati dagli extractor. Le risposte Alpha Vantage espongono anche un
`data_url` su `cdn.alphavantage.co`, scaricabile con curl.

Pulizia applicata: su BTC sono state eliminate 1.017 righe del periodo 2010-2013
in cui `open=high=low=close` con volume nullo, cioè quotazione illiquida senza
scambi reali.
