# Validazione fuori campione del candidato `cloud_exit`

Eseguito il 2026-09-15 con `scripts/run_validation.py`. Periodo 2015-08-10 →
2026-09-14, sei asset, un solo set di parametri, costi per asset.

> **Aggiornamento dello stesso giorno, N = 22 → 23.** Dopo questa stesura è stata
> aggiunta al catalogo la ventitreesima ipotesi, `sizing_notional`
> (`results/risk_walkforward.md`), ed è stato aggiunto un test che mancava: il
> differenziale **a parità di volatilità**, perché una variante che gira a tre
> volte la scala del benchmark ha un differenziale grezzo positivo per
> costruzione. Il verdetto di questo documento **non cambia** — anzi si rafforza —
> ma **tre numeri sì**. La sezione «Rifacimento con N = 23» in fondo li elenca, e
> le righe interessate qui sotto rimandano lì. Il testo originale resta com'era:
> è il verbale di cosa si sapeva prima, e riscriverlo cancellerebbe la sola cosa
> che rende leggibile la differenza.

## La risposta

**No. Il vantaggio del candidato non sopravvive.**

Non perché il candidato sia cattivo — non lo è, e in quasi tutti i sotto-periodi
fa meglio del benchmark. Non sopravvive perché **quel "meglio" non è
distinguibile dal miglior risultato che ventidue tentativi senza alcun vantaggio
produrrebbero comunque**, e perché **la procedura che ha selezionato `cloud_exit`
non ha valore fuori campione**: rieseguita dentro finestre di training e
misurata dopo, aggiunge in media −0.04 di MAR, e sceglie `cloud_exit` una volta
su otto.

Tre numeri, in ordine di importanza:

| | valore | significato |
|---|---|---|
| **DSR del differenziale candidato − benchmark** | **0.025** † | La soglia per il migliore di 22 ipotesi è 0.85 di Sharpe annuo; il differenziale osservato è 0.28. Sotto la soglia. |
| **delta MAR medio della procedura di selezione, fuori campione** | **−0.04** | Scegliere la migliore di 23 varianti su tre anni e usarla l'anno dopo non batte il non scegliere niente. |
| **IC 95% sul delta di MAR, bootstrap a blocchi** | **[−0.31, +0.82]** | Contiene lo zero. P(delta ≤ 0) = 29%. |

† Ricalcolato a N = 23 e a parità di volatilità: **0.074**. Sempre sotto ogni
soglia, e la conclusione è la stessa. Vedi «Rifacimento con N = 23».

## Perché i tre test dicono cose che sembrano diverse

Il candidato *fisso* si comporta bene ovunque lo si misuri. La *procedura* che
lo ha prodotto non funziona. Non è una contraddizione: è esattamente ciò che si
osserva quando una variante è stata scelta con il senno di poi su tutto il
periodo. Tenere separate le due affermazioni è l'unico modo di leggere le
tabelle che seguono.

### 1. Walk-forward a candidato fisso — misura la stabilità, non la selezione

Otto finestre di test contigue, training di tre anni, avanzamento annuale.
Candidato e benchmark sottoposti al medesimo protocollo.

| finestra | MAR base | MAR cand | delta | Sharpe base | Sharpe cand | asset migliorati |
|---|---|---|---|---|---|---|
| 2018-08 → 2019-08 | 3.29 | 2.63 | −0.66 | 1.91 | 1.67 | 3/6 |
| 2019-08 → 2020-08 | 3.15 | 3.30 | +0.15 | 1.46 | 1.39 | 2/6 |
| 2020-08 → 2021-08 | 3.37 | 4.25 | +0.88 | 2.04 | 2.12 | 5/6 |
| 2021-08 → 2022-08 | 1.20 | 1.26 | +0.06 | 0.75 | 0.87 | 3/6 |
| 2022-08 → 2023-08 | −0.86 | −0.80 | +0.06 | −1.28 | −0.92 | 4/6 |
| 2023-08 → 2024-08 | 1.83 | 2.22 | +0.39 | 1.24 | 1.24 | 4/6 |
| 2024-08 → 2025-08 | 1.97 | 3.31 | +1.35 | 1.18 | 1.41 | 2/6 |
| 2025-08 → 2026-08 | 2.86 | 3.69 | +0.82 | 1.18 | 1.51 | 5/6 |
| **distribuzione** | | | **mediana +0.27, media +0.38, 7/8 positivi** | | **mediana +0.10, 5/8 positivi** | |

Aggregato sulle otto finestre concatenate (2018-08 → 2026-08):

| | MAR | Sharpe | CAGR | maxDD | Trade |
|---|---|---|---|---|---|
| benchmark | 0.90 | 1.19 | 5.2% | 5.8% | 219 |
| candidato | **1.48** | 1.24 | 5.2% | 3.5% | 224 |

Due avvertenze che cambiano la lettura della tabella.

**I livelli di MAR fra finestre non sono confrontabili con il MAR del periodo
intero.** Il maxDD di un anno è meccanicamente più piccolo di quello di undici,
quindi il MAR di una finestra annuale è meccanicamente più grande: 3.29 su una
finestra e 0.87 su tutto il periodo descrivono la stessa strategia. Solo il
*delta* fra due strategie misurate sulla stessa finestra è una quantità
interpretabile, ed è il motivo per cui il benchmark viene sottoposto allo stesso
identico protocollo.

**Nessuna di queste otto finestre è fuori campione rispetto alla selezione.**
`cloud_exit` è stato scelto conoscendo tutto il periodo 2015-2026, incluse tutte
e otto le finestre di test. Che una variante scelta perché funzionava dappertutto
funzioni poi quasi dappertutto è in parte un fatto meccanico, non una conferma.
Questa tabella dice che `cloud_exit` è **stabile**, e lo dice bene: 7 finestre su
8 e mai un crollo. Non dice che sia **vero**.

Il guadagno, anche qui, è tutto nel drawdown: CAGR identico (5.2% contro 5.2%),
maxDD 3.5% contro 5.8%. Lo Sharpe aggregato passa da 1.19 a 1.24, cioè quasi
niente — coerente con il fatto che il differenziale giornaliero è minuscolo.

### 2. Walk-forward con selezione — il test della procedura

Dentro ogni finestra di training viene rieseguita l'intera ricerca: 23 varianti
(le 22 ipotesi più la rinuncia, cioè il benchmark), si tiene la migliore per MAR,
si misura sulla finestra successiva mai vista. È l'unico protocollo che
riproduce onestamente cosa sarebbe successo decidendo in tempo reale.

| finestra | scelta in-sample | MAR IS | MAR OOS | base OOS | delta | ρ rango IS→OOS |
|---|---|---|---|---|---|---|
| 2018-08 → 2019-08 | signal_sanyaku | 2.44 | 4.08 | 3.29 | +0.78 | 0.42 |
| 2019-08 → 2020-08 | exit_kijun_cross | 3.02 | 4.84 | 3.15 | +1.69 | 0.02 |
| 2020-08 → 2021-08 | exit_kijun_trail | 3.52 | 1.97 | 3.37 | −1.40 | 0.42 |
| 2021-08 → 2022-08 | exit_kijun_cross | 3.59 | 1.36 | 1.20 | +0.16 | 0.40 |
| 2022-08 → 2023-08 | signal_sanyaku | 2.51 | −0.85 | −0.86 | +0.01 | 0.26 |
| 2023-08 → 2024-08 | **exit_cloud_exit** | 1.38 | 2.22 | 1.83 | +0.39 | −0.09 |
| 2024-08 → 2025-08 | signal_tk | 0.88 | 1.13 | 1.97 | −0.83 | −0.28 |
| 2025-08 → 2026-08 | filter_ichi_htf | 0.88 | 1.73 | 2.86 | −1.14 | −0.29 |
| **distribuzione** | | | | | **mediana +0.08, media −0.04, 5/8** | **mediana 0.14** |

Tre cose, tutte negative.

**La procedura non aggiunge niente.** Media −0.04, mediana +0.08, cinque
finestre su otto positive: è una moneta. Applicare la ricerca invece di tenersi
il benchmark non ha prodotto valore fuori campione.

**La classifica in-sample non predice quella out-of-sample.** La correlazione di
rango fra le due graduatorie delle 23 varianti ha mediana 0.14, e in tre finestre
su otto è negativa. Scegliere la migliore in-sample è quasi indistinguibile dal
pescarne una a caso — che è la definizione operativa di selezione su rumore.

**`cloud_exit` viene scelto una volta su otto.** Le finestre scelgono
`signal_sanyaku` due volte, `exit_kijun_cross` due, e poi quattro varianti
diverse una volta ciascuna — compreso `filter_ichi_htf`, che su tutto il periodo
è il filtro Ichimoku **più dannoso** dei quindici (−0.21 di MAR) e il cardine di
entrambe le strategie Pine. Se il candidato fosse un
fatto strutturale dei dati, una finestra di tre anni lo troverebbe più spesso di
così. Non lo trova: `cloud_exit` è primo su undici anni e quasi mai su tre.

### 3. K-fold purgato con embargo

Cinque blocchi contigui. Il training di ogni fold è tutto il resto della serie
meno i **200 giorni** che precedono il test — la durata massima osservata di un
trade sulle varianti candidate è 198 giorni, quindi è l'orizzonte entro cui
un'osservazione di training può avere il proprio esito dentro il test — meno un
**embargo di 40 giorni** (circa l'1% della serie) dopo.

| fold | MAR base | MAR cand | delta | scelta sul training purgato | MAR OOS della scelta |
|---|---|---|---|---|---|
| 1 · 2015-08 → 2017-10 | 2.00 | 2.77 | +0.76 | exit_kijun_cross | 2.20 |
| 2 · 2017-10 → 2020-01 | 1.19 | 1.80 | +0.61 | **exit_cloud_exit** | 1.80 |
| 3 · 2020-01 → 2022-04 | 1.71 | 2.64 | +0.93 | exit_kijun_trail | 2.36 |
| 4 · 2022-04 → 2024-06 | 0.35 | 0.46 | +0.11 | exit_kijun_cross | 0.52 |
| 5 · 2024-06 → 2026-09 | 2.19 | 3.05 | +0.86 | signal_sanyaku | 0.69 |
| **distribuzione** | | | **mediana +0.76, media +0.66, 5/5** | | **delta scelta: media +0.03** |

Di nuovo lo stesso divario, e ancora più netto: il candidato **fisso** batte il
benchmark in 5 fold su 5 con un delta medio di +0.66, la **procedura** che
dovrebbe trovarlo ne ricava +0.03. Il k-fold usa quasi nove anni di training per
fold — molto più del walk-forward — e nemmeno così la selezione diventa
informativa.

Purge ed embargo cambiano la variante selezionata in **1 fold su 5**. Non è un
effetto enorme, ma non è nemmeno nullo: senza potatura una scelta su cinque
sarebbe stata decisa da osservazioni il cui esito cade dentro il test.

### 4. Deflated Sharpe Ratio, N = 22

Due ipotesi delle ventidue — `filter_gann_1x1` e `filter_gann_1x2` — non fanno
alcun trade, quindi il loro Sharpe non è definito: sono contate in N, come
devono, ed escluse dal calcolo della dispersione.

#### 4a. Sullo Sharpe assoluto — non risponde alla domanda

| | Sharpe annuo | soglia per il migliore di 22 | PSR | DSR |
|---|---|---|---|---|
| exit_cloud_exit | 1.53 | 0.21 | 1.000 | **1.000** |
| **donchian (benchmark, mai selezionato)** | 1.39 | 0.21 | 1.000 | **1.000** |
| exit_kijun_cross | 1.50 | 0.21 | 1.000 | 1.000 |
| signal_sanyaku | 1.47 | 0.21 | 1.000 | 1.000 |

Il candidato passa. Passa anche il benchmark, che non è stato scelto da nessuna
procedura e non ha quindi nulla da deflazionare. Quando un test promuove
indistintamente la cosa da dimostrare e la cosa banale che doveva battere, il
test sta misurando altro: qui misura che undici anni di esposizione a un trend
follower producono uno Sharpe positivo, il che era noto. La soglia è così bassa
(0.21) perché le ventidue ipotesi sono varianti della stessa esposizione, quindi
i loro Sharpe stanno tutti fra 1.11 e 1.53 e la loro dispersione è minima.

#### 4b. Sul differenziale candidato − benchmark — il test che discrimina

La domanda del progetto non è mai stata "il candidato ha uno Sharpe positivo",
ma "il candidato batte il benchmark". Applicare la deflazione alla serie
differenziale — il rendimento giornaliero del candidato meno quello del
benchmark — sposta il test su quella domanda.

| | Sharpe annuo del differenziale | soglia per il migliore di 22 | PSR | DSR |
|---|---|---|---|---|
| **exit_cloud_exit − base** | **+0.28** | **0.85** | **0.829** | **0.025** |

*(Numeri a N = 22 e senza correzione di scala. Aggiornati in fondo.)*

Lettura, riga per riga:

* il vantaggio esiste ed è positivo: +0.28 di Sharpe annuo sul benchmark;
* la soglia è +0.85: è lo Sharpe differenziale che ci si aspetta dal **migliore**
  di ventidue ipotesi che non hanno alcun vantaggio. Il vantaggio osservato è
  **un terzo** di quello che il caso produce gratis in un esperimento di questa
  dimensione;
* **DSR 0.025**: la probabilità che il vantaggio vero superi quella soglia è del
  2.5%. Non è distinguibile dal miglior rumore di ventidue tentativi;
* il PSR è 0.829: anche **ignorando del tutto** quante ipotesi sono state
  provate, la probabilità che il vantaggio vero sia positivo è dell'83%, sotto
  il 95% convenzionale. Il risultato non regge nemmeno al test più indulgente
  disponibile.

`cloud_exit` è, fra le ventidue, quella con il differenziale più alto (+0.0145
per barra). È esattamente per questo che è stata scelta, ed è esattamente per
questo che la deflazione le si applica per intero.

Il differenziale ha asimmetria +4.5 e curtosi 111: è dominato da pochi giorni,
quelli in cui una delle due strategie è in posizione e l'altra no. È il motivo
per cui 4.053 osservazioni non bastano a rendere significativo un vantaggio
medio così piccolo — e il PSR lo tiene correttamente in conto, mentre uno Sharpe
letto a occhio no.

### 5. Bootstrap a blocchi circolari sul delta di MAR

2.000 ricampionamenti appaiati — gli stessi blocchi di calendario per candidato e
benchmark, perché la domanda è sul divario e non sui due livelli.

| serie | blocco | delta medio | IC 95% | P(delta ≤ 0) |
|---|---|---|---|---|
| intero periodo (in-sample) | 21 | +0.31 | [−0.09, +0.91] | 7.5% |
| intero periodo (in-sample) | 63 | +0.34 | [−0.04, +0.87] | 3.9% |
| finestre di test concatenate | 21 | +0.18 | [−0.31, +0.82] | 29.2% |
| finestre di test concatenate | 63 | +0.23 | [−0.27, +0.88] | 20.2% |

L'intervallo contiene lo zero in tutte e quattro le configurazioni. Sul periodo
in-sample il candidato ci va vicino (P ≈ 4-8%); sulle finestre concatenate, dove
il vantaggio medio si dimezza, non ci va affatto: una volta su quattro o cinque
il delta sarebbe stato negativo. E questo **senza** alcuna penalità per le
ventidue ipotesi: aggiungendola, come fa il DSR, non resta niente.

## Cosa resta vero

Un risultato negativo non cancella quello che i dati mostrano comunque.

* **`cloud_exit` non fa mai danni.** Delta positivo in 5 fold su 5 e in 7 finestre
  su 8; la finestra peggiore costa −0.66 di MAR, contro punte di +1.35. Un'uscita
  sulla nuvola al posto del canale a 20 barre non è una scelta pericolosa: è una
  scelta di cui non si può dimostrare che sia migliore.
* **Il guadagno è di drawdown, non di rendimento.** Sulle finestre concatenate il
  CAGR è identico al benchmark (5.2%) e il maxDD scende da 5.8% a 3.5%. Vale
  quanto già scritto in `ichimoku_tests.md`: questi sistemi non guadagnano di
  più, perdono di meno.
* **Il benchmark regge.** Donchian 55/20 con parametri pubblicati negli anni
  Ottanta continua a essere la cosa più difficile da battere di questo progetto,
  ventidue ipotesi dopo.

## Limiti dichiarati di questa validazione

Nessuno dei tre favorisce la conclusione negativa: due la indeboliscono.

1. **Il DSR è conservativo per costruzione.** La formula assume prove
   indipendenti; le ventidue ipotesi condividono base, dati e periodo e sono
   fortemente correlate, quindi il numero di prove *indipendenti* è minore di
   ventidue e la soglia vera è più bassa di 0.85. La direzione dell'errore è
   nota ed è quella prudente: **il DSR 0.025 è un limite inferiore**. Il PSR
   0.829, che non dipende da N, non ha questo problema e resta comunque sotto
   la soglia convenzionale.
2. **Il test sul differenziale è appropriato per `cloud_exit` e inappropriato per
   `kijun_cross` e `signal_sanyaku`.** Il differenziale misura il rendimento
   medio in più, quindi penalizza per costruzione le strategie che alzano il MAR
   rinunciando a rendimento: `kijun_cross` ha un differenziale di −0.73 annuo pur
   avendo MAR 1.36 contro 0.87. Per quelle due varianti i numeri della sezione 4b
   vanno letti come **non applicabili**, non come un fallimento. `cloud_exit` è
   l'unica che alza il CAGR e abbassa il drawdown insieme, ed è l'unica a cui il
   test si applica correttamente.
3. **Il differenziale non è un portafoglio realizzabile.** Comprare il candidato
   e vendere il benchmark richiederebbe capitale e costi doppi. È la grandezza di
   cui si vuole il segno, non una strategia.
4. **Undici anni e sei asset sono pochi** per distinguere un vantaggio di 0.28 di
   Sharpe annuo da zero, qualunque test si usi. Questo è un limite dei dati, non
   del metodo: nessuna quantità di statistica recupera informazione che nel
   campione non c'è.

## Conseguenze pratiche

1. **`cloud_exit` non va promosso a risultato del progetto.** Va descritto per
   quello che è: la migliore di ventidue varianti su un periodo unico, con un
   vantaggio che non si distingue dal rumore di selezione, e che la procedura che
   lo ha trovato non ritrova quando le si toglie il senno di poi.
2. **Non testare la ventitreesima ipotesi sugli stessi dati.** Ogni ipotesi in
   più alza la soglia del DSR per tutte le precedenti. Con la dispersione attuale
   dei differenziali, arrivare a N = 40 porterebbe la soglia da 0.85 a 0.96
   di Sharpe annuo: continuare a cercare su questo campione rende *più difficile*, non più
   facile, dimostrare qualcosa.
3. **La leva che i dati hanno mostrato funzionare resta il portafoglio.** Il
   drawdown scende da 38.7% del peggior asset singolo a 8.9% di portafoglio a
   parità di segnale: un effetto di dimensione ben maggiore di qualunque delta
   fra le ventidue varianti, e che non dipende da una selezione. È lì che vale la
   pena spendere il prossimo sforzo — più strumenti, vol targeting — non su un
   ventitreesimo filtro.
4. **Il parity test contro il Pine resta l'unica verifica mai eseguita** e
   l'unica che non richiede di cercare un vantaggio nuovo.

## Riproduzione

```bash
python3 -m pytest tests/ -q          # 70 test
python3 scripts/run_validation.py    # ~1 minuto, risultati in results/validation.json
```

Il modulo è `engine/validation.py`; il catalogo delle ipotesi, da cui si ricava
N, è `engine/hypotheses.py` — `N_HYPOTHESES` è la lunghezza del catalogo, così il
numero che entra nel Deflated Sharpe non può divergere da quello che è stato
davvero provato.

---

# Rifacimento con N = 23

Eseguito il 2026-09-15, dopo l'aggiunta di `sizing_notional` a
`engine.hypotheses.CATALOGUE`. Due cambiamenti, uno di conteggio e uno di metodo.

**Il conteggio.** `N_HYPOTHESES` passa da 22 a 23, quindi la soglia del DSR sale
per *tutte* le ipotesi precedenti. È il meccanismo previsto dalla regola 4, e qui
si vede quanto morde: non è solo N a salire, è la **dispersione** dei tentativi.
`sizing_notional` ha il differenziale grezzo più alto di tutti — +1.43 di Sharpe
annuo contro +0.28 di `cloud_exit` — quindi allarga di molto la distribuzione dei
ventitré tentativi, e la soglia del migliore-per-caso passa da **0.85 a 1.19**.

**Il metodo.** Serviva un test che il documento originale non aveva.
`sizing_notional` gira a **3.35 volte la volatilità del benchmark**: il suo
differenziale grezzo è positivo *per costruzione*, e il DSR calcolato su quello
misura la scala, non il vantaggio. È la stessa trappola del MAR che lusinga la
leva (`results/universe_extended.md`), spostata di una formula.
`engine.validation.volatility_matched` riscala ogni serie alla volatilità del
benchmark prima di differenziare. Per le ventidue varianti che girano allo stesso
`risk_pct` il fattore è fra 0.6 e 1.0 e cambia poco; per la ventitreesima cambia
tutto — ed è per questo che si applica a tutte, invece di trattarne una in modo
speciale.

## I numeri

### Differenziale grezzo, N = 23 (non usare per concludere)

| | vol/base | Sharpe annuo | soglia (23) | PSR | DSR |
|---|---|---|---|---|---|
| **sizing_notional − base** | 3.35 | **+1.43** | 1.19 | 1.000 | **0.784** |
| exit_cloud_exit − base | 0.96 | +0.28 | 1.19 | 0.829 | **0.001** |
| exit_kijun_cross − base | 0.61 | −0.73 | 1.19 | 0.006 | 0.000 |
| signal_sanyaku − base | 0.76 | −0.48 | 1.19 | 0.054 | 0.000 |

Letto così, la ventitreesima ipotesi sembra l'unica viva del progetto: DSR 0.784,
"dubbio" invece di "non distinguibile", e il differenziale più alto mai misurato
qui dentro. **È un artefatto**, e la riga `vol/base` dice quale.

### Differenziale a parità di volatilità, N = 23 (il test valido)

| | vol/base | Sharpe annuo | soglia (23) | PSR | DSR |
|---|---|---|---|---|---|
| **exit_cloud_exit − base** | 0.96 | **+0.48** | 0.89 | 0.952 | **0.074** |
| **sizing_notional − base** | 3.35 | **+0.20** | 0.89 | 0.750 | **0.011** |

Riscalata alla volatilità del benchmark, la ventitreesima ipotesi passa da +1.43
a **+0.20** di Sharpe annuo: **l'86% del suo vantaggio apparente era scala.** Il
DSR crolla da 0.784 a **0.011**, il più basso dei due. Non è distinguibile dal
rumore di ventitré tentativi, e nemmeno dal rumore di uno solo — il suo PSR è
0.750, sotto il 95% convenzionale anche ignorando del tutto quante ipotesi sono
state provate.

Nello stesso test `cloud_exit` risulta il differenziale più alto dei ventitré, con
DSR 0.074: più alto del 0.025 pubblicato, perché la correzione di scala restringe
la dispersione dei tentativi e abbassa la soglia da 1.19 a 0.89. Resta comunque
**non distinguibile**, e resta l'ipotesi non falsificata che era.

### La procedura di selezione, con 24 varianti nel pool

| | pubblicato (23 varianti) | ora (24 varianti) |
|---|---|---|
| delta MAR medio, fuori campione | −0.04 | **−0.10** |
| mediana | +0.08 | +0.04 |
| finestre positive | 5/8 | 4/8 |
| ρ di rango IS vs OOS, mediana | 0.14 | **+0.02** |

`sizing_notional` viene scelta in **1 finestra su 8**, e in quella finestra fa
**−0.08** di MAR contro il benchmark. Aggiungere un'ipotesi al pool ha peggiorato
la procedura, che è il comportamento che ci si aspetta aggiungendo rumore a un
menu di scelte fra cui non c'è niente di buono.

## Verdetto sulla ventitreesima ipotesi

**Falsificata come vantaggio, confermata come artefatto di misura.**

Il percorso, per intero, perché è istruttivo:

1. la curva del rischio per trade mostrava il MAR salire da 0.89 a 1.50 —
   **artefatto**, il MAR lusinga la leva, e a leva pura lo Sharpe è costante;
2. lo Sharpe però saliva davvero, da 1.18 a 1.41 — **reale**, ma non per la leva:
   sopra il 2% il tetto sul capitale spegneva il sizing ATR;
3. formulata come regola esplicita e parametro-libera, `sizing_notional` prende
   MAR 1.27 in-sample, quarta su ventitré — **artefatto di nuovo**, il suo maxDD
   è 23% contro 8.9% e i due MAR non sono confrontabili;
4. il differenziale grezzo dà DSR 0.784, il migliore del progetto — **artefatto
   un'ultima volta**, gira a 3.35× la scala;
5. a parità di volatilità: **+0.20 di Sharpe annuo, DSR 0.011, 2 asset su 6.**

Quattro livelli di misura, ognuno dei quali sembrava un risultato e nessuno dei
quali lo era. Lo Sharpe che sale da 1.18 a 1.41 resta vero: semplicemente non
sopravvive a essere confrontato a parità di rischio con le altre ventidue cose
già provate sugli stessi dati.

## Cosa cambia nel resto del progetto

* **N = 23** è ora la lunghezza di `engine.hypotheses.CATALOGUE`, e ogni futuro
  DSR la usa senza che nessuno debba ricordarsene.
* **Il benchmark non si muove**: 0.87 / 1.39 / 7.7% / 8.9% / 303 trade. Nessun
  numero di `benchmark_donchian.md`, `comparison.md`, `ablation.md` o
  `ichimoku_tests.md` dipende da N.
* **La conclusione su `cloud_exit` non cambia**, e il suo DSR corretto (0.074) è
  più alto di quello pubblicato (0.025). Resta sotto ogni soglia: non falsificata,
  non confermata.
* **La soglia è ora 0.89 di Sharpe annuo** (a parità di volatilità) contro lo 0.85
  di prima. Chi volesse una ventiquattresima ipotesi la alzerebbe ancora.
