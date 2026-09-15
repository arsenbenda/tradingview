# v3.2 e v5.5 contro il benchmark

Eseguito il 2026-09-15 con `scripts/compare_strategies.py`. Stesso periodo
(2015-08-10 → 2026-09-14), stessi costi per asset, un solo set di parametri,
stesso motore di esecuzione.

## Risultato

| Strategia | Trade | CAGR | maxDD | MAR | Sharpe | PF | Esposizione |
|---|---|---|---|---|---|---|---|
| **Donchian 55/20** (benchmark) | 303 | **7.7%** | 8.9% | **0.87** | **1.39** | 5.72 | 54% |
| Confluence v3.2 | 115 | 3.4% | 6.6% | 0.51 | 1.02 | 7.18 | 26% |
| Sanyaku v5.5 | 76 | 2.1% | 5.7% | 0.37 | 0.93 | 8.09 | 16% |

**Nessuna delle due batte il benchmark.** L'ordine è netto e non ambiguo:
Donchian 0.87 → v3.2 0.51 → v5.5 0.37 sul MAR, e identico sullo Sharpe.

Fra le due, la v3.2 è chiaramente migliore della v5.5: MAR più alto su cinque
asset su sei, e l'unica delle due che estrae qualcosa da CORN.

### Il dettaglio che pesa di più

Su **BTC**, l'asset su cui entrambe sono state sviluppate — e su cui la v3.2 ha
esplicitamente calibrato le patch della v3.2 guardando le perdite del 2021-2024
— il benchmark fa MAR **0.65** contro **0.27** della v3.2 e **0.33** della v5.5.
Perdono in casa, sul campione da cui sono nate.

### Il profit factor alto non è una buona notizia

v5.5 ha PF 8.09 e v3.2 7.18, contro 5.72 del benchmark. Ma l'esposizione è 16% e
26% contro 54%: stanno fuori dal mercato quasi sempre, e quando entrano scelgono
bene. Il PF premia la selettività e ignora il capitale fermo; il MAR no. È la
dimostrazione pratica del perché il PF non può essere la metrica obiettivo —
**la strategia con il PF più alto delle tre è la peggiore delle tre.**

## Scomposizione della v5.5 per tipo di ingresso

| Ingresso | Trade | win% | avgR | PnL totale |
|---|---|---|---|---|
| E1 Sanyaku | 23 | 35% | 5.54 | **147.457** |
| E2 rimbalzo Kijun | 5 | 20% | 3.82 | 21.647 |
| E3 TK precoce | 30 | 33% | 0.76 | 11.667 |
| **E4 reclaim** | **15** | **20%** | **0.23** | **1.776** |
| E5 cloud reclaim | 3 | 67% | 7.32 | 16.347 |

**E1 da solo produce il 73% del profitto.** E3 è l'ingresso più frequente e il
terzo per contributo. E4 — quello che aggira cooldown e zone lock, segnalato
come rischioso prima di misurarlo — produce 15 trade al 20% di vittorie per
1.776 di PnL complessivo: rumore che consuma capitale e occupa lo slot di
posizione. Su cinque meccanismi di ingresso, uno paga e uno è da togliere.

## Una previsione sbagliata, da registrare

Avevo indicato come difetto serio il fatto che entrambe calcolino quantità e
stop sul close della barra di segnale mentre il fill avviene all'apertura
successiva, misurando su USO uno scarto mediano dello 0.774% con un giorno su
sette oltre il 2%.

Misurato in esecuzione, il difetto **non cambia il risultato**: v5.5 con size al
fill e con size al close di segnale danno lo stesso identico MAR di 0.37. La
ragione è che queste strategie operano pochissimo proprio sugli asset dove lo
scarto è grande — 6 trade su CRUDE, 5 su CORN in undici anni. Il difetto è reale
e andrebbe corretto in ogni caso, ma su queste due strategie non costa nulla, e
sostenere il contrario sarebbe stato un errore.

## Deviazioni dichiarate del porting

1. **Timeframe inferiore assente (v3.2).** Il Pine deriva un LTF a 6 ore da un
   grafico daily e lo usa in `ltfConfirms`, che entra nello score. Con dati
   daily quel timeframe non esiste: `ltfConfirms` è sempre falso e la componente
   si riduce a `nearTimeWindow`. Il timing LTF di ingresso e uscita è
   disattivato per default nel Pine, quindi lì non cambia nulla.
2. **Regime HTF sull'ultimo blocco chiuso (v3.2).** Il Pine usa `lookahead_off`,
   che espone il blocco a 5 giorni in formazione; qui si usa l'ultimo blocco
   completo. Più conservativo, mai anticipatorio, con reattività inferiore fino
   a quattro barre.
3. **`syminfo.mintick` non esiste fuori da TradingView.** I test di Kijun e
   Senkou B piatti usano una soglia relativa allo 0.01% del prezzo.

Nessuna delle tre favorisce il benchmark: la prima toglie al massimo un punto di
score alla v3.2, la seconda la rende più lenta, la terza è neutra.

## Osservazione sul codice, emersa dal porting

Negli ingressi di continuazione della v3.2 nessun setup è attivo, quindi
`setupBull` è falso e lo stop viene preso da `cloudTop` invece che da
`cloudBot`. Con prezzo sopra la nuvola il risultato è uno stop più stretto, non
un errore di direzione — ma è un comportamento che nasce da un valore di default
e non da una scelta, e infatti i trade CON risultano avere un profilo di rischio
diverso dai REV senza che nulla lo dichiari.

## Conclusione

La domanda posta all'inizio era se una macchina a 53-54 input battesse cinquanta
righe con parametri pubblicati negli anni Ottanta, a parità di periodo, costi e
un solo set di parametri. La risposta misurata è **no**, per entrambe, con un
margine ampio e nella stessa direzione su ogni metrica che tiene conto del
capitale impiegato.
