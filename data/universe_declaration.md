# Dichiarazione dell'universo allargato

**Scritto il 2026-09-15, prima di scaricare qualunque nuova serie e prima di
eseguire qualunque backtest sull'universo allargato.** Il commit che introduce
questo file non contiene dati nuovi né risultati: la cronologia git è la prova
che la lista non è stata scelta dopo aver visto cosa funzionava.

## Perché questo file esiste

La regola 5 del progetto dice che un componente che aiuta un solo gruppo di
asset è adattato a quel gruppo. La stessa trappola vale per gli strumenti:
aggiungerne quattordici e tenere i dieci che hanno migliorato il portafoglio è
la ricerca di ipotesi rifatta in un altro costume, e il Deflated Sharpe della
validazione non ne saprebbe niente.

L'unica difesa è dichiarare la lista prima, con un criterio che non guarda i
rendimenti, e tenerla tutta.

## Il criterio, in cinque punti

1. **Copertura settoriale, non selezione di strumenti.** Si rappresentano i
   quattro settori classici del trend following — azionario, obbligazionario,
   valute, materie prime — più le crypto, che l'universo ha già. Oggi
   obbligazionario e valute sono **completamente assenti**: è il buco più grande,
   e si riempie prima di ogni altra cosa.
2. **Dentro un settore si scelgono esposizioni economicamente distinte**, non
   varianti dello stesso fattore: duration e credito, non due scadenze di
   Treasury; dollaro e yen, non dollaro ed euro, che sono quasi l'uno l'opposto
   dell'altro. Un ETF che replica un fattore già presente non aggiunge
   diversificazione, aggiunge solo righe.
3. **Il più liquido per ogni esposizione**, perché lo slippage stimato sia
   difendibile e perché la liquidità non dipende dai rendimenti.
4. **Quotazione precedente al 2015-08-08**, l'inizio del periodo comune
   (`data.DEFAULT_START`), verificata su Twelve Data **prima** di scrivere questa
   lista. Nessuno strumento entra o esce in mezzo al periodo.
5. **Una sola famiglia di fonti**, come impone `data/README.md`: Twelve Data per
   tutto ciò che non è crypto, Alpha Vantage per le crypto.

E la clausola che rende il criterio vincolante:

> **La lista è congelata.** Ogni strumento che passa `scripts/validate_series.py`
> resta nell'universo qualunque sia il suo contributo, positivo negativo o nullo.
> Uno strumento può uscire **solo** per un difetto dei dati, e l'uscita va
> documentata qui con il difetto che l'ha causata. Non può uscire perché rende
> poco: sei dei sei attuali rendono poco o niente da soli, e il portafoglio batte
> comunque il migliore di loro.

## La lista

I sei attuali restano invariati. Nove nuovi, tutti ETF quotati negli Stati Uniti.

| Settore | Strumento | Esposizione | Prima barra | Stato |
|---|---|---|---|---|
| Crypto | BTC | Bitcoin | 2013-04-28 | già presente |
| Crypto | ETH | Ethereum | 2015-08-08 | già presente |
| Azionario | SPY | USA large cap | 2006-10-26 | già presente |
| Azionario | **EFA** | sviluppati ex-USA | 2001-08-27 | **nuovo** |
| Azionario | **VWO** | emergenti | 2013-01-02 | **nuovo** (sostituisce EEM) |
| Obbligazionario | **TLT** | duration USA 20+ anni | 2002-07-30 | **nuovo** |
| Obbligazionario | **HYG** | credito high yield | 2007-04-11 | **nuovo** |
| Valute | **UUP** | dollaro | 2007-03-01 | **nuovo** |
| Valute | **FXY** | yen | 2007-02-13 | **nuovo** |
| Materie prime | GLD | oro | 2006-10-26 | già presente |
| Materie prime | **SLV** | argento | 2006-04-28 | **nuovo** |
| Materie prime | USO | petrolio | 2006-10-26 | già presente |
| Materie prime | **UNG** | gas naturale | 2007-04-18 | **nuovo** |
| Materie prime | CORN | mais | 2010-06-09 | già presente |
| Immobiliare | **VNQ** | REIT USA | 2004-09-29 | **nuovo** |

Quindici strumenti, cinque settori più l'immobiliare. Le prime barre sono quelle
riportate da `get_earliest_timestamp` di Twelve Data.

### Perché queste e non altre

* **TLT e HYG** invece di TLT e IEF: duration e credito sono due fattori di
  rischio diversi, due scadenze di Treasury sono lo stesso fattore.
* **UUP e FXY** invece di UUP e FXE: l'euro pesa circa il 57% dell'indice del
  dollaro, quindi UUP e FXE sono quasi la stessa scommessa al contrario. Lo yen è
  il mercato valutario su cui il trend following ha la storia più lunga.
* **UNG** invece di un secondo ETF sul petrolio: il gas naturale è il mercato a
  più alta volatilità fra quelli accessibili via ETF, ed è poco correlato al
  greggio nonostante entrambi siano energia.
* **EFA ed EEM** invece di QQQ o IWM: geografia, non stile. QQQ e IWM sono
  correlati a SPY molto più di quanto lo siano l'Europa o gli emergenti.
* **Nessun secondo ETF azionario USA**, nessun LQD, nessun IEF, nessun FXE: tutti
  fattori già coperti.

## Modifiche alla lista, dopo la dichiarazione

Registrate qui come impone la clausola: uno strumento esce solo per un difetto
dei dati, mai per il suo rendimento, e l'uscita va documentata.

### EEM → VWO, il 2026-09-15, prima di qualunque backtest

Twelve Data restituisce EEM con ogni giorno di contrattazione dal 2013 al 2021
ripetuto due volte, e su quattro date le due righe portano **aperture diverse fino
allo 0.9%** — l'apertura è il prezzo con cui il motore riempie gli ordini, quindi
tenerne una a caso significa scegliere il prezzo di esecuzione fra due valori
discordanti. Il filtro per borsa non cambia nulla: sono due pagine sovrapposte
della stessa richiesta, non due venue. Dettaglio completo in `data/README.md`,
difetto numero 4.

VWO ha la stessa esposizione dichiarata — azionario emergenti — ed è il secondo
fondo per liquidità su quella esposizione, quindi il criterio resta soddisfatto.
Passa il gate senza rilievi oltre al gap COVID del 2020-03-16, comune a tutto
l'azionario.

**Nessun backtest era stato eseguito quando la sostituzione è avvenuta**: non
esisteva alcuna informazione sul rendimento né di EEM né di VWO.

## Cosa mi aspetto, dichiarato prima di eseguirlo

Registrato qui perché sia falsificabile. Un'attesa scritta dopo il risultato non
è un'attesa.

* **Il drawdown di portafoglio scende.** È l'unico effetto garantito dalla
  matematica finché le correlazioni sono sotto 1, e l'unica ragione per fare
  questo lavoro.
* **Il CAGR resta simile o scende leggermente.** Obbligazionario e valute hanno
  volatilità molto più bassa di crypto e materie prime; a parità di rischio per
  trade contribuiscono meno rendimento assoluto. Con capitale equipesato, il peso
  delle crypto nel portafoglio si diluisce da 2/6 a 2/15.
* **Il MAR sale, ma meno di quanto il calo del drawdown suggerisca**, per lo
  stesso motivo.
* **Il guadagno sarà minore di quello dei primi sei.** I sei attuali sono già
  molto eterogenei: la diversificazione ha rendimenti decrescenti, e i nove nuovi
  arrivano dopo che il grosso dell'effetto è già stato incassato.

Se invece il CAGR **sale** e il drawdown **non** scende, qualcosa non torna e va
indagato prima di scrivere qualunque conclusione.

## Cosa questo lavoro non è

Non è una nuova ipotesi. Il segnale, i parametri, lo stop, il rischio per trade e
il modello di costo restano identici: Donchian 55/20, 2×ATR(20), 1% per trade.
Cambia solo su quante cose gira. **N resta 22** e il Deflated Sharpe non si
muove: non c'è niente da deflazionare, perché non si sta scegliendo niente.
