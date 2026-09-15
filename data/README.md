# Dati: cosa è disponibile, cosa manca, e perché

Stato al 2026-09-14. Ricognizione fatta via connector MCP (Alpha Vantage,
Google Drive) e via rete diretta dal container.

## Matrice di disponibilità

| Asset | Fonte | Granularità | OHLC? | Storia | Stato |
|---|---|---|---|---|---|
| BTC/USD | Alpha Vantage `DIGITAL_CURRENCY_DAILY` | daily | **sì** | 2013-04-28 → oggi, 4.887 barre | **pronto** |
| ETH/USD | Alpha Vantage `DIGITAL_CURRENCY_DAILY` | daily | **sì** | 2015-08-08 → oggi, 4.056 barre | **pronto** |
| BTC, ETH (controllo) | Binance.US REST pubblico | daily | sì | 2019-09 → oggi, ~1.970 barre | **pronto** (script) |
| Gold (GLD ETF) | Alpha Vantage `TIME_SERIES_WEEKLY` | **weekly** | sì | 2004-11 → oggi, 1.139 barre | parziale |
| Gold spot (XAU) | Alpha Vantage `GOLD_SILVER_HISTORY` | daily | **no — solo close** | 2011-06 → oggi | **inutilizzabile** |
| WTI spot | Alpha Vantage `WTI` | daily | **no — solo close** | 1986-01 → oggi, 10.241 barre | **inutilizzabile** |
| Corn, Wheat, Copper, Sugar… | Alpha Vantage commodities | **monthly** + solo close | no | lunga | **inutilizzabile** |
| ETF daily (GLD, USO, CORN, UNG, DBA) | Alpha Vantage `TIME_SERIES_DAILY` | daily | sì | `outputsize=full` è **premium**; il piano free dà 100 barre | **bloccato** |

### Perché "solo close" significa inutilizzabile

Non è pignoleria. Tenkan, Kijun e Senkou B sono **midpoint di massimo e minimo**
su una finestra; l'ATR, che regge stop e sizing, è definito su high/low. Una
serie di soli close non permette di calcolare nessuno dei tre, né di
normalizzare Gann in unità ATR. Con i soli close si può testare un sistema a
medie mobili, non Ichimoku.

### Percorsi di rete verificati

Testati dal container: Binance globale **451** (geo-block), Yahoo Finance **429**,
stooq nessuna risposta, CryptoCompare / EODHD / TwelveData / FMP richiedono
chiave (le chiavi demo sono rifiutate). Funzionano: **Binance.US**, **Kraken**
(max 720 barre), CoinGecko ping, Alpha Vantage.

Conclusione: **il lato crypto è risolto e riproducibile; il lato
commodities/indici daily non è ottenibile gratuitamente da qui.**

## Controllo incrociato fra fonti indipendenti

Confronto AV vs Binance.US sui giorni in comune (1.970 barre):

| | BTC | ETH |
|---|---|---|
| Scarto mediano sul close | 0.095% | 0.168% |
| Scarto mediano sul high | 0.169% | 0.211% |
| Giorni con scarto close > 2% | 29 (**1.5%**) | 32 (**1.6%**) |
| Scarto massimo | 21.2% | 21.4% |

Le due serie concordano nel caso tipico ma divergono in modo materiale
sull'1.5% dei giorni. Parte è attribuibile a Binance.US nei primi mesi (nel
2019 stampa ripetutamente lo stesso valore, es. ETH 213.46 su tre giorni
consecutivi: prezzo fermo per illiquidità), parte a giornate estreme
(2020-03-12) dove i venue divergono davvero.

**Implicazione operativa, non accademica**: una regola come "il close attraversa
cloudTop" cambia giorno di attivazione a seconda della fonte su ~1.5% delle
barre. È lo stesso ordine di grandezza dell'edge che stiamo cercando di
misurare. Ne segue che il **parity test contro il Pine ha senso solo se entrambi
i lati usano lo stesso feed** — quindi l'export CSV da TradingView non è un
ripiego, è la fonte corretta per quel test specifico.

## File

```
data/raw/BTCUSD_1d.csv                  OHLCV daily, Alpha Vantage
data/raw/ETHUSD_1d.csv                  OHLCV daily, Alpha Vantage
data/raw/BTCUSD_1d_binanceus.csv        OHLCV daily, Binance.US (controllo)
data/raw/ETHUSD_1d_binanceus.csv        OHLCV daily, Binance.US (controllo)
data/raw/GLD_1w.csv                     OHLCV weekly, Alpha Vantage
data/raw/WTI_spot_1d_CLOSEONLY.csv      solo close — non usare per Ichimoku
```

Pulizia applicata in `scripts/extract_av_result.py`: ordine cronologico
crescente, scarto delle barre piatte a volume nullo (1.017 righe eliminate su
BTC, tutto il periodo 2010-2013 di quotazione illiquida in cui
open=high=low=close), scarto delle righe che violano `low <= open,close <= high`.

Verifiche: BTC 0 duplicati, 1 solo giorno mancante (2013-08-07), copertura 100%.
ETH 0 duplicati, 0 buchi.

## Riproducibilità

- `scripts/fetch_binanceus.py BTCUSD ETHUSD` — ricostruisce i file Binance.US da
  zero, nessuna chiave richiesta, paginazione automatica.
- I file Alpha Vantage arrivano dal connector MCP, che non è richiamabile da uno
  script: `scripts/extract_av_result.py` normalizza il risultato salvato su
  disco. Le risposte grandi espongono anche un `data_url` su
  `cdn.alphavantage.co`, scaricabile con curl.

## Server MCP: ricognizione del registry

Verificato se un altro connector MCP risolve il buco sulle commodities daily.

### Perimetro esatto del piano Alpha Vantage free

Testato endpoint per endpoint, non dedotto:

| Endpoint | Esito |
|---|---|
| `DIGITAL_CURRENCY_DAILY` | **libero, storia completa, OHLCV** |
| `TIME_SERIES_WEEKLY` | **libero, storia completa, OHLCV** |
| `TIME_SERIES_DAILY` `outputsize=full` | premium (il free dà 100 barre) |
| `TIME_SERIES_DAILY_ADJUSTED` | premium |
| `INDEX_DATA` (SPX, DAX, indici) | premium — "not yet entitled to index data access" |
| `FX_DAILY` con `XAU/USD` | rifiutato: XAU non è nella lista FX di Alpha Vantage |
| commodities (`WTI`, `CORN`, …) | libere ma **solo close**, e le agricole solo monthly |

Quindi su Alpha Vantage il daily OHLC esiste solo per le crypto. Il resto
richiede il piano premium.

### Altri connector già collegati

- **Bigdata.com** `market_tearsheet`: prezzo corrente e variazioni % su
  1D/5D/1M/3M/6M/YTD/1Y, comprese commodities. È uno snapshot, **non una serie
  storica** — inutilizzabile per un backtest.
- **Crypto.com** `get_market_candles`: OHLCV crypto a intervalli, ma limitato
  per numero di barre. Il lato crypto è già coperto meglio da Alpha Vantage.

### Candidati che risolverebbero, da collegare su claude.ai

| Server | Free tier | Storia daily | Giudizio |
|---|---|---|---|
| **Twelve Data** | 800 crediti/giorno, 8/min | **storia completa** dalla prima data di quotazione su intervalli daily/weekly/monthly | **prima scelta**; da verificare la copertura ETF sul piano free, che la documentazione lega ai piani superiori |
| **FMP** | 250 chiamate/giorno, EOD, 500MB/30gg | **~5 anni** | simboli commodities diretti (`GCUSD` oro, `CLUSD` crude) senza passare dagli ETF, ma 5 anni non coprono più di un regime |
| **CoinDesk** | — | OHLCV crypto e indici | `connect_incomplete`; crypto già coperto |

Nessuno dei due può essere collegato da qui: l'autorizzazione va fatta
dall'utente su claude.ai.

## Cosa serve per sbloccare le commodities

Tre opzioni, in ordine di preferenza:

1. **Export CSV daily da TradingView** per i simboli target. Gratis, ed è lo
   stesso feed su cui girerà il Pine — rende il parity test esatto invece che
   approssimato. È anche l'unica opzione che elimina il problema del
   back-adjustment, perché si esporta la serie che si vede a schermo.
2. **Chiave Alpha Vantage premium** (~50 USD/mese): sblocca
   `TIME_SERIES_DAILY outputsize=full`, quindi OHLC daily su GLD, USO, CORN,
   UNG, DBA e indici. Da mettere come secret dell'ambiente, non nel repo.
3. **ETF come proxy** invece dei futures continui — da adottare in ogni caso,
   indipendentemente dalla fonte: il prezzo dell'ETF **è** la serie tradabile,
   quindi il costo del roll è già incorporato e il problema del
   back-adjustment dei contratti continui non esiste. Per un sistema retail è
   anche più realistico dei futures.
