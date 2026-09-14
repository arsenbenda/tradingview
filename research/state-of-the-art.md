# Stato dell'arte: Ichimoku, Gann, trend following multi-asset

Ricerca svolta il 2026-09-14, prima della fase di validazione. Scopo: capire cosa
esiste di documentato, quali risultati sono credibili e quali sono artefatti di
selezione, e cosa questo implica per il target dichiarato (PF 2.5, DD ridotto,
un solo set di parametri da crypto a commodities).

Criterio di lettura applicato a ogni fonte: **numero di trade, lunghezza del
campione, costi modellati, esistenza di un out-of-sample**. Un rendimento senza
questi quattro dati non è un risultato, è un aneddoto.

---

## 1. Ichimoku: cosa dice l'evidenza seria

### 1.1 Deng et al. (2021), International Journal of Finance & Economics

L'unico studio peer-reviewed rilevante trovato. Testa strategie Ichimoku su 4
indici azionari (1995-2018) e 4 coppie FX (2003-2018).

Risultati:
- con i parametri di default **(9, 26, 52)**: diverse strategie profittevoli nel
  primo sottoperiodo, che **nel secondo sottoperiodo non creano valore in modo
  consistente**;
- con parameter sweep: alcune configurazioni profittevoli sugli indici azionari,
  **nessuna sul forex**.

Lettura: è un risultato di non-stazionarietà, non di inefficacia assoluta. Ma è
esattamente il profilo di un sistema il cui apparente edge in-sample non
sopravvive al cambio di regime. I default 9/26/52 non hanno una giustificazione
empirica fuori dal periodo in cui sono stati osservati.

### 1.2 Backtest meccanico su BTC daily, 8 anni (Coinquant)

Regola: entry quando close chiude sopra il Kumo **e** Tenkan incrocia sopra
Kijun; exit quando close rientra sotto la nuvola. Long-only, no leva, BTCUSDT
spot daily, gen 2018 - lug 2026.

| Metrica | Valore |
|---|---|
| Trade | **12** |
| Win rate | 50% (6/6) |
| Profit factor | **1.95** |
| Max drawdown | **56.26%** |
| CAGR | 12.91% |
| Sharpe | 0.57 |
| Sortino | 0.30 |
| Tempo a mercato | 22.16% |
| vs buy & hold | cattura ~65% del risultato |

Questo è il **benchmark onesto** per l'Ichimoku puro su BTC. Da notare:
- PF 1.95 è vicino al tuo target 2.5, ma con **DD 56%** — le due cose arrivano
  insieme, come previsto;
- **12 trade in 8 anni**: nessuna inferenza statistica è possibile su questo
  campione. Il PF 1.95 ha un intervallo di confidenza che include 1.0;
- il sistema cattura meno del buy & hold stando fuori dal mercato il 78% del
  tempo. Il valore, se c'è, è nel profilo di rischio, non nel rendimento.

### 1.3 Il repo che ha già costruito ciò che volevamo costruire

`sakshamverma2030/Algorithmic-Trading-Framework-in-Crypto-Python` è, in pratica,
il binario Python che avevo proposto — e ha già dato il suo verdetto.

Infrastruttura presente:
- doppio motore di backtest (vettoriale + event-driven bar-by-bar);
- costi: fee taker/maker 0.1%, half-spread, slippage, **market impact
  sqrt (I = Y·σ·√(Q/V))**, financing dei perp;
- fill conservativi (gap attraverso lo stop riempito all'open, ambiguità
  stop-vs-target risolta pessimisticamente);
- **53 unit test, fra cui test espliciti di look-ahead bias e un test di parità
  live-vs-backtest** — esattamente il parity test che avevo indicato come il
  pezzo che nessuno fa;
- separazione in-sample / out-of-sample.

Risultati su dati Binance reali:
- Ichimoku long-only BTC/USDT 1h e ETH/USDT 1h: **profit factor 0.4-0.7** (in
  perdita);
- il vincitore dell'ottimizzatore in-sample: **Sharpe IS ~0.49 → OOS ~ -2.7**;
- pairs trading su 310 giorni: negativo; portafoglio momentum K-Means su 5
  altcoin: -15.6%, sotto il buy & hold di BTC.

Conclusione dichiarata dagli autori stessi: *"treat the system as validated
plumbing with an unvalidated strategy."*

Questo è il singolo dato più informativo di tutta la ricerca. Qualcuno ha
costruito l'infrastruttura corretta, con i costi modellati come si deve, e
l'Ichimoku puro su crypto intraday **perde**. Il crollo Sharpe 0.49 → -2.7 è la
misura diretta di quanto vale un'ottimizzazione in-sample su questa famiglia di
segnali.

### 1.4 I risultati "spettacolari" su TradingView, e cosa li spiega

| Script | Risultato dichiarato | Trade | Campione | Costi | Osservazione |
|---|---|---|---|---|---|
| Skyrexio, *Ichimoku Clouds Strategy L&S* | PF **1.775**, +109%, DD 22.87% | 119 | **1 anno** (2023-01→2024-01), 1H | 0.1% + 5 tick | Disclosure corretta e completa. Campione di un anno, in un anno di recupero crypto |
| Quant_Trading_Pro, *Enhanced Ichimoku V1* | **~3600%** | **29** | Solana, range dichiarato 2018→**2069** | 0.1% + 3 tick | **EMA 171 periodi** descritta come "optimized"; drawdown non dichiarato |
| Ichimoku + RSI (ForexTester) | PF 1.96, +247% | n/d | GBPJPY | n/d | Nessun OOS |

Il pattern è regolare e vale come legge empirica per tutta questa letteratura:
**il rendimento dichiarato è inversamente proporzionale alla dimensione del
campione**. 3600% su 29 trade con un parametro a tre cifre scelto per
ottimizzazione (171) è il caso da manuale: quel numero esiste solo perché ha
funzionato su quel campione. Nessuno dei risultati spettacolari ha un campione
che lo sostenga; l'unico con >100 trade e costi dichiarati (Skyrexio) riporta
PF 1.775 su un anno solo.

**Nessuna fonte credibile trovata riporta PF 2.5 su un campione ampio, costi
inclusi, fuori campione.**

---

## 2. Gann: separare le tre componenti

Le tre parti che ti interessano hanno status probatorio radicalmente diverso e
vanno trattate separatamente.

### 2.1 Ottavi / Murrey Math: nessun supporto statistico

Murrey Math è la formalizzazione meccanica anni '90 della divisione in ottavi di
Gann (frame a 64 barre, range high-low diviso in 8). È quindi la versione
*testabile* degli ottavi, ed è quella che ha avuto più diffusione.

Verdetto documentato: **nessuna statistica pubblicata supporta i ruoli attribuiti
alle singole linee**; sono convenzioni tramandate dalla letteratura divulgativa.
Osservazione ricorrente fra i praticanti: le linee hanno statistiche debolissime
come punti di inversione reale, e i tocchi si risolvono più spesso in correzioni
temporali che proseguono nella direzione iniziale.

Implicazione operativa: gli ottavi restano ammissibili **solo** come ipotesi da
falsificare contro un benchmark banale (livelli di range al 50%), con l'àncora
definita meccanicamente. Il 4/8 e il 5/8 sono i soli su cui vale spendere un
test.

### 2.2 Square of 9 e Gann fan: falliti o non testabili

- **Square of 9 intraday** (backtest su Reliance, Unofficed): non solo non
  funziona, ma **migliora prendendo il trade opposto**.
- **Gann fan**: QuantifiedStrategies dichiara di non essere riuscita a
  backtestarlo, perché l'àncora è soggettiva e non codificabile.

Questo secondo punto conferma, da fonte indipendente, la diagnosi della sessione
precedente: **il contenuto informativo di Gann sta nell'àncora, non nella
geometria**, e senza una regola meccanica di ancoraggio non esiste nemmeno il
test. Chi pubblica risultati Gann positivi sta quasi sempre scegliendo l'àncora
a posteriori.

### 2.3 L'unica evidenza a favore, e perché va trattata con cautela

Max Brown, *"Do Gann Angles Work? An Empirical Test of Angle-Derived Support and
Resistance in High-Frequency Equity Futures"*, SSRN, apr 2026.

Metodologia dichiarata — ed è quella giusta: ES (E-mini S&P 500) a 1 minuto,
2.491 sessioni 2016-2025, **ipotesi pre-registrate** su in-sample 2016-2022 e
testate su held-out 2023-2025, permutation test con sign-flip.

Risultati dichiarati:
- anchor di prezzo dinamici: Cohen's d 0.416 (IS) / 0.497 (OOS), p < 0.001;
- **segnali near-touch sull'angolo 1×1: Sharpe annualizzato 3.81 (IS) / 5.03
  (OOS)**, p < 0.001;
- **fan crossing su 1×2, 2×1, 1×1: rendimenti netti significativamente
  negativi** (d da -0.15 a -0.24);
- gerarchia di pendenza (angoli più ripidi → reazioni più forti): **nessun
  supporto**.

Cautele, che sono serie:
1. **Non ho potuto leggere il full text** — SSRN risponde 403 sia sull'abstract
   page sia sul PDF. Tutto quanto sopra viene da snippet di ricerca, non dal
   paper.
2. **Non è peer-reviewed.** È un preprint, di un autore con altri preprint
   auto-pubblicati sulla stessa microstruttura ES.
3. **Sharpe 3.81-5.03 su ES intraday è implausibile** come edge netto: è un
   ordine di grandezza sopra ciò che sopravvive a costi e impatto su uno degli
   strumenti più efficienti al mondo. Sospetto forte che i costi non siano
   modellati o che il Sharpe sia calcolato su holding period molto brevi senza
   tenere conto della capacità.
4. È **un solo strumento, intraday a 1 minuto**. Non è trasferibile a un sistema
   daily multi-asset senza essere ri-testato da zero.

Però una cosa è utile e va registrata: il paper trova segnale **solo sulla 1×1**
e trova il resto del ventaglio nullo o negativo. Questo è coerente con la
proposta già fatta — tenere la sola 1×1, normalizzata in unità ATR/barra, e
buttare il resto del fan. Vale come **ipotesi con un indizio a favore**, non come
prova.

---

## 3. Dove sta l'evidenza vera: trend following multi-asset

Cambiando famiglia, il quadro probatorio si capovolge.

- **Time-series momentum**: filone consolidato. Un portafoglio TSMOM
  diversificato su tutte le asset class è documentato come notevolmente stabile e
  robusto, con Sharpe elevato e correlazione bassa ai benchmark passivi. Dal
  1995, Sharpe ~0.95 su rendimenti nominali, con volatilità e drawdown molto
  inferiori all'equity.
- **Crypto, TSMOM vs cross-sectional**: il time-series momentum domina —
  ~31.96% annuo, migliore su base risk-adjusted; il cross-sectional mostra DD
  massimi del 55% con profittabilità inferiore.
- **AdaptiveTrend** (Medium, auto-pubblicato): 150+ perp Binance, barre 6h,
  Sharpe 2.41, **maxDD -12.7%**, Calmar 3.18, netto di 4 bps taker + slippage +
  funding, IS 2021 / OOS 2022-2024, circular block bootstrap. Da pesare: i
  parametri vengono **ri-ottimizzati mensilmente via grid search**, che è data
  snooping ricorrente, e il claim non è peer-reviewed.

Il punto strutturale, che è il più importante di tutta la ricerca:

> Tutti i risultati con **drawdown contenuto** (-12.7%, -22.9%) provengono da
> sistemi con **molti strumenti** o portafoglio diversificato. Il risultato
> single-asset su BTC daily ha **DD 56%**. Il drawdown basso non viene dal
> segnale: viene dal numero di posizioni decorrelate e dal vol targeting.

Questo chiude la questione sollevata nella sessione precedente, con evidenza
esterna: "DD ridotto" non è un obiettivo raggiungibile lavorando sulla qualità
dei segnali Ichimoku/Gann su un simbolo alla volta.

---

## 4. Strumenti e infrastruttura

**Validazione.** Lo standard è definito: purged k-fold con embargo, CPCV
(combinatorial purged CV, López de Prado), **Deflated Sharpe Ratio** (Bailey &
López de Prado) per correggere la selezione da test multipli, PBO (probability of
backtest overfitting). vectorbt PRO implementa splitter rolling/expanding,
walk-forward e CV leakage-aware; `mlfinlab` copre CPCV e DSR.

**Dati (il collo di bottiglia reale).** Yahoo/Investing forniscono daily gratuito
sui continui più liquidi (ES, CL, GC, NQ) ma **la costruzione del contratto
continuo non è trasparente** — non è materiale da lavoro quant serio. Databento
fornisce CME/ICE con settlement, back-adjustment, roll date e open interest, a
pagamento. Il problema del back-adjustment resta il rischio numero uno per la
parte commodities: su contratti continui non aggiustati, nuvole, twist e chikou
vengono calcolati su discontinuità di roll che nessuno ha potuto tradare.

---

## 5. Conseguenze operative per questo progetto

1. **Il target PF 2.5 non ha precedenti credibili.** Nessuna fonte con campione
   ampio, costi e OOS lo raggiunge. Il massimo difendibile in questa famiglia è
   PF 1.7-2.0 con DD 20-25%, e solo a livello di portafoglio. Confermo la
   proposta: PF come output, MAR/Calmar e DSR come metriche primarie.

2. **Il benchmark non è il buy & hold: è un trend follower banale.** Donchian
   breakout o MA crossover + vol targeting, sugli stessi 6 asset, stesso periodo,
   stessi costi. Ichimoku + Gann devono battere **quello**. Se non lo battono, la
   complessità non è giustificata — e l'evidenza attuale (Deng, repo Binance) dice
   che è lo scenario più probabile.

3. **Non ricostruire il plumbing da zero.** Esiste già un repo con costi,
   market impact, test di look-ahead e parity live-vs-backtest. Va usato come
   riferimento e come benchmark negativo.

4. **Gann si riduce a due sole ipotesi testabili**: (a) angolo 1×1 in unità
   ATR/barra — con un indizio a favore, non peer-reviewed, da ri-testare su
   daily multi-asset; (b) ottavi 4/8 e 5/8 in log-price su àncora meccanica,
   contro benchmark di range 50%. Square of 9, fan crossing e gerarchia di
   pendenza: **scartati sulla base dell'evidenza trovata**, non implementarli.

5. **Niente ri-ottimizzazione periodica dei parametri.** È la pratica che
   produce i numeri più belli e i fallimenti più rapidi.

6. Le tre patch v3.2 (gate SMA-bull sugli short, soglie e rischio asimmetrici)
   restano da rimuovere o rendere opzionali prima di qualunque test multi-asset:
   sono state selezionate guardando gli esiti su BTC 2021-2024.

---

## Fonti

- Deng, Yu, Wei, Yang, Tatsuro (2021), *The profitability of Ichimoku Kinkohyo
  based trading rules in stock markets and FX markets*, International Journal of
  Finance & Economics 26(4): 5321-5336 —
  https://onlinelibrary.wiley.com/doi/10.1002/ijfe.2067 ·
  https://ideas.repec.org/a/wly/ijfiec/v26y2021i4p5321-5336.html
- Coinquant, *Ichimoku Cloud Strategy on Bitcoin: 8 Years of Backtest Results* —
  https://www.coinquant.ai/blog/ichimoku-cloud-strategy-on-bitcoin-8-years-of-backtest-results
- sakshamverma2030, *Algorithmic Trading Framework in Crypto Python* —
  https://github.com/sakshamverma2030/Algorithmic-Trading-Framework-in-Crypto-Python
- dagzk, *Ichimoku_Backtest* — https://github.com/dagzk/Ichimoku_Backtest
- shikokuchuo, *ichimoku* (R, con interfaccia OANDA per metalli/commodities) —
  https://github.com/shikokuchuo/ichimoku/
- Skyrexio, *Ichimoku Clouds Strategy Long and Short* (TradingView) —
  https://www.tradingview.com/script/uycyVpIq-Ichimoku-Clouds-Strategy-Long-and-Short/
- Quant_Trading_Pro, *Enhanced Ichimoku Cloud Strategy V1* (TradingView) —
  https://www.tradingview.com/script/JqHBw7D3-Enhanced-Ichimoku-Cloud-Strategy-V1-Quant-Trading/
- Brown, M. (2026), *Do Gann Angles Work? An Empirical Test of Angle-Derived
  Support and Resistance in High-Frequency Equity Futures*, SSRN preprint (full
  text non accessibile, 403) —
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6918818
- LuxAlgo Library, *Murrey Math Levels* —
  https://www.luxalgo.com/library/concept/murrey-math-levels/
- LuxAlgo Library, *Gann Square of 9* —
  https://www.luxalgo.com/library/concept/gann-square-of-9/
- Unofficed, *Gann Square of 9 - Reliance Backtest* —
  https://unofficed.com/dashboards/gann-square-of-9-reliance-backtest/
- QuantifiedStrategies, *Gann Fan Trading Strategy* —
  https://www.quantifiedstrategies.com/gann-fan-trading-strategy/
- Quantpedia, *Time Series Momentum Effect* —
  https://quantpedia.com/strategies/time-series-momentum-effect
- *Time-Series and Cross-Sectional Momentum in the Cryptocurrency Market* (AUT
  Centre for Financial Research) —
  https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf
- Velazquez Bustamante, A., *AdaptiveTrend* —
  https://antonio-velazquez-bustamante.medium.com/adaptivetrend-a-6-hour-trend-following-system-for-crypto-that-adapts-its-portfolio-every-month-eb114edcbcef
- Man Group, *Trend Following and Drawdowns: Is This Time Different?* —
  https://www.man.com/insights/is-this-time-different
- Wikipedia, *Purged cross-validation* —
  https://en.wikipedia.org/wiki/Purged_cross-validation
- Databento, *Commodity Futures Data & APIs* —
  https://databento.com/futures/commodity
