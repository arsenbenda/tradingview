# v3.2 e v5.5 contro il benchmark

Eseguito il 2026-09-15 con `scripts/compare_strategies.py`. Stesso periodo
(2015-08-10 → 2026-09-14), stessi costi per asset, un solo set di parametri,
stesso motore di esecuzione.

> **Rifatto il 2026-09-15, dopo la correzione di un difetto del porting.** La
> pausa da perdite consecutive della v5.5 non scadeva mai: il Pine valuta la
> soglia alla chiusura di un trade e azzera il contatore quando arma la pausa
> (`ichimoku_sanyaku_v55.pine`, righe 133-137), il porting la valutava a ogni
> barra e non azzerava. Raggiunte cinque perdite, ogni barra riarmava la pausa,
> nessun trade poteva aprirsi, e quindi il contatore non tornava mai sotto la
> soglia. La v5.5 era **ferma dal 67% al 94% delle barre** a seconda dell'asset
> e smetteva di operare anni prima della fine del periodo: CORN nel 2016, CRUDE
> nel 2017, BTC e GOLD nel 2018, ETH nel 2019. I 76 trade della versione
> precedente di questo documento erano quasi tutti anteriori al blocco.
>
> Il difetto è emerso dal confronto con l'export dello Strategy Tester su
> BINANCE:BTCUSD 2020-2026: la lista dei trade di TradingView arrivava al 2026,
> la nostra si fermava all'aprile 2022. **Tre conclusioni di questo documento
> erano artefatti del blocco e sono ritirate qui sotto**, segnalate una per una.
> Il catalogo delle ventitré ipotesi non è toccato — `donchian`, `ichimoku_tf` e
> `filters` non istanziano `SanyakuV55` — quindi ablazione, test Ichimoku,
> validazione/DSR e universo esteso restano invariati.

## Risultato

| Strategia | Trade | CAGR | maxDD | MAR | Sharpe | PF | Esposizione |
|---|---|---|---|---|---|---|---|
| **Donchian 55/20** (benchmark) | 303 | **7.7%** | 8.9% | **0.87** | **1.39** | 5.72 | 54% |
| Confluence v3.2 | 115 | 3.4% | 6.6% | 0.51 | 1.02 | 7.18 | 26% |
| Sanyaku v5.5 | 321 | 5.0% | 6.1% | 0.83 | **1.42** | 4.90 | 57% |

**Nessuna delle due batte il benchmark sul MAR**, che è la metrica primaria:
Donchian 0.87 → v5.5 0.83 → v3.2 0.51. Ma il margine sulla v5.5 è di 0.04, cioè
niente, e **sullo Sharpe l'ordine si inverte**: 1.42 della v5.5 contro 1.39 del
benchmark. La v5.5 arriva a quel risultato con meno rendimento (5.0% contro
7.7%) e meno drawdown (6.1% contro 8.9%): non è una versione migliore dello
stesso motore, è un motore più lento e più liscio.

*Ritirata la prima conclusione.* La versione precedente diceva che l'ordine era
«netto e non ambiguo» e «identico sullo Sharpe». Con la pausa corretta non è né
netto né identico: sul MAR è un sostanziale pareggio, sullo Sharpe la v5.5 è
davanti.

*Ritirata la seconda.* Diceva che «fra le due, la v3.2 è chiaramente migliore
della v5.5». È il contrario: la v5.5 ha MAR più alto su quattro asset su sei
(BTC, ETH, GOLD, CRUDE), pareggia su EQUITY e perde solo su CORN. Restava vero
che la v3.2 è l'unica a estrarre qualcosa da CORN, e resta vero adesso.

Va detto con chiarezza cosa questo **non** è. La v5.5 è stata sviluppata su
questi dati e non è mai passata dalla macchina di validazione che ha bocciato le
ventitré ipotesi: nessun DSR, nessun walk-forward, nessun k-fold purgato. Uno
Sharpe in-sample di 1.42 contro 1.39, dopo una correzione che ha cambiato il
numero di 0.49, è esattamente il tipo di risultato che la regola 7 dice di non
chiamare risultato.

### Il dettaglio che pesa di più

*Ritirata la terza conclusione.* La versione precedente diceva che entrambe
«perdono in casa, sul campione da cui sono nate». Su **BTC** — l'asset su cui
entrambe sono state sviluppate, e su cui la v3.2 ha calibrato le sue patch
guardando le perdite del 2021-2024 — il benchmark fa MAR **0.65** contro
**0.27** della v3.2 e **0.73** della v5.5. La v3.2 perde in casa; la v5.5 no, e
anzi BTC è il suo asset migliore.

La v5.5 batte il benchmark su tre asset su sei: BTC (0.73 contro 0.65), GOLD
(0.40 contro 0.19) ed EQUITY (0.28 contro 0.02). Perde su ETH (0.39 contro
0.68), CRUDE (0.11 contro 0.19) e CORN (−0.08 contro −0.00). Per la regola 5,
tre su sei è il minimo che impedisca di chiamarlo un filtro adattato a un asset
— ed è anche il massimo che si possa dire senza validarlo.

### Il profit factor alto non è una buona notizia

La v3.2 ha PF 7.18 contro 5.72 del benchmark e 4.90 della v5.5. Ma la sua
esposizione è 26% contro 54% e 57%: sta fuori dal mercato tre volte su quattro,
e quando entra sceglie bene. Il PF premia la selettività e ignora il capitale
fermo; il MAR no. È la dimostrazione pratica del perché il PF non può essere la
metrica obiettivo — **la strategia con il PF più alto delle tre è la peggiore
delle tre.**

La correzione della pausa rafforza questo punto invece di indebolirlo. Prima era
la v5.5 ad avere il PF più alto (8.09) con l'esposizione più bassa (16%), ed
entrambi i numeri erano prodotti dal blocco: una strategia ferma per l'85% delle
barre è selettiva per costruzione. Sbloccata, l'esposizione sale al 57%, il PF
scende a 4.90 — sotto quello del benchmark — e il MAR raddoppia. Il PF si è
mosso nella direzione opposta alla qualità, come previsto.

## Scomposizione della v5.5 per tipo di ingresso

| Ingresso | Trade | win% | avgR | PnL totale |
|---|---|---|---|---|
| E1 Sanyaku | 90 | 32% | 3.06 | **406.565** |
| E2 rimbalzo Kijun | 10 | 10% | 1.66 | 19.158 |
| E3 TK precoce | 147 | 29% | 0.61 | 76.401 |
| E4 reclaim | 60 | 28% | 1.54 | 51.641 |
| E5 cloud reclaim | 14 | 43% | 1.68 | 17.583 |

**E1 da solo produce il 71% del profitto**, ed è l'unica affermazione della
versione precedente di questa sezione che sopravvive. E3 resta l'ingresso più
frequente — 147 trade, il 46% del totale — e il secondo per contributo con un
avgR di 0.61, il più basso dei cinque.

*Ritirata anche questa.* La versione precedente concludeva che «su cinque
meccanismi di ingresso, uno paga e uno è da togliere», indicando E4 come rumore
sulla base di 15 trade al 20% di vittorie per 1.776 di PnL. Con la pausa
corretta E4 fa 60 trade al 28% con avgR 1.54 e 51.641 di PnL: il 9% del totale,
il terzo contributo dei cinque, e positivo. La conclusione era un artefatto del
campione ridotto dal blocco — quindici trade non bastavano a distinguere un
meccanismo inutile da uno mediocre, e il segno era sbagliato. **Nessuno dei
cinque ingressi risulta da togliere.**

## Una previsione sbagliata, da registrare

Avevo indicato come difetto serio il fatto che entrambe calcolino quantità e
stop sul close della barra di segnale mentre il fill avviene all'apertura
successiva, misurando su USO uno scarto mediano dello 0.774% con un giorno su
sette oltre il 2%.

Misurato in esecuzione, il difetto **non cambia il risultato**: v5.5 con size al
fill e con size al close di segnale danno lo stesso MAR di 0.83, lo stesso
Sharpe di 1.42 e lo stesso drawdown, su 321 e 314 trade rispettivamente.

La conclusione regge, la spiegazione che le avevo dato no. Dicevo che il difetto
non costava nulla perché «queste strategie operano pochissimo proprio sugli
asset dove lo scarto è grande — 6 trade su CRUDE, 5 su CORN in undici anni».
Quei numeri erano il blocco: sbloccata, la v5.5 fa 57 trade su CRUDE e 65 su
CORN, dieci volte tanto, e il MAR resta identico lo stesso. Il difetto è reale e
andrebbe corretto in ogni caso, ma su queste due strategie non costa nulla — e
adesso lo si può dire per la ragione giusta, cioè che lo scarto fra close di
segnale e apertura successiva è simmetrico e si annulla su molte ripetizioni,
non perché le ripetizioni fossero poche.

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
un solo set di parametri. La risposta misurata è **no** sul MAR, per entrambe —
ma con due margini molto diversi: ampio per la v3.2 (0.51 contro 0.87),
trascurabile per la v5.5 (0.83 contro 0.87), che anzi sullo Sharpe passa davanti.

La versione precedente di questa conclusione diceva «con un margine ampio e
nella stessa direzione su ogni metrica». Era vero dei numeri che aveva, e quei
numeri misuravano una strategia spenta per la maggior parte del periodo. La
risposta onesta oggi è più stretta e meno soddisfacente: **la v3.2 è battuta, la
v5.5 non è distinguibile dal benchmark su questo campione**, e per sapere se sia
qualcosa di più servirebbe sottoporla alla stessa validazione delle ventitré
ipotesi — che è l'unica cosa che qui non è ancora stata fatta.
