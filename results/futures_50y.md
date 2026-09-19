# Donchian 55/20 su 30 futures, 1970-2024 — **fallito**

Eseguito il 2026-09-16 con `scripts/run_futures50.py`, secondo
`results/preregistrazione_futures.md`, committata prima del run.

## L'esito pre-registrato

| | valore | soglia dichiarata prima |
|---|---|---|
| Sharpe di portafoglio | **−0.30** | — |
| SR/SE su 54 anni | **−2.17** | > 1.96 |
| MAR | −0.01 | — |
| mercati con MAR positivo | **9/30** | — |
| maxDD | 52.3% | — |

**Non distinguibile da zero, e nella direzione sbagliata.** 30 mercati,
1970-2024, 333.459 barre, 12.705 trade.

## Perché è fallito: un parametro che ho scelto male io

Non è il mercato ad aver risposto. È l'assunzione sui costi.

La pre-registrazione dichiarava `costs.DEFAULT` — 0.05% di commissione più 0.10%
di slippage per lato, **0.30% di round-trip**. Quel numero è tarato su crypto ed
ETF. Per un future liquido il round-trip reale sta fra **0.01% e 0.03%**: ho
dichiarato un costo dieci-trenta volte quello vero.

Con ~8 trade per mercato all'anno, lo 0.30% vale **2.4% annuo di attrito** contro
un rendimento lordo di circa il 2%. Il test non poteva che fallire, e quello che
ha misurato è la mia assunzione, non il mercato.

La sensibilità — che la pre-registrazione *richiedeva* di riportare — lo mostra
senza ambiguità:

| round-trip | MAR | Sharpe | maxDD | mercati positivi |
|---|---|---|---|---|
| **0.30% (dichiarato)** | **−0.01** | **−0.30** | 52.3% | 9/30 |
| 0.15% | 0.07 | 0.59 | 14.7% | 14/30 |
| 0.06% | 0.22 | 0.94 | 7.7% | 25/30 |
| 0.03% (realistico) | 0.30 | **1.03** | 6.2% | **28/30** |
| zero | 0.38 | 1.11 | 5.2% | 28/30 |

## Cosa **non** si può concludere

**Che il trend following funzioni su questi mercati.** La riga da Sharpe 1.03 è
suggestiva e non è dimostrativa, e la differenza non è formale: il costo è stato
cambiato **dopo** aver visto che quello dichiarato falliva. È esattamente ciò che
la pre-registrazione esiste per impedire, e vale anche quando la ragione del
cambio è buona.

**Il privilegio di N = 1 su questi trenta mercati è speso.** Il risultato è stato
visto; non può essere non visto. Qualunque riesecuzione su questo insieme, con
qualunque costo, è contaminata.

## Cosa si può concludere, e vale

**Questa strategia su questi mercati vive o muore su due decimi di punto per
trade.** Fra 0.30% e 0.03% di round-trip lo Sharpe passa da −0.30 a +1.03 e i
mercati in guadagno da 9 a 28. Non è una sfumatura: è la variabile dominante, più
del segnale, più dell'universo, più del mezzo secolo di storia.

Ne segue una regola operativa che vale oltre questo test: **per una strategia ad
alta frequenza di trade, il modello di costo non è un dettaglio di contorno ma un
parametro di primo ordine, e va specificato per classe di strumento prima di
qualunque altra cosa.** `costs.DEFAULT` non è un default neutro: è un'assunzione,
e applicarla fuori dalla classe per cui è stata tarata è un difetto di misura
come lo era la pausa della v5.5.

## La via di recupero

L'universo di Carver ha **252 mercati**. Ne sono stati usati 49 (≥30 anni) e ne
sono sopravvissuti 30 al filtro sui prezzi negativi. **Restano oltre duecento
mercati mai guardati** — quelli fra i 15 e i 30 anni di storia, più i 19 esclusi
qui, che con un aggiustamento diverso potrebbero rientrare.

Un secondo test, con i costi specificati per classe di strumento **prima**, su un
insieme **disgiunto** di mercati, riparte legittimamente da N = 1. È l'unica
strada che resta dopo aver bruciato questa, e richiede una pre-registrazione
nuova, scritta prima di caricare quei dati.
