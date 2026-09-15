# Il rischio per trade, scelto fuori campione

Eseguito il 2026-09-15 con `python3 scripts/run_risk_walkforward.py`, che applica
al rischio per trade lo stesso protocollo che `run_validation.py` applica alle
ventidue ipotesi: si sceglie dentro la finestra di training, si misura sulla
finestra di test mai vista.

Nasce da una domanda diretta: la curva del rischio in `universe_extended.md` ha
un massimo al 4-8%, ma quel massimo è letto su tutto il periodo — è scelto con il
senno di poi. Quanto ne resta senza quel privilegio?

Il termine di paragone di ogni confronto è **il rischio fisso all'1%**, cioè il
valore con cui è stato misurato tutto il progetto: la domanda non è "alzare il
rischio batte zero", è "alzare il rischio batte il non scegliere".

## La risposta breve

**Fuori campione l'ottimo è il 4%, non l'1%, e lo è su tutte e quattro le
configurazioni provate.** Ma la *procedura* che lo sceglie anno per anno non è
affidabile, e — soprattutto — **ciò che migliora non è la leva.** Sono tre
affermazioni separate e vanno tenute separate.

## 1. L'ottimo fuori campione

MAR e Sharpe sulle otto finestre di test concatenate (2018-08 → 2026-08), cioè
solo su dati mai usati per scegliere:

| rischio | sei solo long | sei long/short | quindici | tredici no-crypto |
|---|---|---|---|---|
| 0.5% | 0.73 | 0.76 | 0.58 | 0.15 |
| **1%** *(pubblicato)* | 0.87 | 0.90 | 0.73 | 0.21 |
| 2% | 1.05 | 1.09 | 0.94 | 0.31 |
| **4%** | **1.30** | **1.21** | 1.07 | **0.38** |
| 8% | **1.37** | 1.03 | 1.09 | 0.33 |
| 16% | 1.34 | 0.96 | **1.09** | 0.31 |
| 32% | 1.34 | 0.94 | 1.09 | 0.31 |

Lo **Sharpe** fuori campione ha il massimo al 4% in tutte e quattro le colonne:
1.37 contro 1.21 sui sei solo long, 1.34 contro 1.19 long/short, 1.13 contro 0.84
sui quindici, 0.64 contro 0.35 sui tredici. È l'unica cosa in questo progetto che
si sia mossa nella stessa direzione su ogni universo provato, crypto e non.

Nota che sui tredici senza crypto l'ottimo resta **0.38 di MAR e 2.2% di CAGR**:
il livello non cambia, cambia solo la pendenza. Alzare il rischio non crea un
vantaggio dove non c'è.

## 2. La procedura che sceglie il rischio non funziona

Dentro ogni finestra di training di tre anni si prende il rischio con il MAR
migliore e lo si applica all'anno successivo:

| universo | delta MAR medio | finestre positive | ρ di rango IS vs OOS |
|---|---|---|---|
| sei, solo long | +0.41 | 4/8 | **−0.04** |
| sei, long/short | +0.68 | 6/8 | +0.31 |
| quindici | +0.46 | 7/8 | +0.58 |
| tredici no-crypto | +0.07 | 3/8 | **−0.22** |

Sui sei solo long la mediana del delta è **−0.01** e la deviazione standard 1.19:
la media +0.41 è interamente una finestra sola, il 2020-08 → 2021-08, che vale
+3.26 da sola. Il ρ di rango medio è −0.04: **la classifica in-sample dei livelli
di rischio non predice quella fuori campione.**

Il k-fold purgato è più generoso (positivo in 5/5 fold, +0.77 medio), ma il suo
training vede dati successivi al test: è un test di stabilità, non della
decisione in tempo reale. Vale qui la stessa gerarchia dichiarata in
`validation.md` — il walk-forward con selezione è l'unico che riproduce onestamente
cosa sarebbe successo decidendo al momento.

Conclusione: **il 4% si può fissare una volta, non si può inseguire.** Chi lo
ri-sceglie ogni anno guardando gli ultimi tre non fa meglio di chi lascia l'1%.

## 3. Quello che migliora non è la leva — correzione

La sezione sulla leva in `universe_extended.md`, scritta poche ore prima di
questa, diceva che "il MAR sale con la dimensione della posizione". È vero come
osservazione e **fuorviante come spiegazione**. Le due cose si separano
misurandole:

**A. Leva pura** — si prendono i rendimenti del backtest a rischio 1% e si
moltiplicano per *k*. Stessi trade, stessa regola di sizing, solo scala:

| k | CAGR | maxDD | MAR | Sharpe |
|---|---|---|---|---|
| 1 | 7.6% | 8.5% | 0.89 | **1.18** |
| 2 | 15.4% | 16.5% | 0.93 | **1.18** |
| 4 | 31.7% | 31.0% | 1.02 | **1.18** |
| 8 | 66.0% | 54.2% | 1.22 | **1.18** |

Lo Sharpe è **esattamente costante**, come dev'essere. Il MAR sale da 0.89 a 1.22
e quella salita è **interamente l'artefatto di misura**: il drawdown percentuale
è limitato da 100% e cresce sublinearmente, il rendimento composto cresce
superlinearmente. La leva pura non migliora niente. Non c'era nessun pasto
gratis, e la sezione precedente lasciava intendere di sì.

**B. Rischio alzato nel motore** — stessa griglia, ma passando `risk_pct` al
backtest:

| rischio | CAGR | maxDD | MAR | Sharpe |
|---|---|---|---|---|
| 1% | 7.6% | 8.5% | 0.89 | 1.18 |
| 2% | 13.4% | 10.3% | 1.29 | 1.29 |
| 4% | 21.4% | 14.2% | 1.50 | **1.39** |
| 8% | 27.7% | 18.5% | 1.50 | **1.41** |

Qui lo Sharpe sale davvero, da 1.18 a 1.41. Non è scala: è un'altra distribuzione
di rendimenti. Il meccanismo è in `backtest.run`, riga del sizing:

```python
size = min(risk_amount / dist, st.cash * max_notional_pct / fill)
```

Quante volte morde il secondo termine, sui sei solo long:

| rischio | trade aperti al tetto del capitale |
|---|---|
| 1% | 13 / 178 |
| 2% | 86 / 178 |
| 4% | 132 / 178 |
| 8% | **142 / 178** |
| 16% | 143 / 178 |

A rischio 8% l'80% dei trade **non è dimensionato dall'ATR**: è dimensionato dal
contante disponibile. Cioè il parametro `risk_pct`, oltre il 2%, non regola più
il rischio — spegne la regola di sizing proporzionale all'ATR e la sostituisce
con "compra quanto il capitale consente".

**Quindi il risultato vero di questo documento non è "alzare il rischio al 4%".
È: su questi dati il sizing a nozionale costante batte il sizing proporzionale
all'ATR, e vale +0.21 di Sharpe.** Il rischio per trade è solo la manopola grezza
che commuta fra i due regimi, e la saturazione oltre il 16% è il punto in cui la
commutazione è completa.

## Cosa farne

> **Aggiornamento, stesso giorno: fatto.** L'ipotesi è stata aggiunta al catalogo
> come `sizing_notional`, N è passato a 23 e il DSR è stato rifatto. Esito:
> **falsificata** — a parità di volatilità il vantaggio è +0.20 di Sharpe annuo
> con DSR 0.011, contro il +1.43 e DSR 0.784 del differenziale grezzo. L'86% era
> scala. Vedi `results/validation.md`, sezione «Rifacimento con N = 23». Quanto
> segue è il ragionamento con cui la decisione è stata posta, e resta valido come
> procedura.

È un'**ipotesi nuova, la ventitreesima**, e non è stata cercata: è caduta fuori da
una misura richiesta. Il che non la rende esente dalle regole.

* Non è stata aggiunta a `engine/hypotheses.CATALOGUE`, quindi **N resta 22** e
  nessun numero pubblicato cambia. Aggiungerla alza la soglia del DSR per tutte le
  ventidue precedenti, ed è una decisione che non si prende di soppiatto.
* Se la si vuole trattare come risultato serve il protocollo completo: dichiararla
  come ipotesi di sizing (non di rischio), riformularla come regola esplicita
  — nozionale costante, o inverso della volatilità — invece che come effetto
  collaterale di un tetto, e passarla dal DSR con N = 23.
* Formulata correttamente potrebbe anche non sopravvivere: +0.21 di Sharpe è nello
  stesso ordine di grandezza dei 0.28 che `validation.md` dichiara
  indistinguibili da zero su questo campione.

Fino ad allora vale quello che vale per `cloud_exit`: **non falsificata, non
confermata.** E il rischio resta all'1% in tutti i runner, perché cambiarlo
renderebbe incomparabili tutti i numeri già pubblicati.

## Limiti

1. **Le finestre di test partono dal 2018.** Servono tre anni di training, quindi
   il periodo misurato fuori campione è otto anni su undici, e sono gli otto in
   cui le crypto hanno dominato.
2. **Un MAR su una finestra di un anno è rumoroso.** Contano le distribuzioni,
   non le righe singole — ed è esattamente perché la media +0.41 su una mediana
   −0.01 non è un risultato.
3. **La griglia è dichiarata, non cercata**: logaritmica, due ordini di grandezza
   intorno all'1%, fermata al 32% dove il motore satura. Una griglia più fitta
   intorno al massimo sarebbe ottimizzazione.
4. **Nessun margine, nessun costo di finanziamento.** `max_notional_pct = 1.0`: il
   motore non presta denaro. Un conto vero con margine avrebbe una curva diversa
   e un costo che qui non è modellato.
5. **Il gap oltre lo stop non è modellato più gentilmente qui che altrove.** A
   rischio 4-8% nominale la perdita realizzata di un singolo trade può eccedere di
   molto il rischio dichiarato, e nessuna di queste medie lo mostra.

## Riproduzione

```bash
python3 scripts/run_risk_walkforward.py                      # i sei, solo long
python3 scripts/run_risk_walkforward.py --short              # i sei, long/short
python3 scripts/run_risk_walkforward.py --universe extended  # i quindici
python3 scripts/run_risk_walkforward.py --universe no-crypto # i tredici
```
