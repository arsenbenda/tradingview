# Pre-registrazione — Peak-AVWAP come gate sugli ingressi

**Scritta e committata prima di eseguire il test.** Il commit che introduce questo
file non contiene risultati; quello successivo li aggiunge senza modificare
niente qui sopra la riga di verdetto.

## Da dove viene l'ipotesi

Dalla decomposizione dello script TradingView `IQ Dual Anchor Setup [IQ-TRADER]`
(invite-only, sorgente non leggibile, `script_type: study`, quindi senza alcun
risultato di Strategy Tester). Delle quattro componenti che la descrizione
dichiara, tre appartengono a famiglie già misurate in questo progetto:

| componente | stato |
|---|---|
| trendline discendente da uno swing high, in log | famiglia dei fan di Gann (pendenza qui fittata, non fissa) |
| livelli Fibonacci trough→peak in log | ottavi log 4/8 e 5/8 + controllo lineare: MAR 0.67 contro 0.87 |
| corridoio in compressione, poi rottura con volume | breakout + gate di volatilità |
| **Peak-AVWAP che passa da resistenza a supporto** | **non presente fra le 22 ipotesi** |

Solo la quarta è nuova, ed è l'unica cosa testabile: è una media pesata sui
**volumi reali**, informazione che né Ichimoku né Gann guardano.

## Specifica esatta, fissata adesso

* **Àncora.** La barra del massimo `high` nelle `LOOKBACK = 50` barre che
  terminano in `t-1`. Il 50 è il default dichiarato dall'autore (range 10–500),
  **non** un valore scelto da noi: scegliendolo introdurremmo un grado di
  libertà. Non verranno provati altri lookback.
* **Finestra spostata di una barra**, come i canali di Donchian: l'àncora non
  può dipendere dalla barra su cui si decide.
* **AVWAP.** Da quella barra in avanti, cumulativa:
  `Σ(tp·volume) / Σ(volume)` con `tp = (high+low+close)/3` (convenzione VWAP
  standard; la descrizione non la specifica).
* **Àncora simmetrica per lo short.** Il minimo `low` nella stessa finestra —
  è il `Trough-AVWAP` che lo script stesso definisce. La struttura è identica
  nelle due direzioni: si ancora all'estremo da cui si sta ripartendo.
* **La domanda, una sola:** *il prezzo ha riconquistato l'AVWAP ancorato?*
  `close > peak_avwap` consente long, `close < trough_avwap` consente short.
  La combinazione resta nel codice deterministico, come per ogni altro filtro.

## Regola di decisione, fissata adesso

Metrica primaria: **delta di MAR di portafoglio** contro la base (Donchian
55/20 long-short, parametri Turtle, stessi costi, stesso periodo).

Il componente **aggiunge valore** solo se valgono *entrambe*:

1. delta MAR di portafoglio **> 0**;
2. migliora il MAR su **almeno 4 dei 6 asset** (regola 5: un filtro che aiuta un
   asset è un filtro adattato a quell'asset).

Qualunque altro esito è riportato come "non aggiunge valore". Si riporta anche
il **tasso di blocco**: quante barre di ingresso il gate ferma davvero. Un
filtro che non blocca niente non è un filtro — è una tautologia, come il Chikou
(0 ingressi bloccati su 1.728).

## Perché questo test non paga la tassa del massimo-di-N

La penalità per molteplicità morde quando si **seleziona il massimo** di N
tentativi. Aggiungere questa variante al mucchio e poi riportare il migliore di
ventitré sarebbe inquinato. Dichiararla prima come **ipotesi singola** e
riportarne l'esito qualunque esso sia costa la penalità di *un* test, non quella
del massimo. `N_HYPOTHESES` passa comunque a 23, perché il catalogo deve
contenere tutto ciò che è stato provato: alza la soglia per le affermazioni
future, non per questa.

## Previsione, registrata prima di guardare

Prevedo che **non aggiunga valore**, e per una ragione strutturale precisa, non
per pessimismo:

un ingresso Donchian scatta sulla barra che fa un nuovo massimo a 55 barre.
Quella barra chiude sopra il massimo delle 55 precedenti, quindi sopra il
massimo delle 50 precedenti — che è proprio la nostra àncora. L'AVWAP calcolato
da quell'àncora in avanti è una media di prezzi che stanno, quasi sempre, sotto
la chiusura di rottura. **Quindi mi aspetto che il gate long sia aperto quasi
sempre e blocchi quasi niente**: la stessa tautologia del Chikou, per la stessa
ragione geometrica.

Se è così, il risultato non è "l'AVWAP non funziona": è che **l'AVWAP non è
testabile come gate su ingressi di breakout**, perché le due meccaniche sono
incompatibili. Lo script lo dice da solo — *"New high: a higher high to the
right; prior setup is dropped"* — cioè l'IQ-DAS **scarta** il setup proprio
sulla barra in cui Donchian entra. È uno strumento da pullback, non da breakout.

In quel caso il test informativo sarebbe l'AVWAP **come segnale autonomo**, come
si è fatto per Ichimoku. Sarebbe un'ipotesi nuova, con la sua pre-registrazione.
Non viene eseguita qui.

## Verdetto

**NON aggiunge valore.** Nessuna delle due condizioni pre-dichiarate è
soddisfatta, e la previsione registrata prima del test è risultata esatta.

Periodo 2015-08-10 → 2026-09-14, sei asset, un solo set di parametri.
Riproducibile con `python3 scripts/run_prereg_avwap.py`.

| | MAR | Sharpe | CAGR | maxDD | Trade |
|---|---|---|---|---|---|
| base (Donchian 55/20) | 0.87 | 1.39 | 7.7% | 8.9% | 303 |
| base + `peak_avwap` | 0.87 | 1.39 | 7.7% | 8.9% | 303 |

* **delta MAR di portafoglio: +0.00** (serviva > 0);
* **migliora 0 asset su 6** (ne servivano almeno 4);
* delta per asset **esattamente zero ovunque**: BTC 0.65, ETH 0.68, GOLD 0.19,
  CRUDE 0.19, CORN −0.00, EQUITY 0.02, prima e dopo.

### Perché: è una tautologia condizionale, non un filtro inerte

Il tasso di blocco lo dice senza ambiguità: **5 ingressi bloccati su 1.728**
(long 3/1243, short 2/485), lo **0.3%**.

E il delta non è "piccolo": è **esattamente zero**. Le curve di equity con e
senza il gate sono identiche su tutti e sei gli asset, e il numero di trade non
cambia su nessuno (58, 51, 44, 46, 53, 51). I cinque ingressi bloccati cadevano
tutti su barre in cui il sistema era **già in posizione**, quindi non avrebbero
aperto niente comunque. Il filtro è un no-op esatto.

Se ne vede la traccia anche nel Deflated Sharpe: il differenziale
`peak_avwap − base` è identicamente nullo, quindi il suo Sharpe non è definito e
la variante viene contata in N ma esclusa dalla dispersione — esattamente come
`ichi_chikou`, e per la stessa ragione.

La diagnosi però non è "l'AVWAP è una condizione vuota", e il numero che la
separa dall'altra è questo:

| il gate long è aperto su… | |
|---|---|
| tutte le barre | **35.8%** |
| le sole barre di rottura a 55 barre | **99.8%** |

L'AVWAP ancorato è una condizione **selettiva** — esclude due barre su tre — ma
sulle barre in cui il benchmark entra è **già vera per costruzione**. La ragione
è geometrica ed era scritta prima del test: un ingresso Donchian scatta sulla
barra che chiude sopra il massimo delle 55 precedenti, quindi sopra il massimo
delle 50 precedenti, che è proprio l'àncora; e l'AVWAP calcolato da lì in avanti
è una media di prezzi che stanno sotto quella chiusura.

È la stessa struttura del Chikou, che bloccava 0 ingressi su 1.728, e il
risultato è letteralmente identico: nell'ablazione `peak_avwap` e `ichi_chikou`
hanno lo stesso MAR (0.87), gli stessi 303 trade e lo stesso 0/6.

### Cosa si può e non si può concludere

**Si può concludere** che il Peak-AVWAP non è utilizzabile come gate su ingressi
di breakout: le due meccaniche sono incompatibili. Lo dice anche lo script di
origine, che sulla barra del nuovo massimo *scarta* il setup
(*"New high: a higher high to the right; prior setup is dropped"*). L'IQ-DAS è
uno strumento da pullback; il benchmark è uno strumento da rottura. Gatare il
secondo col primo non è un test dell'idea, è una contraddizione nei termini.

**Non si può concludere** che l'AVWAP ancorato non valga niente. Questo test non
lo ha misurato — non poteva. L'esperimento informativo sarebbe l'AVWAP **come
segnale autonomo**, come si è fatto per Ichimoku quando l'ablazione dei filtri
aveva dato lo stesso tipo di risposta muta. Sarebbe un'ipotesi nuova, con la sua
pre-registrazione, e porterebbe N a 27.

### Effetto sul conteggio

`N_HYPOTHESES` passa da **25 a 26**, e con esso la soglia del Deflated Sharpe
per tutte le affermazioni precedenti:

| | N = 25 | N = 26 |
|---|---|---|
| soglia sul differenziale grezzo (Sharpe annuo) | 1.400 | **1.411** |
| DSR di `cloud_exit` − benchmark, grezzo | 0.000057 | **0.000049** |
| soglia sul differenziale a parità di volatilità | 0.937 | **0.945** |
| DSR di `cloud_exit` − benchmark, vol matched | 0.0538 | **0.0508** |

Il differenziale di `peak_avwap` è identicamente nullo, quindi il suo Sharpe non
è definito: la variante è **contata in N** — come devono esserlo `gann_1x1`,
`gann_1x2` e `ichi_chikou` — ma esclusa dal calcolo della dispersione, che resta
0.0367. L'unico effetto sulla soglia è quello di N, ed è quello che si vede
sopra.

È il prezzo dichiarato in partenza, ed è il motivo per cui la regola resta
valida: **ogni ipotesi in più costa a tutte le precedenti.** Qui è stato pagato
consapevolmente, per una componente mai misurata e che guardava i volumi invece
della geometria. Il test informativo che resta — l'AVWAP come *segnale
autonomo*, non come gate — porterebbe N a 27, e va pre-registrato a parte.

## Nota sulla cronologia

La pre-registrazione qui sopra e la sua esecuzione sono state scritte a partire
dallo stato del progetto al commit `4f31b0c`, quando il catalogo contava 22
ipotesi. Nel frattempo il branch era andato avanti di ventisei commit —
universo esteso, parity chiuso, tre ipotesi aggiunte — e al merge il catalogo ne
contava già 25.

**La misura non è cambiata di una cifra** sul motore aggiornato: stesso delta
nullo, stessi 5 ingressi bloccati su 1.728, stesse curve di equity identiche. È
cambiata solo la contabilità di N, corretta qui sopra ai valori veri. La
specifica, la regola di decisione e la previsione restano quelle committate
prima del test, in `4da2166`, e non sono state toccate.
