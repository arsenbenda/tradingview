# Seconda pre-registrazione — Donchian 55/20 su 53 futures, 15-30 anni

**Scritta e committata il 2026-09-16, prima di preparare i dati e prima di
eseguire.** La cronologia git deve mostrare questo commit prima di
`results/futures_50y_2.md`.

Il primo tentativo (`results/preregistrazione_futures.md` →
`results/futures_50y.md`) è fallito, e **non per il mercato: per un parametro
scelto male da me.** Avevo dichiarato `costs.DEFAULT`, 0.30% di round-trip,
tarato su crypto ed ETF e dieci-trenta volte il costo vero di un future. Il test
ha misurato la mia assunzione. Questo documento esiste per non ripetere quello
sbaglio, e la differenza sta quasi tutta nella sezione sui costi.

## L'ipotesi, la stessa di prima

> Il breakout di Donchian 55/20, con i parametri Turtle pubblicati negli anni
> Ottanta e mai adattati a questi dati, ha un vantaggio distinguibile da zero su
> un universo ampio di futures.

Identica. Nessuna variante, nessuna riserva. Cambia il campione e cambia il
modello di costo; la regola no.

## Universo — disgiunto dal primo, lista congelata

1. storia fra **15 e 30 anni** (il requisito statistico è ~11 anni, coperto con
   margine);
2. **mai apparsi nel primo test**, né come contratto pieno né come variante di
   uno che c'era;
3. esclusi i `_mini`/`_micro` quando il contratto pieno è nella lista;
4. si applicherà lo stesso filtro sui difetti dei dati del primo test (prezzi ≤ 0
   o salti oltre il 50%, che sull'aggiustamento per differenza indicano un
   attraversamento dello zero o un rollo sporco).

**53 mercati, mediana 21 anni, 285.327 giorni-mercato.** Lista congelata in
`data/futures_universe_2.txt`.

Cosa ho già visto di questi mercati: **nomi, date di inizio e fine, numero di
barre.** Nient'altro. Nessun prezzo, nessun rendimento, nessun risultato.

## Il modello di costo — la parte che è andata storta la prima volta

**Round-trip = una frazione della volatilità giornaliera dello strumento**, non
una percentuale fissa del prezzo. Tre ragioni: è adimensionale e non richiede le
tabelle di tick value che non ho; lo slippage in pratica scala con la volatilità;
e non dipende dal livello del prezzo, che su una serie back-adjusted è distorto
andando indietro.

Calibrato **sui 30 mercati già bruciati**, non su questi — è una convenzione, non
una selezione:

| costo dichiarato | round-trip mediano | contro il costo reale (0.01-0.03%) |
|---|---|---|
| 5% di una sigma giornaliera | 0.046% | 1,5-4× |
| 10% di una sigma | 0.092% | 3-9× |
| **20% di una sigma** | **0.184%** | **6-18×** |

**Il verdetto si dà al 20%**, cioè al livello più severo dei tre: da sei a
diciotto volte il costo reale di un future liquido. Gli altri due si riportano
come sensibilità.

### Perché la soglia sta al livello più severo, e non al più realistico

Perché **ho già visto la curva di sensibilità sul campione bruciato** e so
grosso modo quali livelli di costo lo lasciavano passare. Quella conoscenza non
può essere cancellata, quindi viene neutralizzata: la soglia è fissata **sopra**
il punto che so essere comodo, dove dai numeri del primo test il risultato è
marginale. Se passa lì, passa **nonostante** un handicap di un ordine di
grandezza, e la contaminazione ha lavorato contro l'ipotesi invece che a favore.

Dichiararla è più onesto che fingere che non ci sia.

## Strategia e parametri — nessuno scelto qui

Identici al primo test e al benchmark del progetto: ingresso **55**, uscita
**20**, stop **2×** volatilità, rischio **1%** per trade, long/short simmetrico,
capitale equipesato, un solo set per tutti i mercati. Canali e volatilità sulle
chiusure, perché questi dati non hanno OHLC.

## Cosa conta come risultato, deciso adesso

| | |
|---|---|
| metrica primaria | **MAR** di portafoglio, poi Sharpe |
| **soglia** | **Sharpe del portafoglio distinguibile da zero al 95% (SR/SE > 1.96), al costo del 20% di sigma** |
| N per il Deflated Sharpe | **1** |
| si riporta comunque | mercati con MAR positivo su 53, e la sensibilità a 5% e 10% |

**Un solo run.** Se fallisce non si cambia il costo, non si toglie un mercato,
non si prova il 20/10. Si scrive che ha fallito, e il campione è bruciato come
il primo.

## Revisione della specifica — il passo che mancava

Il primo fallimento non è stato un errore di ragionamento ma di procedura:
nessuno ha guardato la specifica prima di eseguirla. Prima di questo run ogni
parametro dichiarato è stato ricondotto a una fonte:

| parametro | valore | da dove viene |
|---|---|---|
| ingresso / uscita | 55 / 20 | Turtle System 2, pubblicato negli anni Ottanta |
| stop | 2× volatilità | idem |
| rischio per trade | 1% | convenzione del progetto, invariata dall'inizio |
| **costo** | **20% di una sigma giornaliera** | **calibrato sul campione bruciato, dichiarato conservativo, verificato contro il round-trip reale di un future liquido** |
| universo | regola meccanica, 15-30 anni | questo documento |
| soglia | SR/SE > 1.96 | convenzione statistica, scelta prima |

La riga in grassetto è quella che la prima volta non era stata ricondotta a
niente. **Un parametro senza una provenienza scritta è un parametro da
verificare, non da usare.**

## Limiti dichiarati prima

1. **Niente stop intragiornaliero** su dati close-only: code più grasse sui gap.
   Misurato altrove: −0.25 di MAR.
2. **Una sola curatela** — i calendari di rollo sono le scelte di Carver.
3. **Contaminazione da addestramento**: l'LLM che esegue ha visto questi mercati
   fino al 2026. La regola però è del 1983 e i parametri non si scelgono qui.
4. **Contaminazione dal primo test**: la convenzione di costo è stata calibrata
   conoscendo la curva di sensibilità. Neutralizzata fissando la soglia al livello
   più severo, come sopra.
5. **Dati al 2024-03-28**, e **bias di sopravvivenza**: sono i mercati che Carver
   segue oggi.
6. **Storie più corte del primo test** (mediana 21 anni contro 41): meno potenza
   statistica per mercato, compensata in parte dai 53 mercati invece di 30.
