# Donchian 55/20 su 35 futures, 1995-2024 — **passa alla lettera, non regge alla prova**

Eseguito il 2026-09-16 con `scripts/run_futures50_2.py`, secondo
`results/preregistrazione_futures_2.md`, committata prima del run.

## L'esito pre-registrato

| | valore | soglia dichiarata prima |
|---|---|---|
| Sharpe di portafoglio (costo 20% sigma) | **0.48** | — |
| **SR/SE su 28.6 anni** | **2.44** | **> 1.96** |
| MAR | 0.12 | — |
| mercati con MAR positivo | 17/53 (35 esclusi/inclusi: 17/35) | — |

**Per la lettera della pre-registrazione: superato.** 35 mercati (53 meno 18
esclusi per lo stesso difetto dei dati del primo test), 1995-2024, 191.430
barre, 4.408 trade. La sensibilità richiesta:

| livello di costo | Sharpe | SR/SE | mercati positivi |
|---|---|---|---|
| 20% sigma (verdetto) | 0.48 | **2.44** | 17/35 |
| 10% sigma | 0.67 | 3.23 | 20/35 |
| 5% sigma | 0.76 | 3.58 | 20/35 |

## Perché questo non è un risultato, nonostante il numero

La pre-registrazione impediva di cambiare un parametro dopo aver visto fallire
la soglia. Non impediva di **caratterizzare** un successo — ed è esattamente
quello che il progetto ha sempre fatto (i tre trade che erano il 65% del
profitto su ETH nel benchmark originale, l'ingresso E1 che valeva il 71% del
PnL della v5.5). Farlo qui ha trovato un problema serio.

**Il 110% del PnL totale del portafoglio viene da due mercati: MILK e
MILKWET.** Gli altri 33 mercati, nel complesso, sono in perdita netta.

| mercato | quota del PnL totale | trade | R-multiple dei 3 trade migliori |
|---|---|---|---|
| MILK | 56.7% | 142 | 15.6 / 29.3 / 17.0 |
| MILKWET | 36.4% | 78 | 31.6 / 40.2 / 25.8 |

**Tolto il solo mercato migliore (MILK), SR/SE scende da 2.44 a 1.06 — sotto la
soglia di 1.96.** Il risultato non è un vantaggio distribuito su un universo
ampio: è due mercati che trascinano trentatré.

## La causa, verificata e non solo sospettata

`validate_series.py` aveva già segnalato entrambi prima di eseguire il test:
**MILKWET ha il 58% delle barre copiate dalla precedente, MILK l'11%.** Sono
quotazioni ferme per giorni — non movimento di mercato, illiquidità della serie
sorgente.

Il meccanismo con cui questo produce risultati che sembrano ottimi è meccanico,
non statistico: con il prezzo fermo per giorni, l'ATR misurato collassa verso
zero; lo stop (2×ATR) diventa minuscolo; il sizing, che è rischio/distanza dello
stop, si gonfia di conseguenza; e quando il prezzo infine si muove — anche di
poco — il trade vince per un R-multiple enorme. **R-multiple di 15-40 non sono
un edge: sono la firma di uno stop calcolato su una volatilità che i dati
sottostimano.** Il costo, calibrato sulla stessa sigma collassata, è a sua
volta artificialmente basso su questi due mercati — un secondo modo in cui lo
stesso difetto dei dati si traduce in un risultato migliore di quanto sia.

## Perché il filtro pre-registrato non li ha presi

L'esclusione dichiarata (prezzo ≤ 0, salto oltre il 50%) intercetta un difetto
diverso — l'attraversamento dello zero nel back-adjustment per differenza — non
le quotazioni stantie. I due difetti sono indipendenti e **nessuno dei due
implica l'altro**: MILK e MILKWET passano il filtro sui prezzi negativi perché
non ce l'hanno, e hanno comunque un difetto che rende il loro Donchian
inaffidabile.

## Il verdetto onesto

**Non si può dire che il trend following abbia un vantaggio su questo
universo.** Il numero che soddisfa la soglia pre-registrata esiste, ma non è
robusto al controllo più elementare — togliere il primo contribuente — e la
ragione per cui non lo è si identifica con precisione in un difetto dei dati
che il progetto stesso aveva già segnalato prima di eseguire.

Non è lo stesso genere di fallimento del primo test. Lì l'errore era mio, in
un parametro dichiarato male. Qui l'errore è nel campione: due serie che non
avrebbero dovuto essere trattate come osservazioni indipendenti di un mercato
liquido.

## Cosa NON si fa adesso

Non si toglie MILK e MILKWET e si ripete il conteggio. Sarebbe scegliere
un'esclusione **dopo** aver visto quali mercati salvano il risultato — la
stessa cosa che ha reso inutilizzabile il primo test, capovolta: là il
parametro comodo era stato scelto dopo un fallimento, qui sarebbe
un'esclusione comoda scelta dopo un successo. Il privilegio di questo campione
(15-30 anni, disgiunto dal primo) è speso, come lo speso del primo.

Una regola **generale** che vale per test futuri su qualunque campione nuovo,
questa sì dichiarabile in anticipo la prossima volta: **escludere le serie con
più del 5% di barre ripetute dalla precedente prima di guardare qualunque
risultato**, non dopo. `validate_series.py` calcola già questo numero — va
promosso da segnalazione a filtro.

## Cosa resta, di solido

Due campioni sono ora bruciati (≥30 anni e 15-30 anni dell'universo di
pysystemtrade), con esiti diversi ma entrambi istruttivi: il primo è fallito
per un costo mal specificato, il secondo passa alla lettera ma non regge alla
diagnostica per un difetto di liquidità delle serie. In nessuno dei due casi il
trend following ha mostrato un vantaggio che sopravviva al controllo.

Quello che si è imparato, ed entra nelle regole di lavoro per la prossima
volta: **la soglia di qualità dei dati non può fermarsi a "niente prezzi
negativi"**. Serie stantie producono ATR sottostimato, stop troppo stretti,
sizing gonfiato e R-multiple che sembrano un vantaggio e sono un artefatto — lo
stesso tipo di errore della pausa della v5.5, questa volta nei dati invece che
nel codice.
