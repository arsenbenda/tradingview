# Pre-registrazione — i livelli agiscono da supporto e resistenza?

**Scritta e committata prima di eseguire.** Il commit che introduce questo file
non contiene risultati; quello successivo li aggiunge sotto la riga di verdetto
senza toccare niente qui sopra.

## La domanda, e perché è nuova

Il progetto ha misurato Ichimoku e Gann **solo come condizioni binarie dentro una
strategia**: sei filtri, tre segnali, quattro uscite. Mai come *livelli di prezzo
di cui si misura la reazione*. Le due cose non sono la stessa:

* una strategia consuma undici anni per produrre ~300 trade, e con 300 trade non
  si distingue niente — è il muro contro cui ha sbattuto ogni conclusione;
* una statistica di reazione su **~11.000 tocchi** ha due ordini di grandezza di
  potenza in più, e risponde alla domanda diretta.

La domanda diretta è: **il prezzo reagisce a questi livelli più di quanto
reagirebbe a un livello qualunque messo alla stessa distanza?**

## Perché la nuvola è il primario, deciso adesso

Fra i livelli in esame la nuvola ha una proprietà che nessun altro ha, ed è già
nel motore (`indicators.ichimoku`):

```python
# la nuvola sopra la barra corrente e' stata calcolata disp barre fa
span_a_now = senkou_a.shift(disp)
```

**Il livello alla barra `t` è stato fissato alla barra `t−26`.** Esiste prima che
il prezzo ci arrivi. Tenkan e Kijun sono medie del range recente e si muovono
*con* il prezzo; la nuvola è congelata. È il solo livello per cui «predizione» è
letterale: il valore di domani si conosce oggi, l'unica incognita è se verrà
rispettato.

La seconda ragione è la frequenza, misurata prima di scegliere:

| livello | tocchi | % delle barre | distanza mediana \|close−livello\| |
|---|---|---|---|
| tenkan | 5.496 | **28.6%** | **0.85 ATR** |
| kijun | 2.729 | 14.3% | 1.57 ATR |
| **cloud_top** | 1.333 | **7.1%** | **3.30 ATR** |
| **cloud_bot** | 1.301 | 6.9% | 3.42 ATR |

Il Tenkan è toccato su più di una barra su quattro a meno di un ATR: «il prezzo
rispetta il Tenkan» è quasi «il prezzo sta vicino a una media a 9 barre», vero per
costruzione. È la terza volta che il progetto incontra questa struttura, dopo il
Chikou (0 ingressi bloccati su 1.728) e il Peak-AVWAP (gate aperto al 99.8% sulle
rotture). La nuvola invece è **rara e lontana**.

## Specifica esatta, fissata adesso

### I livelli

**Famiglia primaria — `cloud`.** `cloud_top` e `cloud_bot` come li calcola
`indicators.ichimoku` con i parametri canonici (9/26/52, displacement 26),
riuniti in una famiglia sola perché l'affermazione da testare è «la nuvola fa da
supporto e resistenza», non «il bordo superiore sì e l'inferiore no». Il dettaglio
per bordo si riporta come descrittivo.

**Famiglie secondarie, esplorative:** `tenkan`, `kijun`, e i **sette ottavi di
Gann** (1/8 … 7/8) in log-price sul range definito, a ogni barra, dal **pivot
massimo confermato più recente e dal pivot minimo confermato più recente**.

I pivot sono frattali con `k = 20` barre di conferma per lato, e il livello è
utilizzabile **solo da `pivot + k` in avanti**: il pivot su `t` non è noto prima
di `t + k`. Nessuna coppia arbitraria di estremi storici — solo la più recente,
che è anche l'unica che un operatore userebbe. Il `k = 20` è fissato qui e non
verranno provati altri valori.

### L'evento «tocco»

Bar `t` tocca il livello `L` se `low[t] ≤ L ≤ high[t]`.

Per evitare di contare dieci volte lo stesso episodio, un **evento** è il primo
tocco dopo almeno **5 barre** senza tocchi di quel livello. La direzione di
avvicinamento la decide la barra precedente: `close[t−1] < L` è un test di
**resistenza**, `close[t−1] > L` di **supporto**.

### La reazione: una corsa fra due barriere

Niente orizzonte arbitrario e niente soglia sul rendimento. Dal tocco in avanti,
si guarda quale delle due cose succede **prima**:

* il prezzo si allontana di **1.0 ATR(14)** dal livello, dal lato da cui veniva
  → **rifiuto** (il livello ha tenuto);
* il prezzo lo attraversa di **1.0 ATR(14)** → **rottura**;
* nessuna delle due entro **20 barre** → **censurato**, escluso dal rapporto.

`P(rifiuto) = rifiuti / (rifiuti + rotture)`. È simmetrica, adimensionale e non
ha parametri scelti guardando i risultati.

### Il placebo: lo stesso livello, spostato

È la parte che rende il test decisivo, e che manca a tutta la letteratura su
supporti e resistenze.

Per ogni livello reale si generano **5 livelli placebo** spostandolo di
`δ = s · u · ATR(14)` con `s` segno casuale e `u ~ U(0.5, 1.5)`, e si ripete su
ciascuno la stessa procedura di tocco e di corsa.

Il placebo è per costruzione appaiato su **distanza percorsa dal prezzo, regime di
volatilità, asset, epoca e direzione di avvicinamento**. L'unica cosa che cambia è
*la posizione esatta*. Quindi:

> Se il livello reale non rifiuta più del suo placebo spostato di un ATR, quello
> che si stava misurando non era il livello: era il fatto che il prezzo abbia
> percorso quella distanza.

Lo spostamento minimo è 0.5 ATR perché sotto quella soglia il placebo sarebbe lo
stesso livello con un'altra etichetta; il massimo è 1.5 ATR perché oltre le
condizioni di mercato non sono più confrontabili.

Il confronto ingenuo — livello reale contro «una barra qualunque» — sarebbe
inutile: un tocco di nuvola arriva dopo 3.3 ATR di viaggio, quindi seleziona
periodi di tendenza, e produrrebbe un risultato positivo per una ragione che con
Ichimoku non c'entra niente.

### La statistica

`Δ = P(rifiuto | livello reale) − P(rifiuto | placebo)`, con intervallo di
confidenza al 95% per **bootstrap sugli eventi**, 2000 ricampionamenti,
raggruppati per asset.

## Regola di decisione, fissata adesso

**La famiglia primaria `cloud` agisce da supporto e resistenza** se e solo se:

1. `Δ > 0`;
2. l'intervallo di confidenza al 95% su `Δ` **esclude lo zero**;
3. vale su **almeno 4 dei 6 asset** nel segno (regola 5: un effetto su un asset
   è un effetto di quell'asset).

Qualunque altro esito è riportato come «non agisce da supporto e resistenza in
modo distinguibile».

**Le famiglie secondarie non possono sostenere nessuna affermazione.** Sono dieci,
e riportare la migliore di dieci è il massimo-di-N che ha ucciso `cloud_exit`. Si
riportano come descrittivo, con la molteplicità dichiarata, e se una risultasse
interessante richiederebbe una pre-registrazione propria su dati nuovi.

## Il conteggio delle ipotesi

Questo test **non produce una curva di equity**, quindi non può entrare in
`hypotheses.CATALOGUE`, che contiene `Runner`, e non muove il Deflated Sharpe.
Non è un'esenzione: è la constatazione che il DSR misura la selezione fra
strategie, e qui non si sta selezionando una strategia.

Ma la regola 4 non fa sconti sull'origine, e guardare i dati resta guardare i
dati. Quindi si dichiara qui: **se il primario passa e da lì nasce un gate o un
segnale, quello entra nel catalogo come 27ª ipotesi e il DSR va ricalcolato
prima** di pubblicare qualunque numero — come è stato fatto per la 26ª.

## Previsione, registrata prima di guardare

* **`tenkan` e `kijun`: non batteranno il placebo.** Sono medie del prezzo
  recente: il prezzo è vicino per costruzione, e la «reazione» è in buona parte
  ritorno alla media di una finestra che contiene la barra stessa.
* **I sette ottavi di Gann: non batteranno il placebo.** Il progetto ha già
  misurato che 4/8 log, 5/8 log e il controllo 4/8 lineare danno **tutti e tre
  MAR 0.67**, identici a due decimali. Se il 5/8 avesse una proprietà sua non
  pareggerebbe con il 4/8 alla seconda cifra: quell'identità è già evidenza che
  il livello specifico non porta informazione.
* **Sulla nuvola sono genuinamente incerto**, ed è la prima volta in ventisei
  ipotesi. Non perché Ichimoku meriti fiducia, ma perché la nuvola è l'unico
  livello del set che **non deve la sua posizione a dove il prezzo è appena
  stato**: è stata fissata 26 barre prima, da dati che a quel punto erano già
  storia. Se un livello pre-impegnato non facesse niente, sarebbe una risposta
  netta; se facesse qualcosa, sarebbe la prima cosa nuova del progetto.

Se il primario passa, la prima cosa da controllare — e la dichiaro adesso perché
la regola 8 la impone su ogni pass — è la **concentrazione**: quanti asset,
quante epoche, e il risultato regge togliendo il primo contribuente?

## Verdetto

*(vuoto: da compilare nel commit successivo)*
