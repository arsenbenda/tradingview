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

## Il residuo dopo la correzione: è il feed

Restano 3 ingressi di TradingView senza corrispondenza e 5 nostri in più. Tutti
si spiegano con lo scarto fra Alpha Vantage e Binance, che sulle 23 date di
TradingView ha **mediana +0.20% ma escursione da −3.75% a +5.63%**.

| ingresso TV non corrisposto | nostro close | scarto |
|---|---|---|
| 2020-02-22 | 9.667,52 | +0.45% |
| 2020-04-17 | 7.034,54 | **−1.85%** |
| 2023-10-08 | 27.932,44 | −0.30% |

E i nostri cinque in più non sono sparsi a caso: 2020-04-09 sta otto giorni prima
del 2020-04-17 di TradingView, 2023-10-02 sei giorni prima del 2023-10-08. Sono
**gli stessi eventi, su una barra diversa**, perché un attraversamento TK o di
nuvola cade su un giorno diverso quando i prezzi differiscono dell'1-2%.

Questo era già previsto in `data/README.md`: fonti diverse per lo stesso
strumento crypto non sono intercambiabili. Qui se ne vede il costo in unità
interpretabili: **su ventitré ingressi, tre cadono su una barra diversa.**

## Cosa si può e non si può concludere

**Si può dire** che nessuna divergenza *strutturale* di porting sopravvive al
confronto: nessun tipo di ingresso è sistematicamente scoperto, il numero di
posizioni aperte coincide (24 contro 23), e non c'è più un verso dell'errore.

**Non si può dire** che il porting sia identico. Con due feed diversi il parity
esatto non è raggiungibile nemmeno in linea di principio, e 18/23 è il massimo
che questo confronto possa produrre. Per passare da «nessuna divergenza visibile»
a «nessuna divergenza» serve l'export OHLCV di TradingView e una riesecuzione
sulle stesse barre. Quello resta aperto.

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
