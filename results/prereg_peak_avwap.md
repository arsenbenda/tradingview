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

*(vuoto: da compilare nel commit successivo)*
