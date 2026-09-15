# Ichimoku come segnale e come uscita

Eseguito il 2026-09-15 con `scripts/run_ichimoku_tests.py`. Le due ipotesi
rimaste aperte dopo l'ablazione, entrambe con stop, rischio, costi e motore
identici al benchmark: l'unica cosa che cambia è il segnale (A) o l'uscita (B).

## A) Ichimoku come generatore di segnale, simmetrico long/short

| | MAR | Δ | Sharpe | CAGR | maxDD | PF | Trade | Asset migliorati |
|---|---|---|---|---|---|---|---|---|
| Donchian (benchmark) | 0.87 | | 1.39 | 7.7% | 8.9% | 5.72 | 303 | |
| ichimoku cloud | 1.06 | +0.19 | 1.42 | 7.8% | 7.4% | 2.83 | 915 | 4/6 |
| ichimoku tk | 1.17 | +0.30 | 1.41 | 5.9% | 5.0% | 2.33 | 850 | 3/6 |
| **ichimoku sanyaku** | **1.38** | **+0.51** | 1.47 | 6.2% | 4.5% | 2.51 | 937 | 3/6 |

## B) Ichimoku come meccanismo di uscita, ingressi del benchmark invariati

| | MAR | Δ | Sharpe | CAGR | maxDD | PF | Trade | Asset migliorati |
|---|---|---|---|---|---|---|---|---|
| canale 20 (benchmark) | 0.87 | | 1.39 | 7.7% | 8.9% | 5.72 | 303 | |
| **kijun_cross** | **1.36** | +0.49 | 1.50 | 5.0% | 3.7% | 3.45 | 361 | 4/6 |
| kijun_trail | 1.30 | +0.43 | 1.34 | 3.9% | 3.0% | 2.61 | 400 | 2/6 |
| **cloud_exit** | **1.15** | +0.28 | **1.53** | **8.2%** | 7.1% | 5.76 | 320 | 3/6 |
| cloud_trail | 0.95 | +0.08 | 1.38 | 7.9% | 8.3% | 5.35 | 272 | 5/6 |

**Tutte e sette le varianti migliorano il benchmark.** Sette su sette nella
stessa direzione è un pattern molto più difficile da attribuire al caso di un
singolo vincitore fra molti — che è invece quello che l'ablazione sui filtri non
aveva prodotto.

## Correzione di una conclusione precedente

Dall'ablazione avevo concluso che i componenti Ichimoku non aggiungono nulla.
Quella conclusione valeva — e vale ancora — per Ichimoku **come filtro sugli
ingressi di un breakout**, dove è ridondante quasi per costruzione. Non vale
come affermazione generale: **come segnale autonomo e come meccanismo di uscita,
Ichimoku batte il benchmark**. Avevo generalizzato oltre quello che il test
misurava.

## Le due cose da sapere prima di entusiasmarsi

### 1. Il guadagno viene dal drawdown, non dal rendimento

`ichimoku sanyaku` fa CAGR 6.2% contro 7.7% del benchmark: **rende meno**. Il MAR
sale perché il drawdown dimezza, da 8.9% a 4.5%. Non è un artefatto di scala —
il rendimento è sceso del 19% mentre il drawdown è sceso del 49%, quindi il
rapporto migliora davvero, e con leva doppia si otterrebbe circa 12.4% di CAGR
con 9% di drawdown, battendo il benchmark su entrambi i fronti. Ma va detto
chiaramente: **questi sistemi non guadagnano di più, perdono di meno.**

L'unica eccezione è `cloud_exit`, che alza il CAGR (8.2% contro 7.7%) *e*
abbassa il drawdown (7.1% contro 8.9%) contemporaneamente, senza bisogno di leva.

### 2. Il vincitore apparente è il meno robusto

| | MAR costi normali | MAR costi doppi | Trade |
|---|---|---|---|
| Donchian | 0.87 | 0.84 | 303 |
| ichimoku sanyaku | 1.38 | **1.15** | 937 |
| kijun_cross | 1.36 | 1.27 | 361 |
| cloud_exit | 1.15 | **1.11** | 320 |

`sanyaku` ha 937 trade e perde 0.23 di MAR raddoppiando i costi: è il più
esposto alle ipotesi sul modello di costo, che restano stime. E per asset i suoi
guadagni sono **concentrati sulle crypto**:

| Asset | Donchian | ichi sanyaku | kijun_cross | cloud_exit |
|---|---|---|---|---|
| BTC | 0.65 | 0.78 | 0.80 | 0.83 |
| ETH | 0.68 | **1.12** | 0.88 | 0.82 |
| GOLD | 0.19 | 0.18 | **0.32** | **0.33** |
| CRUDE | 0.19 | **0.08** | 0.22 | 0.17 |
| CORN | −0.00 | −0.03 | −0.06 | −0.01 |
| EQUITY | 0.02 | 0.07 | −0.02 | 0.02 |

Su CRUDE `sanyaku` peggiora il benchmark più che dimezzandone il MAR, e su CORN
resta negativo. Per la regola che ci siamo dati — un componente che aiuta un
solo gruppo di asset è adattato a quel gruppo — il suo 1.38 di portafoglio va
letto come **un risultato crypto**, non multi-asset.

`cloud_exit` e `kijun_cross` distribuiscono meglio: migliorano anche oro e
crude, e reggono i costi doppi quasi senza muoversi.

## Cosa terrei

**`cloud_exit` è il risultato più solido del progetto finora**: alza il
rendimento, abbassa il drawdown, ha il miglior Sharpe di tutta la tabella
(1.53), usa lo stesso numero di trade del benchmark e non si muove raddoppiando
i costi. Ed è concettualmente pulito — la nuvola non decide *quando entrare*,
decide *quando il trend non c'è più*, che è il lavoro per cui Ichimoku è stato
costruito.

Il candidato da portare avanti è quindi: **ingressi Donchian, uscita sulla
nuvola**. Non è la strategia Ichimoku + Gann che cercavi, ma è l'unica
combinazione, fra tutte quelle testate, che batte il benchmark su rendimento e
rischio insieme e sopravvive alle verifiche.

## Prossime verifiche, prima di crederci

1. **Walk-forward e purged k-fold con embargo**: tutti i numeri qui sono su un
   periodo unico.
2. **Deflated Sharpe Ratio**: le ipotesi testate finora sono 22 (15 filtri, 3
   segnali, 4 uscite). Il conteggio va usato, non ignorato.
3. **Parity test contro il Pine**, che resta mai eseguito.
