# tradingview — stato del progetto

Sistema di ricerca per strategie multi-asset basate su Ichimoku e Gann. Il
deliverable finale è Pine su TradingView; la validazione avviene in Python,
perché TradingView non espone API per lo Strategy Tester.

## Come ripartire in trenta secondi

```bash
pip install pandas numpy pytest
python3 -m pytest tests/ -q                      # 97 test, devono passare tutti
python3 scripts/run_benchmark.py                 # benchmark, i sei asset
python3 scripts/run_benchmark.py --universe extended   # gli stessi parametri sui quindici
python3 scripts/run_benchmark.py --universe no-crypto  # i tredici senza BTC ed ETH
python3 scripts/run_benchmark.py --risk 4              # la stessa cosa a rischio 4%/trade
python3 scripts/compare_strategies.py            # v3.2 e v5.5 contro il benchmark
python3 scripts/run_ablation.py                  # quali componenti aggiungono valore
python3 scripts/run_ichimoku_tests.py            # Ichimoku come segnale e come uscita
python3 scripts/run_validation.py                # walk-forward, k-fold purgato, DSR
python3 scripts/run_risk_walkforward.py          # il rischio per trade scelto fuori campione
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
benchmark. Sette varianti lo battono in-sample, ma **nessuna sopravvive alla
validazione fuori campione** (`results/validation.md`): il miglior candidato ha un
Deflated Sharpe di **0.074** sul differenziale a parità di volatilità contro il
benchmark, e la procedura che lo seleziona vale −0.10 di MAR fuori campione.
Dopo **ventitré** ipotesi, il benchmark è ancora la cosa più difficile da battere.

E il benchmark stesso, allargato a quindici strumenti, è **un risultato crypto**
(`results/universe_extended.md`): stesso segnale e stessi parametri su un universo
davvero eterogeneo fanno **MAR 0.61** contro 0.87, perché solo BTC ed ETH hanno un
vantaggio e nove strumenti su quindici sono negativi anche a costi zero. Tolte le
due crypto, i tredici che restano fanno **MAR 0.17 e CAGR 0.4%** solo long, e
perdono long/short: il rendimento del progetto sta tutto in due strumenti su
quindici.

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
   Il **rischio per trade è parte di quel set**: tutti i runner usano `risk_pct=0.01`.
   Non è ottimizzato, ed è tenuto fisso per due ragioni distinte. La prima è di
   misura: il MAR **lusinga la leva** — a leva pura lo Sharpe resta esattamente
   costante e il MAR sale lo stesso da 0.89 a 1.22 — quindi due MAR misurati a
   rischio diverso non sono confrontabili, mai. La seconda è che sopra il 2% quel
   parametro **non regola più il rischio**: il tetto sul capitale morde e il sizing
   proporzionale all'ATR viene sostituito da uno a nozionale costante (142 trade su
   178 a rischio 8%). Misure in `results/risk_walkforward.md`.
4. **Ogni ipotesi testata va contata.** Il conteggio non sta più a mano: è la
   lunghezza di `engine/hypotheses.CATALOGUE`, e da lì entra nel Deflated Sharpe.
   Aggiungere un'ipotesi significa aggiungere una riga a quel catalogo, e la
   soglia si alza da sola. Con ventitré ipotesi il migliore per caso migliora
   comunque qualcosa — di quanto, lo dice `run_validation.py`.
   La ventitreesima è costata cara alle precedenti, ed è istruttivo: non è solo N
   a salire, è la **dispersione** dei tentativi. Vale anche il contrario — un
   confronto **a parità di volatilità** restringe quella dispersione, e va fatto
   sempre, perché una variante che gira a tre volte la scala del benchmark ha un
   differenziale positivo per costruzione (`validation.volatility_matched`).
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
  data.py         caricamento con controlli bloccanti; CORE (6), EXTENDED (15),
                  NO_CRYPTO (13)
  filters.py      componenti da innestare sul benchmark (catalogo per l'ablazione)
  hypotheses.py   il catalogo di tutte le ipotesi provate; N_HYPOTHESES entra nel DSR
  validation.py   walk-forward, k-fold purgato con embargo, Deflated Sharpe, bootstrap
  strategies/     donchian (benchmark), sanyaku (v5.5), confluence (v3.2)
scripts/          runner riproducibili + estrattori dati + gate di qualità
strategies/       i due Pine originali, invariati
results/          benchmark_donchian.md, comparison.md, ablation.md,
                  ichimoku_tests.md, validation.md, universe_extended.md,
                  risk_walkforward.md
data/universe_declaration.md   la lista dei quindici, dichiarata prima dei dati
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
  vantaggio non è distinguibile dal miglior rumore di ventitré tentativi — DSR
  **0.074** a parità di volatilità (era 0.025 a N = 22 senza correzione di scala),
  PSR 0.952, IC 95% sul delta di MAR [−0.31, +0.82]. Va descritto come
  *non falsificato*, mai come confermato.
* **`sizing_notional`, la ventitreesima ipotesi**: **falsificata.** Posizione pari
  a tutto il capitale invece che a rischio/distanza dello stop. Sembrava viva a
  quattro livelli di misura diversi e non lo era a nessuno: MAR 1.27 in-sample
  (ma con maxDD 23% contro 8.9%, non confrontabile), differenziale grezzo il più
  alto del progetto con DSR 0.784 (ma gira a **3.35× la volatilità** del
  benchmark). A parità di volatilità il vantaggio passa da +1.43 a **+0.20** di
  Sharpe annuo — l'86% era scala — con **DSR 0.011**, PSR 0.750 e 2 asset su 6.
  Lo Sharpe che sale da 1.18 a 1.41 alzando `risk_pct` resta un fatto vero; non
  sopravvive al confronto a parità di rischio. Vedi `results/validation.md`,
  sezione «Rifacimento con N = 23».
* **Il portafoglio come leva di rendimento.** Allargare da sei a quindici
  strumenti dimezza il drawdown (8.9% → 4.1%) ma taglia il CAGR di due terzi
  (7.7% → 2.5%): il MAR **scende** a 0.61. La diversificazione riduce il rischio,
  non fabbrica rendimento, e con capitale equipesato ogni strumento senza
  vantaggio diluisce quelli che ce l'hanno. Vale in tutti e tre gli scenari di
  costo e direzione. **Con una correzione importante**: questo confronto è a
  rischio fisso 1% per trade, e il MAR *non* è invariante rispetto a quel numero —
  sale fino a un massimo intorno al 4-8% e poi ridiscende. A rischio 4% il divario
  è 1.50 contro 1.45, non 0.87 contro 0.61, e i quindici ci arrivano con metà del
  drawdown. Il divario non si inverte, ma si riduce di due terzi.
  Controprova diretta: i tredici senza crypto fanno MAR 0.17 solo long (0.21 a
  costi zero) e −0.03 long/short, e allungando il campione al 2013 — possibile
  solo senza ETH — scendono a 0.10. Non è il periodo e non sono i costi. E non è
  nemmeno il rischio per trade: al suo ottimo fuori campione i tredici arrivano a
  MAR 0.38 e CAGR 2.2% (`results/risk_walkforward.md`).
* **La leva come leva di rendimento.** A leva pura — stessi trade, rendimenti
  moltiplicati per k — lo Sharpe è **esattamente costante a 1.18** per k da 1 a 8,
  e il MAR sale da 0.89 a 1.22 solo per l'artefatto di misura. Non c'è pasto
  gratis. Quello che migliora davvero lo Sharpe (1.18 → 1.41) alzando `risk_pct`
  è un'altra cosa: il tetto sul capitale che sostituisce il sizing ATR con uno a
  nozionale costante. Vedi la questione aperta 5.
* **Cercare la ventiquattresima ipotesi su questi dati.** Ogni ipotesi in più
  alza la soglia del DSR per tutte le precedenti, e la ventitreesima l'ha
  dimostrato sul campo: la soglia del differenziale grezzo è passata da 0.85 a
  **1.19** di Sharpe annuo, e il DSR di `cloud_exit` da 0.025 a 0.001, per il solo
  fatto di aver provato una cosa in più. Continuare a cercare su questo campione
  rende più difficile, non più facile, dimostrare qualcosa.

## Questioni aperte

1. ~~Ichimoku come uscita~~, ~~Ichimoku simmetrico come segnale~~ e
   ~~validazione del candidato~~: **chiusi**. Le sette varianti battono il
   benchmark in-sample (`results/ichimoku_tests.md`), ma la validazione
   (`results/validation.md`) dice che il vantaggio non sopravvive:

   | | risultato |
   |---|---|
   | DSR del differenziale `cloud_exit` − benchmark, N = 23, a parità di volatilità | **0.074** |
   | PSR dello stesso differenziale, senza penalità per N | 0.952 |
   | delta MAR della procedura di selezione, fuori campione | **−0.10** |
   | ρ di rango fra classifica in-sample e out-of-sample, mediana | +0.02 |
   | IC 95% sul delta di MAR, bootstrap a blocchi | **[−0.31, +0.82]** |

   Il candidato *fisso* è stabile ovunque lo si misuri; la *procedura* che lo ha
   prodotto sceglie `cloud_exit` una volta su otto e non aggiunge valore. Le due
   affermazioni vanno tenute separate: la prima è ciò che ci si aspetta da una
   variante scelta con il senno di poi su tutto il periodo, la seconda è il test
   vero. `cloud_exit` resta utilizzabile — non fa mai danni — ma come ipotesi
   **non falsificata**, non come risultato.

2. ~~Portafoglio invece che segnale~~: **chiuso, con esito negativo**
   (`results/universe_extended.md`). Era l'ultima leva che sembrava funzionare, ed
   era l'unica non ancora misurata. Misurata, fa così:

   | | sei | quindici |
   |---|---|---|
   | MAR | **0.87** | **0.61** |
   | Sharpe | 1.39 | 0.85 |
   | CAGR | 7.7% | 2.5% |
   | maxDD | 8.9% | **4.1%** |

   Il drawdown scende come previsto; il rendimento crolla, perché **due strumenti
   su quindici hanno un vantaggio e sono le due crypto**. Gli altri tredici stanno
   fra −2.0% e +2.6% di CAGR, e restano negativi anche azzerando i costi. Lo 0.87
   contro cui sono state misurate tutte e ventidue le ipotesi non è la performance
   di un trend follower multi-asset: è BTC ed ETH con quattro strumenti quasi
   neutri intorno.

   La controprova, `--universe no-crypto`, lo misura a livello di portafoglio: i
   tredici non-crypto, l'86% del capitale, fanno **MAR 0.17 / CAGR 0.4% solo
   long** e **MAR −0.03 long/short**. Il vincolo long-only vale 0.20 di MAR qui
   contro 0.13 sui quindici, perché senza crypto lo short non ha più niente da
   compensare. A costi zero 0.21, e sul campione più lungo (2013, possibile solo
   togliendo ETH) 0.10: né le frizioni né il periodo. **Undici anni di
   obbligazionario, valute, azionario globale, immobiliare e materie prime non
   producono con Donchian 55/20 nulla di distinguibile da zero.**

3. ~~Sizing a nozionale costante contro sizing proporzionale all'ATR~~:
   **chiusa, falsificata.** Aggiunta al catalogo come `sizing_notional`, ventitreesima
   ipotesi, e passata dal DSR con N = 23 (`results/validation.md`, sezione
   «Rifacimento con N = 23»). A parità di volatilità il vantaggio è +0.20 di
   Sharpe annuo con DSR 0.011: l'86% di quello che sembrava vantaggio era scala.
   Rimane vero, e va tenuto a mente, che **alzare `risk_pct` sopra il 2% non alza
   il rischio ma cambia regola di sizing** — il tetto sul capitale morde su 142
   trade su 178 — e che il rischio per trade resta all'1% in tutti i runner.
   Il costo della prova è registrato: la soglia del DSR è salita per tutte le
   ventidue ipotesi precedenti.

4. **Parity test contro il Pine.** Mai eseguito, e ora l'unica verifica aperta
   che non richieda di cercare un vantaggio nuovo. Richiede export CSV da
   TradingView degli stessi simboli, perché il parity ha senso solo se i due lati
   usano lo stesso feed — l'1.5% delle barre crypto differisce oltre il 2% fra
   due fonti diverse.

5. **Dati fuori campione veri.** Nessun test su questo campione può più
   distinguere un vantaggio di 0.28 di Sharpe annuo da zero: undici anni e sei
   asset non contengono l'informazione necessaria. L'unico modo di riaprire la
   domanda è allargare il campione — altri strumenti, o il tempo che passa — non
   un'altra statistica sugli stessi dati.

## Deviazioni note del porting

Dichiarate in `results/comparison.md`, nessuna favorisce il benchmark:
timeframe inferiore assente per la v3.2 (dati solo daily), regime HTF calcolato
sull'ultimo blocco chiuso invece che su quello in formazione (più conservativo),
`syminfo.mintick` sostituito da una soglia relativa.
