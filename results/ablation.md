# Ablazione: quali componenti aggiungono qualcosa al benchmark

Eseguito il 2026-09-15 con `scripts/run_ablation.py`. Base identica per tutti —
Donchian 55/20 long-short, parametri Turtle — un filtro alla volta applicato
solo come gate sugli ingressi. Periodo 2015-08-10 → 2026-09-14, sei asset,
stessi costi.

**Base: MAR 0.87 · Sharpe 1.39 · CAGR 7.7% · maxDD 8.9% · 303 trade**

## Risultato

| Filtro | MAR | Δ MAR | Sharpe | Trade | Asset migliorati |
|---|---|---|---|---|---|
| ichi_chikou | 0.87 | +0.00 | 1.39 | 303 | 0/6 |
| ichi_cloud | 0.86 | −0.01 | 1.38 | 299 | 3/6 |
| adx_15 | 0.86 | −0.01 | 1.37 | 290 | 2/6 |
| ichi_tk | 0.85 | −0.02 | 1.37 | 300 | 1/6 |
| gann_1x8 | 0.84 | −0.03 | 1.36 | 267 | 1/6 |
| ichi_full | 0.84 | −0.03 | 1.36 | 296 | 2/6 |
| ichi_thick | 0.77 | −0.10 | 1.28 | 287 | 0/6 |
| sma_200 | 0.70 | −0.17 | 1.25 | 266 | 1/6 |
| gann_oct_4_8 | 0.67 | −0.20 | 1.23 | 240 | 2/6 |
| gann_oct_5_8 | 0.67 | −0.20 | 1.24 | 218 | 2/6 |
| ctrl_mid_lineare | 0.67 | −0.20 | 1.23 | 244 | 3/6 |
| ichi_htf | 0.66 | −0.21 | 1.23 | 171 | 2/6 |
| gann_1x4 | 0.56 | −0.31 | 1.11 | 145 | 1/6 |
| gann_1x1 | — | — | — | **0** | 0/6 |
| gann_1x2 | — | — | — | **0** | 0/6 |

**Nessun filtro migliora la base.** Quindici ipotesi testate, il migliore pareggia
e tutti gli altri peggiorano. Nessun risultato da correggere per test multipli,
perché non c'è nessun risultato positivo da correggere.

## Tre cose che l'ablazione dimostra

### 1. L'angolo 1×1 di Gann non è una soglia che il mercato attraversa

Normalizzando la pendenza in ATR per barra su 26 barre, la pendenza massima
osservata in undici anni è:

| BTC | ETH | GOLD | CRUDE | CORN | EQUITY |
|---|---|---|---|---|---|
| 0.46 | 0.47 | 0.45 | 0.46 | 0.43 | 0.49 |

Mai sopra 0.5 su nessun asset. La 1×1 (soglia 1.0) e la 1×2 (0.5) producono
**zero trade**, e non per un difetto: è una proprietà della scala.

Il prezzo diffonde come **radice del tempo** — la deriva netta su *n* barre
scala come √n × volatilità per barra — mentre una retta a pendenza fissa cresce
come *n*. Il rapporto fra i due va quindi a zero come 1/√n: qualunque retta
"un'unità di prezzo per unità di tempo" diventa irraggiungibile al crescere
dell'orizzonte. Su 26 barre il valore tipico è circa 1/√26 ≈ 0.2, e infatti i
massimi osservati stanno intorno a 0.45, poco più del doppio, com'è atteso con
code grasse.

Questo spiega anche perché Gann funziona "a occhio": la 1×1 diventa attraversabile
solo scegliendo una scala del grafico su misura, e **quella scelta è il vero
parametro libero**. Una volta resa dimensionalmente coerente, l'ipotesi non è
falsa — è vuota.

### 2. Gli ottavi non aggiungono nulla agli ottavi

Tre varianti, lo stesso identico risultato:

* 4/8 in log-price: MAR 0.67
* 5/8 in log-price, l'ottavo a cui Gann attribuiva più peso: MAR 0.67
* **controllo**: 4/8 in prezzo lineare: MAR 0.67

Il 5/8 non batte il 4/8, e il logaritmo non cambia niente rispetto al lineare.
Gli ottavi si riducono a un banale "prezzo nella metà alta del range a 252
barre", e quel filtro da solo costa 0.20 di MAR. L'ipotesi degli ottavi era
l'unica di Gann che la ricerca non aveva già scartato; ora è scartata anche
questa, con il suo controllo.

### 3. Il Chikou è esattamente ridondante con un breakout

Il filtro Chikou blocca **0 ingressi su 1.728 barre di breakout**, su tutti e sei
gli asset. Non "quasi nessuno": zero. Un breakout a 55 barre implica
logicamente che il close superi il massimo di 26 barre fa, quindi la condizione
Chikou è già contenuta nel segnale. Non è un filtro debole, è una tautologia.

## Il resto della classifica

`ichi_htf` è il filtro Ichimoku più dannoso: taglia i trade da 303 a 171 e perde
0.21 di MAR. È lo stesso gate di regime su timeframe superiore che sia la v3.2
sia la v5.5 usano come cardine.

`sma_200` perde 0.17, `adx_15` pareggia a meno di un centesimo. Anche i filtri
occidentali, sopra un trend follower, non aggiungono.

## Limite del test, dichiarato

I filtri sono applicati **solo agli ingressi**, sopra una base che è già essa
stessa un filtro di trend. In questa configurazione i filtri di trend di
Ichimoku sono ridondanti quasi per costruzione, e il test lo conferma
misurandolo. Restano fuori due domande diverse, che questo studio non affronta:

* Ichimoku sopra una base **mean-reverting** invece che trend following;
* Ichimoku come meccanismo di **uscita** invece che di ingresso — il trail sulla
  nuvola o sul Kijun è l'unico pezzo delle due strategie Pine che non è stato
  isolato qui.

La seconda è l'unica direzione che, sulla base di questi numeri, riterrei ancora
sensata.
