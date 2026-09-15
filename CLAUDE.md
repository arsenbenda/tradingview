# tradingview — stato del progetto

Sistema di ricerca per strategie multi-asset basate su Ichimoku e Gann. Il
deliverable finale è Pine su TradingView; la validazione avviene in Python,
perché TradingView non espone API per lo Strategy Tester.

## Come ripartire in trenta secondi

```bash
pip install pandas numpy pytest
python3 -m pytest tests/ -q                      # 70 test, devono passare tutti
python3 scripts/run_benchmark.py                 # benchmark di riferimento
python3 scripts/compare_strategies.py            # v3.2 e v5.5 contro il benchmark
python3 scripts/run_ablation.py                  # quali componenti aggiungono valore
python3 scripts/run_ichimoku_tests.py            # Ichimoku come segnale e come uscita
python3 scripts/run_validation.py                # walk-forward, k-fold purgato, DSR
python3 scripts/validate_series.py               # gate di qualità sui dati
```

I dati sono già in `data/raw/`, puliti e verificati. Non serve rete per
rieseguire nulla.

## Il risultato, in tre righe

| | MAR | Sharpe | CAGR | maxDD | Trade |
|---|---|---|---|---|---|
| **Donchian 55/20** (benchmark, parametri Turtle mai ottimizzati) | **0.87** | 1.39 | 7.7% | 8.9% | 303 |
| Confluence v3.2 (54 input) | 0.51 | 1.02 | 3.4% | 6.6% | 115 |
| Sanyaku v5.5 (53 input) | 0.37 | 0.93 | 2.1% | 5.7% | 76 |

Periodo 2015-08-10 → 2026-09-14, sei asset, un solo set di parametri, costi per
asset. Nessuna delle due strategie Pine batte il benchmark, e perdono anche su
BTC, l'asset su cui sono state sviluppate.

Nessuno dei 15 componenti Ichimoku/Gann testati come filtro migliora il
benchmark. Sette varianti su ventidue lo battono in-sample, ma **nessuna
sopravvive alla validazione fuori campione** (`results/validation.md`): il
miglior candidato ha un Deflated Sharpe di 0.025 sul differenziale contro il
benchmark, e la procedura che lo seleziona vale −0.04 di MAR fuori campione.
Dopo ventidue ipotesi, il benchmark è ancora la cosa più difficile da battere.

## Regole di lavoro che hanno prodotto questi risultati

Sono il motivo per cui i numeri sopra sono affidabili. Vanno mantenute.

1. **Il benchmark è un trend follower banale, non il buy & hold.** Donchian
   55/20 con parametri Turtle pubblicati negli anni Ottanta: nessun vantaggio di
   adattamento ai dati. Qualunque cosa si costruisca va confrontata con la riga
   PORTAFOGLIO, non con BTC da solo.
2. **Metrica primaria MAR** (CAGR / maxDD), poi Sharpe. Il profit factor si
   riporta e non si insegue: nel confronto qui sopra la strategia con il PF più
   alto delle tre è la peggiore delle tre, perché il PF ignora il capitale fermo.
3. **Un solo set di parametri su tutti gli asset.** Ottimizzare per asset
   distrugge la domanda a cui il progetto vuole rispondere.
4. **Ogni ipotesi testata va contata.** Il conteggio non sta più a mano: è la
   lunghezza di `engine/hypotheses.CATALOGUE`, e da lì entra nel Deflated Sharpe.
   Aggiungere un'ipotesi significa aggiungere una riga a quel catalogo, e la
   soglia si alza da sola. Con ventidue ipotesi il migliore per caso migliora
   comunque qualcosa — di quanto, lo dice `run_validation.py`.
5. **Un filtro che aiuta un solo asset è un filtro adattato a quell'asset.** Si
   riporta sempre su quanti asset su sei migliora.
6. **Niente ri-ottimizzazione periodica dei parametri.** È la pratica che
   produce i numeri più belli e i fallimenti più rapidi.
7. **Un vantaggio in-sample non è un risultato finché non passa la validazione.**
   Un candidato stabile su tutti i sotto-periodi non è una conferma se è stato
   scelto conoscendoli tutti: va validata la *procedura* di selezione, non il suo
   vincitore. `run_validation.py` fa entrambe le cose e le tiene separate.

## Architettura

```
engine/
  indicators.py   primitive Pine (Ichimoku, ATR/RMA, DMI) con semantica replicata
  backtest.py     motore bar-by-bar: segnale su t, fill su t+1, uscite parziali
  metrics.py      MAR, Sharpe, Sortino, PF, aggregazione di portafoglio
  costs.py        costi per asset, in percentuale (non in tick)
  data.py         caricamento con controlli bloccanti
  filters.py      componenti da innestare sul benchmark (catalogo per l'ablazione)
  hypotheses.py   il catalogo di tutte le ipotesi provate; N_HYPOTHESES entra nel DSR
  validation.py   walk-forward, k-fold purgato con embargo, Deflated Sharpe, bootstrap
  strategies/     donchian (benchmark), sanyaku (v5.5), confluence (v3.2)
scripts/          runner riproducibili + estrattori dati + gate di qualità
strategies/       i due Pine originali, invariati
results/          benchmark_donchian.md, comparison.md, ablation.md,
                  ichimoku_tests.md, validation.md
research/         state-of-the-art.md — ricognizione della letteratura
data/README.md    fonti, difetti trovati, perimetro dei connector
```

### Proprietà del motore, coperte da test

* segnale alla chiusura di `t`, esecuzione all'apertura di `t+1`;
* quantità derivata dal prezzo di **fill** (`size_at_signal=True` riproduce il
  difetto del Pine per poterlo misurare);
* costi su entrambi i lati, in percentuale per asset;
* uscita all'apertura quando la barra gappa oltre lo stop, quindi si può perdere
  più del rischio nominale, come nella realtà;
* trail che muove lo stop solo a favore;
* uscite parziali (la v3.2 scala al 20% e 30%);
* **assenza di lookahead verificata per costruzione**: il valore di un
  indicatore sulla barra `t` calcolato sulla serie completa deve coincidere con
  quello calcolato sulla serie troncata a `t`.

## Dati

Sei asset eterogenei, OHLCV daily, in `data/raw/`:
BTC ed ETH (Alpha Vantage), GOLD/GLD, CRUDE/USO, CORN, EQUITY/SPY (Twelve Data).
Periodo comune 2015-08 → oggi.

Tre difetti silenziosi trovati e documentati in `data/README.md`: il buco di 19
mesi di Binance.US (fonte scartata), le barre duplicate nei festivi sui futures
indice FMP, e il disallineamento della convenzione oraria fra futures ed ETF
(correlazione dei rendimenti 0.88 con volatilità identiche). **Una sola famiglia
di fonti per backtest.**

`scripts/validate_series.py` va eseguito su ogni serie nuova prima di usarla.

## Cosa è già stato escluso, e perché

Non ripetere questi test senza una ragione nuova.

* **Gann, angolo 1×1**: normalizzato in ATR per barra produce zero trade. La
  pendenza massima osservata in undici anni è 0.43-0.49 su tutti gli asset, mai
  sopra 0.5. Il prezzo diffonde come √t mentre una retta a pendenza fissa cresce
  come t: il rapporto va a zero come 1/√n, quindi la retta è irraggiungibile.
  Resa dimensionalmente coerente, l'ipotesi è vuota, non falsa.
* **Gann, ottavi**: 4/8 log, 5/8 log e il controllo 4/8 lineare danno tutti MAR
  0.67. Il 5/8 non batte il 4/8 e il logaritmo non cambia niente. Si riducono a
  "prezzo nella metà alta del range", che costa 0.20 di MAR.
* **Gann, Square of 9 e fan crossing**: scartati già in fase di ricerca
  (`research/state-of-the-art.md`).
* **Chikou come filtro**: blocca 0 ingressi su 1.728 barre di breakout. Un
  breakout a 55 barre implica close > massimo di 26 barre fa: è una tautologia.
* **Gate di regime HTF**: il filtro Ichimoku più dannoso, −0.21 di MAR. È il
  cardine di entrambe le strategie Pine.
* **`cloud_exit` come risultato del progetto**: in-sample batte il benchmark
  (MAR 1.15 contro 0.87) ed è stabile in 7 finestre su 8 e 5 fold su 5, ma il
  vantaggio non è distinguibile dal miglior rumore di ventidue tentativi — DSR
  0.025, PSR 0.829, IC 95% sul delta di MAR [−0.31, +0.82]. Va descritto come
  *non falsificato*, mai come confermato.
* **Cercare la ventitreesima ipotesi su questi dati.** Ogni ipotesi in più alza
  la soglia del DSR per tutte le precedenti: da N = 22 a N = 40 la soglia passa
  da 0.85 a 0.96 di Sharpe annuo. Continuare a cercare su questo campione rende
  più difficile, non più facile, dimostrare qualcosa.

## Questioni aperte

1. ~~Ichimoku come uscita~~, ~~Ichimoku simmetrico come segnale~~ e
   ~~validazione del candidato~~: **chiusi**. Le sette varianti battono il
   benchmark in-sample (`results/ichimoku_tests.md`), ma la validazione
   (`results/validation.md`) dice che il vantaggio non sopravvive:

   | | risultato |
   |---|---|
   | DSR del differenziale `cloud_exit` − benchmark, N = 22 | **0.025** |
   | PSR dello stesso differenziale, senza penalità per N | 0.829 |
   | delta MAR della procedura di selezione, fuori campione | **−0.04** |
   | ρ di rango fra classifica in-sample e out-of-sample | 0.14 |
   | IC 95% sul delta di MAR, bootstrap a blocchi | **[−0.31, +0.82]** |

   Il candidato *fisso* è stabile ovunque lo si misuri; la *procedura* che lo ha
   prodotto sceglie `cloud_exit` una volta su otto e non aggiunge valore. Le due
   affermazioni vanno tenute separate: la prima è ciò che ci si aspetta da una
   variante scelta con il senno di poi su tutto il periodo, la seconda è il test
   vero. `cloud_exit` resta utilizzabile — non fa mai danni — ma come ipotesi
   **non falsificata**, non come risultato.

2. **Portafoglio invece che segnale.** Il drawdown scende da 38.7% del peggior
   asset singolo a 8.9% di portafoglio a parità di segnale. Dopo la validazione
   è l'unica leva rimasta con un effetto più grande della sua incertezza: vale
   più di qualunque delta fra le ventidue varianti, e non dipende da una
   selezione. Con 15-20 strumenti e vol targeting scende ancora.

3. **Parity test contro il Pine.** Mai eseguito, e ora l'unica verifica aperta
   che non richieda di cercare un vantaggio nuovo. Richiede export CSV da
   TradingView degli stessi simboli, perché il parity ha senso solo se i due lati
   usano lo stesso feed — l'1.5% delle barre crypto differisce oltre il 2% fra
   due fonti diverse.

4. **Dati fuori campione veri.** Nessun test su questo campione può più
   distinguere un vantaggio di 0.28 di Sharpe annuo da zero: undici anni e sei
   asset non contengono l'informazione necessaria. L'unico modo di riaprire la
   domanda è allargare il campione — altri strumenti, o il tempo che passa — non
   un'altra statistica sugli stessi dati.

## Deviazioni note del porting

Dichiarate in `results/comparison.md`, nessuna favorisce il benchmark:
timeframe inferiore assente per la v3.2 (dati solo daily), regime HTF calcolato
sull'ultimo blocco chiuso invece che su quello in formazione (più conservativo),
`syminfo.mintick` sostituito da una soglia relativa.
