# Benchmark: Donchian breakout, parametri Turtle

Eseguito il 2026-09-15. È la barra di riferimento per tutto ciò che viene dopo:
`scripts/run_benchmark.py`.

## Setup

Parametri identici su tutti e sei gli asset, **pubblicati e precedenti a questo
lavoro** (Turtle System 2), quindi senza alcun vantaggio di adattamento ai dati:
ingresso su breakout a 55 barre, uscita sul canale a 20, stop a 2×ATR(20),
rischio 1% per trade.

Periodo allineato al comune: **2015-08-10 → 2026-09-14** (11 anni).
Costi per asset, non globali; segnale alla chiusura di t, fill all'apertura di
t+1, size derivata dal prezzo di fill, fill pessimistici sui gap.

## Risultati — long/short, costi stimati

| Asset | Trade | CAGR | maxDD | MAR | Sharpe | PF | win% | avgR |
|---|---|---|---|---|---|---|---|---|
| BTC | 58 | 13.6% | 21.0% | 0.65 | 0.96 | 4.67 | 43% | 2.81 |
| ETH | 51 | 26.4% | 38.7% | 0.68 | 1.14 | 10.25 | 55% | 7.73 |
| GOLD | 44 | 2.6% | 13.4% | 0.19 | 0.49 | 2.25 | 30% | 0.70 |
| CRUDE | 46 | 2.3% | 12.4% | 0.19 | 0.50 | 1.89 | 28% | 0.62 |
| CORN | 53 | −0.0% | 13.1% | −0.00 | 0.02 | 0.99 | 30% | 0.01 |
| EQUITY | 51 | 0.3% | 10.7% | 0.02 | 0.10 | 1.11 | 39% | 0.07 |
| **PORTAFOGLIO** | **303** | **7.7%** | **8.9%** | **0.87** | **1.39** | **5.72** | 38% | 2.05 |

## Cosa dicono questi numeri

### 1. Il drawdown basso viene dalla diversificazione, non dal segnale

Peggior asset singolo: **38.7%** di drawdown. Portafoglio: **8.9%**. Stesso
segnale, stessi parametri, stesso periodo — l'unica differenza è che sono sei
asset poco correlati invece di uno. È la conferma numerica, sui dati di questo
progetto, che "DD ridotto" non è un obiettivo raggiungibile lavorando sulla
qualità dei segnali su un simbolo alla volta.

### 2. Il target PF 2.5 è già superato — e proprio per questo non è un buon target

Il portafoglio fa **PF 5.72** con DD 8.9%. Ma:

| | ETH | BTC |
|---|---|---|
| Miglior trade | R = 214, il 26.8% del profitto lordo | R = 58.6, il 31.7% |
| I 3 trade migliori | **65% del profitto lordo** | **54%** |

Sono trade reali (ETH febbraio–luglio 2017, BTC ottobre 2020–aprile 2021), non
artefatti. Ma un PF costruito su tre operazioni su cinquantuno non è una
statistica stabile: togli quei tre trade e la strategia è mediocre. È esattamente
la ragione per cui il PF va riportato e non inseguito, e per cui la metrica
primaria resta il MAR.

### 3. Il vincolo long-only costa quasi nulla su questo universo

| Scenario | CAGR | maxDD | MAR | Sharpe |
|---|---|---|---|---|
| Long/short | 7.7% | 8.9% | 0.87 | 1.39 |
| **Solo long** | 7.6% | 8.5% | **0.89** | **1.42** |

A livello di portafoglio il solo-long è marginalmente **migliore**. Questo
ridimensiona l'obiezione mossa alla v5.5 sul suo essere long-only: su questo
universo e su questo periodo, il lato short non ha aggiunto valore. Per asset il
quadro è misto — oro e crude migliorano senza short (MAR 0.33 e 0.31 contro 0.19
e 0.19), BTC ed ETH peggiorano di poco. L'obiezione resta valida in linea di
principio per un bear market prolungato sulle commodities, ma non è confermata
dai dati di questi undici anni.

### 4. Il trend following non funziona su tutto

CORN e EQUITY danno MAR ≈ 0: su questi due strumenti il Donchian non estrae
niente. Il portafoglio funziona perché BTC ed ETH lo trainano. Chi volesse
leggere il risultato come "il trend following funziona" sta guardando due asset
su sei.

### 5. Robusto ai costi

Raddoppiando i costi il MAR di portafoglio passa da 0.87 a 0.84. Con 303 trade in
undici anni su sei asset, i costi non sono il fattore limitante — il che è un
punto a favore dei sistemi a bassa frequenza.

### 6. Contro il buy & hold

| Asset | MAR strategia | MAR buy & hold |
|---|---|---|
| BTC | 0.65 | **0.80** |
| ETH | 0.68 | **1.15** |
| GOLD | 0.19 | **0.48** |
| CRUDE | **0.19** | 0.03 |
| CORN | −0.00 | −0.03 |
| EQUITY | 0.02 | **0.36** |
| Portafoglio | **0.87** | — |

Su quattro asset su sei il buy & hold batte la strategia anche corretto per il
rischio. Il trend follower vince solo dove il buy & hold è un disastro (crude,
con il suo 86.8% di drawdown). Il valore non sta nel battere il singolo asset:
sta nel fatto che **il portafoglio a MAR 0.87 con DD 8.9% è più investibile di
qualunque buy & hold della tabella**, che per ottenere MAR simili chiede di
sopportare drawdown dall'83% al 94%.

## La barra da battere

Qualunque cosa costruiremo con Ichimoku e Gann va confrontata con la riga
**PORTAFOGLIO**, sullo stesso periodo, con gli stessi costi e un solo set di
parametri:

> **CAGR 7.7% · maxDD 8.9% · MAR 0.87 · Sharpe 1.39 · PF 5.72 · 303 trade**

Non con il buy & hold, e non su BTC da solo.
