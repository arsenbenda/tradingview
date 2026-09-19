# Universo allargato: da sei a quindici strumenti

Eseguito il 2026-09-15 con `python3 scripts/run_benchmark.py --universe extended`.
Stesso segnale, stessi parametri, stesso motore, stesso periodo
(2015-08-10 → 2026-09-14): cambia solo su quante cose gira. Nessuna nuova
ipotesi, **N resta 22**.

La lista dei nove strumenti aggiunti è stata dichiarata in
`data/universe_declaration.md` e committata **prima** di scaricare i dati, con le
attese scritte in anticipo. Questo report le confronta con il risultato.

## Il risultato

| | MAR | Sharpe | CAGR | maxDD | Trade |
|---|---|---|---|---|---|
| **sei strumenti** | **0.87** | 1.39 | 7.7% | 8.9% | 303 |
| **quindici strumenti** | **0.61** | 0.85 | 2.5% | 4.1% | 787 |

Il drawdown **si è più che dimezzato**, da 8.9% a 4.1%. Il rendimento è sceso di
due terzi, da 7.7% a 2.5%. Il MAR è **peggiorato**, da 0.87 a 0.61.

Vale in tutti e tre gli scenari, quindi non è un effetto del modello di costo né
del vincolo di direzione:

| scenario | sei | quindici |
|---|---|---|
| long/short, costi stimati | 0.87 | **0.61** |
| solo long, costi stimati | 0.89 | **0.74** |
| long/short, costi doppi | 0.84 | **0.56** |

## Attese registrate in anticipo, e cosa è successo

| attesa dichiarata prima | esito |
|---|---|
| Il drawdown di portafoglio scende | **giusta** — 8.9% → 4.1% |
| Il CAGR resta simile o scende leggermente | **sbagliata** — è sceso del 68% |
| Il MAR sale, ma meno del calo del drawdown | **sbagliata** — è sceso, da 0.87 a 0.61 |
| Il guadagno sarà minore di quello dei primi sei | giusta, ma per difetto: è negativo |

Due attese su quattro sbagliate, ed è il motivo per cui registrarle serviva. La
dichiarazione diceva anche cosa avrebbe dovuto far sospettare un errore — "se il
CAGR sale e il drawdown non scende" — e quel caso non si è verificato: il
drawdown è sceso come previsto. Il modello di cosa fa la diversificazione era
giusto; era sbagliata l'ipotesi implicita che gli strumenti aggiunti avessero un
vantaggio da diversificare.

## Perché: il segnale non funziona su nulla che non sia crypto

MAR per strumento, stesso periodo e stessi parametri:

| strumento | MAR | CAGR | | strumento | MAR | CAGR |
|---|---|---|---|---|---|---|
| **ETH** | **0.68** | **26.4%** | | EQUITY_INTL (EFA) | −0.03 | −0.7% |
| **BTC** | **0.65** | **13.6%** | | BOND_LONG (TLT) | −0.04 | −0.6% |
| GOLD | 0.19 | 2.6% | | USD (UUP) | −0.05 | −0.6% |
| CRUDE | 0.19 | 2.3% | | NATGAS (UNG) | −0.05 | −0.9% |
| SILVER | 0.05 | 1.1% | | BOND_HY (HYG) | −0.08 | −1.9% |
| EQUITY (SPY) | 0.02 | 0.3% | | JPY (FXY) | −0.08 | −1.7% |
| CORN | −0.00 | −0.0% | | REIT (VNQ) | −0.08 | −2.0% |
| | | | | EQUITY_EM (VWO) | −0.09 | −1.8% |

**Due strumenti su quindici hanno un vantaggio. Sono le due crypto.** Tutto il
resto sta fra −2.0% e +2.6% di CAGR, e nove dei quindici sono negativi.

### Non sono i costi

Rieseguito con commissioni e slippage azzerati, i nove nuovi restano negativi:
EQUITY_INTL −0.6%, EQUITY_EM −1.6%, BOND_LONG −0.5%, BOND_HY −1.8%, USD +0.1%,
JPY −1.3%, SILVER +1.1%, NATGAS −0.9%, REIT −1.9%. Il vantaggio non è mangiato
dalle frizioni: non c'è.

### Non è un errore di aggregazione

Il difetto che diluiva i rendimenti degli strumenti quotati prima è stato
corretto e testato prima di questo lavoro (`metrics.equal_weight_returns`). Sui
sei originali, che condividono il periodo, il benchmark resta 0.87 / 1.39 / 7.7%
/ 8.9% / 303 trade, identico a prima.

## Cosa significa

**Il portafoglio non fabbrica rendimento.** Riduce il rischio, e lo ha fatto
esattamente come previsto. Ma con capitale equipesato, ogni strumento senza
vantaggio aggiunto diluisce quelli che ce l'hanno: il contributo di BTC ed ETH
passa da 2/6 a 2/15 del capitale, e il rendimento crolla in proporzione mentre il
drawdown scende solo della radice di quanto sarebbe servito.

**La leva NON risolve, ma non per la ragione che questa sezione dava — due
correzioni successive, 2026-09-15.** La versione precedente affermava che il MAR è invariante di scala,
che raddoppiare l'esposizione raddoppia CAGR *e* drawdown, e che un portafoglio a
MAR 0.61 leverato resta a 0.61. **È falso, ed è stato misurato falso.** Vedi la
sezione "La leva, e perché il confronto a rischio 1% non era alla pari" più sotto:
il MAR sale con la dimensione della posizione fino a un massimo e poi ridiscende.

Ma la spiegazione che avevo messo al suo posto era a sua volta sbagliata.
`results/risk_walkforward.md` separa le due cose: sotto **leva pura** — stessi
trade, rendimenti moltiplicati per k — lo Sharpe resta **esattamente costante a
1.18** e il MAR sale da 0.89 a 1.22, quindi quella salita è **interamente
l'artefatto di misura**, e la leva non regala niente. Lo Sharpe sale davvero solo
alzando `risk_pct` dentro il motore, e sale perché sopra il 2% il tetto sul
capitale morde su gran parte dei trade e il sizing proporzionale all'ATR viene
sostituito da un sizing a nozionale costante: a rischio 8%, 142 trade su 178.

Quindi: il portafoglio non fabbrica rendimento (vero), la leva non lo fabbrica
nemmeno (vero, e la prima correzione lo negava), e il confronto fra sei e quindici
a rischio fisso 1% resta comunque non alla pari, perché i due universi stanno in
punti diversi della curva del *sizing*.

**Pesare di più gli strumenti che funzionano è selezione.** È l'unica cosa che
alzerebbe il MAR, ed è esattamente ciò che il progetto ha passato ventidue
ipotesi a non fare: quei pesi sarebbero scelti sapendo che il 2015-2026 è stato
il decennio delle crypto.

E soprattutto: **il benchmark di questo progetto è un risultato crypto.** Lo 0.87
di MAR contro cui sono state misurate tutte e ventidue le ipotesi non è la
performance di un trend follower multi-asset, è la performance di BTC ed ETH con
quattro strumenti quasi neutri intorno. Allargare a quindici lo rende visibile: lo
stesso identico segnale, su un universo davvero eterogeneo, fa 0.61 con Sharpe
0.85.

## Controprova: i tredici senza crypto, solo long

Eseguito il 2026-09-15 con `python3 scripts/run_benchmark.py --universe no-crypto`,
stesso periodo e stessi parametri. Non è una nuova ipotesi e **N resta 22**: è
`EXTENDED` meno una classe di attività intera, cioè la misura diretta
dell'affermazione della sezione precedente. Solo long perché è il vincolo che i
tredici chiedono da soli — sono strumenti a deriva positiva di lungo periodo, e
lo short lì è la metà del segnale che perde.

| quindici / tredici | MAR | Sharpe | CAGR | maxDD | Trade |
|---|---|---|---|---|---|
| quindici, long/short | 0.61 | 0.85 | 2.5% | 4.1% | 787 |
| quindici, solo long | 0.74 | 1.16 | 2.9% | 3.9% | 417 |
| **tredici senza crypto, long/short** | **−0.03** | −0.08 | −0.2% | 5.5% | 678 |
| **tredici senza crypto, solo long** | **0.17** | 0.30 | **0.4%** | 2.4% | 351 |

**Togliere due strumenti su quindici porta via tutto il rendimento.** I tredici
che restano, che sono l'86% del capitale, fanno 0.4% l'anno solo long e perdono
long/short. Il vincolo long-only vale 0.20 di MAR su questo universo — molto più
dei 0.13 che vale sui quindici — perché senza crypto la parte short non ha più
niente da compensare: su nove strumenti su tredici aggiungere lo short peggiora
il CAGR, e su tre lo migliora di meno di 0.2 punti.

### Non sono i costi, di nuovo

Solo long, tredici strumenti, a frizioni azzerate: MAR 0.21, CAGR 0.52%, sette
strumenti positivi su tredici invece di sei. Con i costi stimati 0.17, con i costi
doppi 0.13. La pendenza c'è ma parte da zero: non è un vantaggio eroso dalle
frizioni, è un vantaggio che non esiste e che le frizioni rendono appena
negativo.

### Non è il periodo

Senza ETH cade il vincolo sulla data d'inizio — era lo strumento con meno storia —
e i tredici quotano tutti dal **2013-01-02**. Rieseguito su quei tre anni e mezzo
in più, cioè su un campione più grande del 24%, il risultato peggiora: solo long
MAR 0.10 e CAGR 0.2%, long/short MAR −0.02. I due anni e mezzo aggiuntivi non
contengono un vantaggio che il 2015-2026 nascondeva.

### Cosa aggiunge alla conclusione

La sezione precedente diceva che il benchmark è un risultato crypto sulla base
dei MAR per strumento. Questa lo misura a livello di portafoglio, che è il
livello a cui il progetto decide: **il trend following Donchian 55/20 su undici
anni di obbligazionario, valute, azionario sviluppato ed emergente, immobiliare e
materie prime non produce nulla di distinguibile da zero.** Lo 0.87 dei sei non è
lo 0.87 di un trend follower multi-asset diluito da strumenti mediocri: è lo 0.87
di due strumenti, e gli altri tredici sono zavorra a rendimento nullo.

Questo non falsifica il trend following — vedi il primo dei limiti qui sotto, il
periodo è uno solo e storicamente ostile fuori dalle crypto. Falsifica l'idea che
questo progetto abbia mai misurato un trend follower multi-asset.

## La leva, e perché il confronto a rischio 1% non era alla pari

Misurato il 2026-09-15 con `scripts/run_benchmark.py --risk`, aggiunto per questo.
Nasce da un'obiezione giusta: se una strategia lascia il capitale fermo, il modo
di usarlo è alzare la dimensione della posizione. La risposta che questo documento
dava — "il MAR è invariante di scala" — **era sbagliata.**

MAR di portafoglio al variare del rischio per trade, solo long, stessi segnali:

| rischio/trade | sei | quindici | tredici no-crypto |
|---|---|---|---|
| 1% *(tutti i risultati pubblicati)* | 0.89 | 0.74 | 0.17 |
| 2% | 1.29 | 1.08 | 0.23 |
| **4%** | **1.50** | **1.45** | **0.27** |
| 8% | 1.50 | 1.38 | 0.23 |
| 16% e oltre | 1.44 | 1.32 | 0.22 |

Il MAR non è invariante: sale, ha un massimo intorno al 4-8% di rischio per
trade, poi ridiscende. Somiglia alla curva della *optimal f*, ma non lo è — la
decomposizione in `results/risk_walkforward.md` mostra che è per metà artefatto di
misura e per metà un cambio di regola di sizing. Ignorarla era comunque un
errore.

**Perché sale.** Con sizing a frazione fissa, una sequenza di perdite consuma il
capitale geometricamente — `(1−r)^n`, non `n·r` — quindi il drawdown *in
percentuale* cresce meno che proporzionalmente al rischio, mentre il rendimento
composto cresce più che proporzionalmente. Il rapporto fra i due deve salire. Non
è un vantaggio che appare dal nulla: è che misurare numeratore e denominatore in
percentuale invece che in logaritmi fa sembrare la leva migliore di quanto sia.
**Il MAR lusinga la leva**, e due MAR misurati a rischio diverso non sono
confrontabili.

**Perché satura.** Oltre il 16% la curva si ferma: `backtest.run` limita la
posizione a `st.cash * max_notional_pct / fill`, con `max_notional_pct = 1.0`.
Cioè niente margine — non si può investire più del capitale. La saturazione è il
conto in banca, non una proprietà del segnale.

### Cosa cambia, e cosa no

**Cambia il verdetto su sei contro quindici.** A rischio 1% il divario è 0.89
contro 0.74; a rischio 4% è 1.50 contro 1.45, e i quindici lo ottengono con un
drawdown del 5.9% contro il 14.2% dei sei. Il confronto pubblicato metteva i due
universi sullo stesso rischio nominale, che non è lo stesso punto della curva:
i quindici, avendo drawdown molto più basso, erano sottodimensionati. Il divario
non si inverte, ma da 0.15 scende a 0.05.

**Non cambia il verdetto sulle due Pine.** A parità di drawdown tollerato (20%,
scalando il rischio di ognuna finché non ci arriva), sui sei:

| | rischio | CAGR | maxDD |
|---|---|---|---|
| benchmark long/short | 7.8% | **29.2%** | 20.0% |
| benchmark solo long | satura | **28.5%** | 19.7% |
| Confluence v3.2 | satura | 20.2% | 15.7% |
| Sanyaku v5.5 | 15.7% | **13.7%** | 20.0% |

La Sanyaku, sizzata fino allo stesso rischio del benchmark, rende meno della
metà. Il capitale fermo si può usare, e usarlo non ribalta la classifica.

**Non cambia il verdetto sui tredici senza crypto.** Il massimo della curva è
0.27 di MAR, 1.6% di CAGR. Leverare il nulla dà nulla leverato.

**Non cambia nessuno dei ventidue confronti.** Ogni runner del progetto
(`run_benchmark`, `run_ablation`, `run_ichimoku_tests`, `compare_strategies`,
`validation`) usa `risk_pct=0.01`: tutte le ipotesi sono state misurate contro il
benchmark nello stesso punto della curva, sullo stesso universo. Quei confronti
sono alla pari e restano validi. L'unico che non lo era è sei contro quindici.

### Perché il 4% non è un risultato

La riga migliore di quella tabella è scelta guardando la tabella. È la stessa
selezione in-sample che il progetto ha passato ventidue ipotesi a non fare, e
sulla optimal f è più pericolosa che altrove: la curva è asimmetrica, superare il
massimo costa molto più che restarne sotto, e il massimo stimato su undici anni
di un campione non è il massimo del prossimo. In più il motore ammette che una
barra gappi oltre lo stop, quindi al 4-8% nominale la perdita realizzata di un
singolo trade può superare di parecchio il rischio dichiarato — a rischio 1% è
un fastidio, al 8% è il tipo di evento che chiude un conto.

Il numero utilizzabile di questa sezione non è "il 4% è meglio dell'1%". È: **i
MAR di questo progetto vanno confrontati solo a parità di rischio per trade, e il
rischio per trade è un parametro libero che nessuno ha ottimizzato — per scelta.**

Il seguito, con la validazione fuori campione di quel 4% e la scoperta di cosa
stia davvero cambiando, è in **`results/risk_walkforward.md`**.

## Limiti dichiarati

1. **Undici anni sono un periodo, non un campione di periodi.** Il 2015-2026 è
   stato un decennio difficile per il trend following fuori dalle crypto — tassi a
   zero fino al 2022, poi un solo grande movimento. Il trend following su
   obbligazionario e valute ha decenni di storia in cui ha funzionato, e questo
   test non li tocca. La conclusione è *su questo periodo*, e non si estende.
2. **Un solo set di parametri, per scelta.** Donchian 55/20 con stop 2×ATR(20) è
   tarato, implicitamente, su mercati a volatilità elevata. Su UUP, che si muove
   dell'8% all'anno, un canale a 55 barre è probabilmente la finestra sbagliata.
   Ma cercare la finestra giusta per strumento è ottimizzare per asset, cioè la
   regola 3, e distruggerebbe la domanda a cui il progetto risponde.
3. **Equipesatura del capitale.** È la scelta dichiarata e l'unica che non guarda
   i risultati. Una pesatura per rischio a livello di portafoglio, o per
   correlazione, è un'ipotesi diversa: andrebbe dichiarata prima, contata come
   ipotesi, e sottoposta alla stessa validazione delle altre ventidue.
4. **Nessun numero qui è out-of-sample.** Vale quanto scritto in
   `results/validation.md`: questo è il periodo su cui tutto è stato costruito.

## Conseguenze

* La questione aperta "portafoglio invece che segnale" **si chiude, con esito
  negativo**. L'effetto sul drawdown è reale e misurato; l'effetto sul MAR è
  negativo. Non era "l'unica leva che i dati hanno mostrato funzionare": era
  l'unica non ancora misurata.
* L'universo a quindici resta nel repo e resta congelato, perché è il campione più
  onesto di cui il progetto dispone. I sei restano il default di
  `data.load_universe` solo per non rendere irriproducibili i risultati già
  pubblicati.
* Quello che resta da fare non cambia: il **parity test** contro il Pine, che non
  richiede di trovare un vantaggio nuovo, e **più dati** — altri decenni, non
  altre ipotesi sugli stessi undici anni.

## Riproduzione

```bash
python3 -m pytest tests/ -q                            # 92 test
python3 scripts/run_benchmark.py --universe core       # i sei, 0.87
python3 scripts/run_benchmark.py --universe extended   # i quindici, 0.61
python3 scripts/run_benchmark.py --universe no-crypto  # i tredici, 0.17 solo long
python3 scripts/run_benchmark.py --universe no-crypto --start 2013-01-02   # 0.10
python3 scripts/run_benchmark.py --universe extended --risk 4            # 1.45
```
