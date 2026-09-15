# tradingview — stato del progetto

Sistema di ricerca per strategie multi-asset basate su Ichimoku e Gann. Il
deliverable finale è Pine su TradingView; la validazione avviene in Python,
perché TradingView non espone API per lo Strategy Tester.

## Come ripartire in trenta secondi

```bash
pip install pandas numpy pytest
python3 -m pytest tests/ -q                      # 106 test, devono passare tutti
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
python3 scripts/run_parity.py --xlsx data/tradingview/*.xlsx   # motore contro Strategy Tester
python3 scripts/run_forward.py                   # registra le decisioni di oggi (append-only)
```

I dati sono già in `data/raw/`, puliti e verificati. Non serve rete per
rieseguire nulla.

## Il risultato, in tre righe

| | MAR | Sharpe | CAGR | maxDD | Trade |
|---|---|---|---|---|---|
| **Donchian 55/20** (benchmark, parametri Turtle mai ottimizzati) | **0.87** | 1.39 | 7.7% | 8.9% | 303 |
| Confluence v3.2 (54 input) | 0.51 | 1.02 | 3.4% | 6.6% | 115 |
| Sanyaku v5.5 (53 input) | 0.83 | **1.42** | 5.0% | 6.1% | 321 |

Periodo 2015-08-10 → 2026-09-14, sei asset, un solo set di parametri, costi per
asset. Sul MAR — la metrica primaria — nessuna delle due batte il benchmark, ma
i due margini non si assomigliano: la v3.2 è battuta nettamente, la **v5.5 no**,
e sullo Sharpe passa davanti (1.42 contro 1.39). Su BTC, l'asset su cui entrambe
sono state sviluppate, la v3.2 perde in casa (0.27 contro 0.65) mentre la v5.5
fa 0.73 ed è il suo asset migliore.

**Quello Sharpe non è un vantaggio, ed è stato misurato.** Sottoposta alla stessa
validazione delle altre ipotesi, la v5.5 è **falsificata**: gira a **0.64× la
volatilità del benchmark**, e a parità di volatilità il vantaggio è +0.05 di
Sharpe annuo contro una soglia di 0.89 — **DSR 0.003**, PSR 0.560. Lo Sharpe alto
veniva dal denominatore, non dal numeratore. Nel walk-forward a candidato fisso
fa 3/8 finestre positive con delta MAR mediano −0.36, e il bootstrap sulle
finestre concatenate dà P(delta ≤ 0) del 51%: una monetina. Dettaglio in
`results/validation.md`, sezione «Rifacimento con N = 24». Il numero precedente
(MAR 0.37) era comunque un difetto di misura, non della strategia — vedi
`results/comparison.md`.

Nessuno dei 15 componenti Ichimoku/Gann testati come filtro migliora il
benchmark. Sette varianti lo battono in-sample, ma **nessuna sopravvive alla
validazione fuori campione** (`results/validation.md`): il miglior candidato ha un
Deflated Sharpe di **0.074** sul differenziale a parità di volatilità contro il
benchmark, e la procedura che lo seleziona vale −0.10 di MAR fuori campione.
Dopo **ventiquattro** ipotesi — l'ultima delle quali è la strategia Pine da
cinquantatré input che il progetto doveva validare all'inizio — il benchmark è
ancora la cosa più difficile da battere.

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
   soglia si alza da sola. Con ventiquattro ipotesi il migliore per caso migliora
   comunque qualcosa — di quanto, lo dice `run_validation.py`.
   La ventitreesima è costata cara alle precedenti, ed è istruttivo: non è solo N
   a salire, è la **dispersione** dei tentativi. La ventiquattresima lo conferma
   dal lato opposto: mediocre e in mezzo alla distribuzione, ha lasciato la soglia
   dov'era (0.89) e il DSR di `cloud_exit` è perfino salito di un millesimo.
   Un'ipotesi estrema costa molto alle altre anche quando è sbagliata; una
   mediocre non costa quasi niente. Vale anche il contrario — un
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
  forward.py      registro append-only delle decisioni + sorveglianza (sola lettura)
  proposals.py    coda delle proposte: il solo canale da diagnosi a modifica
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

C'è anche `BTCUSDT_1d_binance.csv` (archivio ufficiale Binance, 3.316 barre dal
2017-08-17, nessun buco, gate superato), scaricato per il parity. **Non è in uso
nei runner**: comincia due anni dopo, quindi adottarlo accorcerebbe il periodo
comune da 2015-08 a 2017-08 — il 18% del campione — cambiando ogni numero
pubblicato.

La ragione per cui era stato scaricato («somiglia di più a TradingView») **non
vale più**, perché il deliverable non è Pine: la domanda da porsi il giorno in cui
si volesse operare non è quale fonte somigli a TradingView, ma su quale venue si
eseguirebbe davvero — e lì un singolo exchange batte un prezzo aggregato, che non
è negoziabile. È una scelta da fare allora, non adesso, e cambia il campione.

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
* **`sanyaku_v55`, la ventiquattresima ipotesi**: **falsificata.** La strategia
  Pine intera, entrata nel catalogo dopo che il parity test aveva corretto il
  blocco della pausa. In-sample fa MAR 0.83 e Sharpe **1.42 contro 1.39** del
  benchmark — l'unico numero del progetto che abbia mai battuto il benchmark su
  una metrica primaria. Non regge nessuna delle cinque prove: walk-forward fisso
  **3/8** finestre positive con delta MAR mediano **−0.36** (`cloud_exit` faceva
  7/8 e +0.27), k-fold purgato 3/5, differenziale grezzo **−0.86** di Sharpe
  annuo, e a parità di volatilità **+0.05 con DSR 0.003 e PSR 0.560**. Il
  bootstrap sulle finestre concatenate dà delta medio −0.02 e **P(delta ≤ 0) del
  51%**.
  La spiegazione è una sola: **gira a 0.64× la volatilità del benchmark**, e uno
  Sharpe si alza anche abbassando il denominatore. È l'**immagine speculare di
  `sizing_notional`**, che girava a 3.35× e aveva il differenziale grezzo più
  alto del progetto: una correva troppo, l'altra troppo poco, e la stessa
  correzione a parità di volatilità le uccide entrambe. Vedi
  `results/validation.md`, sezione «Rifacimento con N = 24».
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

4. **Parity test contro il Pine.** *Chiuso per quanto questi dati permettano*
   (`results/parity.md`, `scripts/run_parity.py`). Ha pagato due volte: ha trovato
   il blocco della pausa, che nessun altro controllo aveva visto, e poi ha smentito
   la mia stessa diagnosi del residuo.

   | configurazione | nostri ingressi | esatti | entro 2 giorni |
   |---|---|---|---|
   | default del Pine | 39 | 12/23 | 15/23 |
   | **preset «Conservative»** | **25** | **18/23** | **20/23** |

   Il residuo «39 ingressi contro 23» **non era un difetto di porting**: l'export
   si chiama «Conservative» perché è un *preset*, e sei input differiscono dai
   default, due dei quali spengono Entry 3 ed Entry 5. A default i nostri E1
   coincidono 10/10 ed E2 1/1, mentre E3 (20 ingressi) ed E5 (2) non coincidono
   **mai** — perché in quell'esecuzione non esistevano.

   **La regola che ne esce vale per ogni parity futuro: leggere il foglio
   `Properties` dell'export e costruire la strategia con quei valori, prima di
   confrontare qualunque cosa.** Il quinto foglio contiene ogni input usato; i
   primi quattro no, e da soli portano a una conclusione sbagliata.

   **Il residuo resta, ed è indipendente dal feed.** Ho proposto tre spiegazioni e
   le prime due sono state falsificate dalla misura. Scaricata la serie Binance
   ufficiale (`data/raw/BTCUSDT_1d_binance.csv`, 3.316 barre dal 2017-08-17, gate
   superato) e rifatto il confronto: **17/23 contro i 18/23 di Alpha Vantage**, a parità di harness —
   il venue esatto che TradingView dichiara non chiude il residuo, lo peggiora di
   uno. I tre ingressi scoperti sono **gli stessi su entrambi i feed**. Anche il
   warmup degli indicatori è stato escluso (era un difetto vero dell'harness,
   corretto, ma il conteggio non cambia).

   Nel farlo è emerso che **la misura dello scarto fra i feed era sbagliata**: il
   prezzo nella lista trade è il **fill**, cioè l'apertura della barra, non la
   chiusura. Contro il close dava mediana 1.40% e punte del 5.7%; contro
   l'apertura giusta dà **0.19% mediano e 1.05% massimo**. I due feed concordano
   fra loro e con TradingView entro due decimi di punto: non c'era nessuno scarto
   dietro cui nascondere la divergenza.

   Quel che resta è **una divergenza di porting isolata ma non diagnosticata**, e
   il profilo è che **anticipiamo**: TV entra il 2020-04-17, noi il 2020-04-09; TV
   il 2023-10-08, noi il 2023-10-02. Il disaccordo è su *quale barra la trinità si
   forma*, non sul fatto che si formi.

   **E lì resta, perché il deliverable non è più Pine.** Deciso il 2026-09-15: la
   strategia girerà in Python. Non c'è nessun Pine da eguagliare, quindi il
   residuo smette di essere un difetto da chiudere e diventa una differenza
   dichiarata fra il motore e lo script che lo ha ispirato. Andare oltre
   richiederebbe l'export degli indicatori barra per barra, e non servirebbe a
   niente che qualcuno debba usare. **Questa questione è chiusa, non sospesa.**

   Resta invece vivo quello che il parity ha **prodotto**, e che vale
   indipendentemente da TradingView: il bug della pausa era reale in qualunque
   riferimento — una strategia ferma per l'83% delle barre è rotta anche senza
   niente con cui confrontarla — e la regola sul foglio `Properties` vale per
   qualsiasi export si vorrà mai confrontare.

   Sopravvive anche il vincolo, che cambia solo di indirizzo: **ciò che esegue e
   ciò che è stato validato devono essere lo stesso oggetto.** Non era un fatto su
   TradingView, era un fatto sul metodo. In Python si applica alla configurazione
   che il runner costruisce, ed è la ragione per cui ogni riga del registro
   forward porta l'impronta di quella configurazione.

5. **Dati fuori campione veri.** Nessun test su questo campione può più
   distinguere un vantaggio di 0.28 di Sharpe annuo da zero: undici anni e sei
   asset non contengono l'informazione necessaria. L'unico modo di riaprire la
   domanda è allargare il campione — altri strumenti, o il tempo che passa — non
   un'altra statistica sugli stessi dati.

   *Dal 2026-09-15 il tempo che passa viene raccolto* invece che aspettato:
   `scripts/run_forward.py` registra ogni giorno la decisione e i suoi ingressi
   in `data/forward/decisioni.jsonl`, append-only e firmato.

   **Manca però il carburante, ed è il primo lavoro da fare.** `data/raw/` è
   statico e finisce al 2026-09-14: rilanciare il runner domani scrive *zero*
   righe, per sempre. Il registro esiste ma non può accumulare finché non c'è un
   passo che aggiorna le serie ogni giorno, con `validate_series.py` come gate e
   **una sola famiglia di fonti per asset** — cambiare fornitore a metà
   spezzerebbe la confrontabilità delle righe esattamente come la spezza un
   cambio di configurazione. Il sorvegliante si accorge del digiuno da solo
   («registro fermo da N giorni», dopo cinque), che è la prova che il meccanismo
   funziona e insieme la misura di quanto sia inutile senza dati freschi. **Nessun holdout
   ritagliato da questo campione è pulito** — è stato guardato tutto, più volte,
   e da un LLM che ha in addestramento l'esito di ogni evento fino al 2026. Quel
   registro è l'unico out-of-sample non contaminato che il progetto possa avere,
   e comincia a valere qualcosa fra qualche centinaio di barre, non domani.

6. ~~Validare la v5.5 come si è validato tutto il resto~~: **chiusa, con esito
   negativo.** Eseguita il 2026-09-15 con lo stesso identico protocollo del
   candidato in tutte e cinque le prove — non solo il DSR, perché confrontare due
   verdetti ottenuti con protocolli diversi non vuol dire niente.

   | prova | `cloud_exit` | **v5.5** |
   |---|---|---|
   | walk-forward fisso, delta MAR mediano | +0.27, 7/8 positivi | **−0.36**, 3/8 |
   | k-fold purgato, delta MAR mediano | +0.76, 5/5 | **+0.01**, 3/5 |
   | DSR a parità di volatilità | 0.075 | **0.003** |
   | PSR a parità di volatilità | 0.952 | **0.560** |
   | bootstrap, P(delta ≤ 0) | 20-30% | **51%** |

   La domanda era se il progetto avesse trovato qualcosa o solo riparato uno
   strumento. **Ha riparato uno strumento.** Lo Sharpe 1.42 era volatilità bassa
   (0.64× il benchmark), non vantaggio: riportato alla scala del benchmark vale
   +0.05 di Sharpe annuo contro una soglia di 0.89.

   Resta però vero, e vale più del verdetto, che il difetto è stato trovato dal
   **parity test** e da nient'altro: né la suite, né undici anni di backtest, né
   ventitré ipotesi lo avevano visto. È l'argomento più forte per chiudere la
   questione 4.

7. **Sorveglianza, sì; correzione automatica, no.** Il registro forward porta con
   sé `forward.anomalie()`, che segnala il silenzio prolungato di un asset e il
   cambio di impronta della configurazione. È **di sola lettura per costruzione**,
   e la distinzione non è di stile:
   * un sorvegliante che *legge, diagnostica, avvisa e al massimo ferma* è utile,
     e il silenzio è proprio l'allarme che sarebbe servito — la v5.5 aveva smesso
     di operare su CORN nel 2016 e nessuno se n'è accorto per undici anni di
     backtest, ventiquattro ipotesi e novantotto test;
   * un sorvegliante che *aggiusta i parametri* quando vede un drawdown viola la
     regola 6, rende non validabile ciò che esegue, e ha il difetto peggiore
     possibile nel tempismo: taglia l'esposizione dopo la perdita, cioè spesso
     subito prima del recupero.

   L'asimmetria è il criterio: **fermare fallisce verso il non fare niente,
   aggiustare fallisce verso il fare qualcosa che nessuno ha validato.**

   La terza via è costruita: `engine/proposals.py`, la coda. È il solo canale
   attraverso cui una diagnosi può diventare una modifica, e tre vincoli sono
   applicati dal codice invece che dalla buona volontà:
   * **nessuna proposta si applica da sola** — non esiste una funzione che
     accetti e modifichi, e un test verifica che non esista;
   * **accettare richiede di nominare l'ipotesi** che entrerà in
     `hypotheses.CATALOGUE`, perché una modifica accettata e non contata è
     un'ipotesi provata di nascosto e falsa il DSR di tutte le altre (regola 4);
   * **una decisione presa non si sovrascrive** — per tornarci sopra si apre una
     proposta nuova, così resta la traccia di entrambe.

   Le proposte nascono **vuote**: il sorvegliante sa dire che qualcosa non torna,
   non cosa cambiare, e un testo generato che *sembra* una diagnosi è peggio di un
   campo in bianco perché invita ad accettarlo senza guardarci.

## Deviazioni note del porting

Dichiarate in `results/comparison.md`, nessuna favorisce il benchmark:
timeframe inferiore assente per la v3.2 (dati solo daily), regime HTF calcolato
sull'ultimo blocco chiuso invece che su quello in formazione (più conservativo),
`syminfo.mintick` sostituito da una soglia relativa.

Una quarta deviazione è stata **trovata e corretta** il 2026-09-15, e questa
favoriva il benchmark: la pausa da perdite consecutive della v5.5 non scadeva
mai, perché il porting valutava la soglia a ogni barra invece che alla chiusura
di un trade e non azzerava il contatore come fa il Pine
(`ichimoku_sanyaku_v55.pine`, righe 133-137). La v5.5 risultava ferma dal 67% al
94% delle barre. È emersa dal parity test, non dalla suite: nessun test
verificava che una strategia restasse viva fino a fine serie. Adesso c'è
(`tests/test_strategies.py::test_la_pausa_dopo_le_perdite_non_e_definitiva`).
**Morale operativa: una strategia che opera poco va trattata come sospetta
finché non si è verificato che il silenzio sia una scelta e non un blocco.**
