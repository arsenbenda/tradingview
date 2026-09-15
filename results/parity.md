# Parity test: il motore contro lo Strategy Tester

Eseguito il 2026-09-15 con `scripts/run_parity.py`. Export dello Strategy Tester
su **BINANCE:BTCUSD, daily, 2020-01-03 → 2026-09-15**, in
`data/tradingview/sanyaku_v55_conservative_BTCUSD_2026-09-15.xlsx`.

```bash
python3 scripts/run_parity.py --xlsx data/tradingview/sanyaku_v55_conservative_BTCUSD_2026-09-15.xlsx
```

## Cos'era la domanda

Il porting della v5.5 riproduce il Pine? Undici anni di backtest, ventiquattro
ipotesi e novantotto test non rispondono a questa domanda: verificano che il
motore sia coerente con sé stesso, non che sia coerente con TradingView.

## La risposta, in due righe

| configurazione | nostri ingressi | esatti | entro 2 giorni | nostri in più |
|---|---|---|---|---|
| default del Pine | 39 | 12/23 | 15/23 | 24 |
| **preset «Conservative»** | **24** | **18/23** | **20/23** | **5** |

TradingView ne apre 23. **Il residuo che sembrava un difetto di porting era un
confronto fra due configurazioni diverse.**

## Quello che è costato di più: non aver letto il foglio Properties

L'export xlsx ha cinque fogli. I primi tre sono performance, il quarto è la lista
dei trade, il quinto è `Properties` — e contiene **il valore di ogni singolo
input** dell'esecuzione. Il primo confronto ha usato i primi quattro e ignorato
il quinto, e ha prodotto una conclusione sbagliata: «il motore apre 39 ingressi
contro 23, manca una condizione di blocco, è la direzione pericolosa».

Non mancava niente. Il file si chiama «Conservative» perché è un **preset**, e sei
input differiscono dai default del Pine:

| input | preset | default del Pine |
|---|---|---|
| Entry 3: Early TK weak buy | **Off** | On |
| Entry 5: Cloud reclaim | **Off** | On |
| HTF gate on continuation entries | **Off** | On |
| Entry 4 ignores zone lock | **Off** | On |
| Drawdown threshold | 12 | 15 |
| Risk reduction factor | 0.9 | 0.5 |

I due spegnimenti spiegano quasi tutto da soli. Scomposizione dei nostri 39
ingressi a default, per tipo:

| tipo | nostri | con corrispondenza in TV |
|---|---|---|
| E1 sanyaku | 10 | **10** |
| E2 rimbalzo Kijun | 1 | **1** |
| E3 TK precoce | 20 | **0** |
| E4 reclaim | 6 | 4 |
| E5 cloud reclaim | 2 | **0** |

E1 ed E2 coincidono al cento per cento; E3 ed E5 non coincidono mai, perché
nell'esecuzione di TradingView **non esistevano**. I due E4 scoperti sono il
`e4_bypass_lock` acceso da noi e spento nel preset.

**Regola che ne esce, e vale per ogni parity futuro: leggere il foglio
`Properties` e costruire la strategia con quei valori, prima di confrontare
qualunque cosa.** Le differenze che restano dopo sono le sole che parlano del
codice. È l'errore gemello di quello della pausa, in direzione opposta: là il
codice divergeva dal Pine e sembrava una scelta, qui il codice era giusto e
sembrava un difetto.

## Il residuo: reale, indipendente dal feed, non spiegato

Dopo la correzione della configurazione restano **3 ingressi di TradingView che
non produciamo** e 5-7 nostri che TradingView non ha. Ho proposto tre
spiegazioni e **le prime due sono state falsificate dalla misura**. Le lascio
scritte perché il modo in cui sono cadute è l'informazione utile.

**Prima ipotesi: «manca una condizione di blocco».** Falsificata dal foglio
`Properties`: era il preset. Vedi sopra.

**Seconda ipotesi: «è lo scarto fra Alpha Vantage e Binance».** Falsificata
scaricando Binance. Scaricata la serie BTCUSDT dall'archivio ufficiale
(`data/raw/BTCUSDT_1d_binance.csv`, 3.316 barre dal 2017-08-17, nessun buco,
gate di qualità superato) e rifatto il confronto:

| feed | esatti | entro 2 giorni | nostri in più |
|---|---|---|---|
| Alpha Vantage | **18/23** | 20/23 | 5 |
| Binance | 17/23 | 20/23 | 6 |

**Passare al venue esatto che TradingView dichiara non chiude il residuo — lo
peggiora di uno.** E i tre ingressi scoperti sono **gli stessi su entrambi i
feed**: 2020-02-22, 2020-04-17, 2023-10-08. Una divergenza che non si muove
cambiando fonte non è una divergenza di fonte.

Nel farlo è emerso che **anche la misura dello scarto fra i feed era sbagliata**.
Il prezzo nella lista trade di TradingView è il **fill**, cioè l'apertura della
barra d'ingresso, non la chiusura. Confrontato con il close dava mediana 1.40% ed
escursione fino al 5.7%, e mi aveva convinto che le fonti divergessero
abbastanza da spiegare tutto. Confrontato con l'apertura della stessa barra:

| riferimento | scarto assoluto mediano | massimo |
|---|---|---|
| close della barra | 1.40% | 5.71% |
| **apertura della barra** | **0.19%** | **1.05%** |

I due feed concordano fra loro e con TradingView entro due decimi di punto. Non
c'era nessun 5% da cui nascondersi.

**Terza ipotesi: «è il riscaldamento degli indicatori».** Falsificata anche
questa, ma ha trovato un difetto vero nell'harness. Il «backtesting range» di
TradingView dice da quando contare i trade, non da quando esistono gli
indicatori: sul grafico la nuvola è calda perché lo storico precedente è
caricato. Troncando la serie al 2020-01-03 Ichimoku partiva da NaN per ~78 barre,
e infatti sulla barra di segnale del 2020-02-22 `cloud_top` era NaN. Corretto —
`run_parity.py` ora carica 400 barre di warmup e confronta solo i trade dentro il
range — **il conteggio non cambia**: 18/23 restano 18/23.

### Dove sta davvero, allora

Il residuo si separa in due parti, e solo una è dei dati:

* **sensibile al feed** (si sposta di 1-2 giorni cambiando fonte): 2020-04-09 su
  Alpha Vantage contro 2020-04-10 su Binance, 2020-05-22 contro 2020-05-20;
* **indipendente dal feed** (identica su entrambi): i 3 ingressi di TradingView
  mai prodotti, più 3 nostri sempre in più — 2023-10-02 (E1), 2023-10-24 (E2),
  2024-05-21 (E4).

La seconda parte è una divergenza di porting, ed è ora **isolata ma non
diagnosticata**. Il profilo è che **anticipiamo**: TradingView entra il
2020-04-17, noi il 2020-04-09; TradingView entra il 2023-10-08, noi il
2023-10-02. Sul 2023-10-07 il prezzo è sopra la nuvola su entrambi i lati, ma il
nostro `e1` non scatta perché la trinità si era già formata prima — cioè il
disaccordo è su **quale barra la trinità si forma**, non sul fatto che si formi.

Per andare oltre serve confrontare **i valori degli indicatori barra per barra**,
non la lista dei trade: l'export OHLCV, o un export dei plot di Ichimoku da
TradingView. Con la sola lista trade questo è il punto di arresto.

## Una conseguenza che riguarda il resto del progetto

Il catalogo valida `sanyaku_v55` **nella configurazione di default del Pine**, che
è quella che `comparison.md` ha sempre misurato. Il preset «Conservative» è una
*strategia diversa*: tre meccanismi di ingresso invece di cinque, gate HTF spento,
circuit breaker più sensibile e meno aggressivo.

Non è stata validata, e non va confusa con quella che lo è stata. Se un giorno il
sistema dovesse operare, **la configurazione eseguita e quella validata devono
essere lo stesso oggetto** — e oggi sarebbero due. Misurare il preset sui sei
asset è legittimo, ma è una venticinquesima ipotesi e va contata come tale
(regola 4).
