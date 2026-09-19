# Pre-registrazione — Donchian 55/20 su 49 futures, 1970-2024

**Scritta e committata il 2026-09-16, prima di eseguire un solo backtest su
questi dati.** È l'unica cosa che fa valere N = 1 invece di N = 26, e se venisse
scritta dopo non varrebbe niente. Chi legge può verificarlo dalla cronologia git:
questo file deve precedere `results/futures_50y.md`.

## Perché un campione nuovo

Il penalty del Deflated Sharpe conta quante ipotesi sono state provate **su un
dato campione**. Sui sei asset e undici anni di `data/raw/` ne sono state provate
venticinque, e la soglia è salita a 0.94 di Sharpe annuo: continuare lì rende più
difficile dimostrare qualcosa, non più facile (è l'esclusione «cercare la
ventiseiesima ipotesi»).

Su un campione mai toccato quel contatore riparte da uno — **a condizione che la
regola sia dichiarata prima**. Questo file è quella condizione.

## L'ipotesi, una sola

> Il breakout di Donchian 55/20, con i parametri Turtle pubblicati negli anni
> Ottanta e mai adattati a questi dati, ha un vantaggio distinguibile da zero su
> un universo ampio di futures su mezzo secolo di storia.

Nessuna variante, nessuna alternativa in riserva. Se fallisce, ha fallito.

## Universo — regola meccanica, lista congelata

Applicata a `robcarver17/pysystemtrade`, `data/futures/adjusted_prices_csv`,
commit scaricato il 2026-09-16:

1. storia ≥ **30 anni** (così il requisito statistico di ~11 anni è coperto con
   margine anche su sottoperiodi);
2. esclusi i `_mini`/`_micro` quando il contratto pieno è già nella lista — sono
   lo stesso mercato, e contarli due volte gonfierebbe la diversificazione;
3. nessuna esclusione discrezionale, né prima né dopo.

**49 mercati, mediana 41,5 anni, 536.724 giorni-mercato.** La lista sta in
`data/futures_universe.txt` ed è congelata: un mercato ne esce solo per un
difetto dei dati documentato, mai perché rende poco.

## Strategia e parametri — nessuno scelto qui

* ingresso: breakout a **55** barre · uscita: canale a **20** · stop **2×**
  volatilità · rischio **1%** per trade. Identici al benchmark del progetto,
  pubblicati prima di questo lavoro.
* **canali e volatilità sulle chiusure**, perché questi dati non hanno OHLC. È la
  venticinquesima ipotesi del catalogo (`canali_su_chiusure`), già misurata sui
  sei asset: differisce dal benchmark OHLC nel 13% dei giorni, quindi i numeri
  **non sono confrontabili con lo 0.87** e non verranno confrontati.
* serie intraday ricampionate a **daily** prendendo l'ultimo prezzo del giorno.
* long/short simmetrico, capitale equipesato, un solo set di parametri per tutti
  e 49 i mercati (regola 3).

## Costi — dichiarati adesso

`costs.DEFAULT` del progetto: 0.05% commissione + 0.10% slippage per lato.
Riportato anche a **costi doppi**, come già si fa in `benchmark_donchian.md`.
Nessuna taratura per mercato.

## Cosa conta come risultato, deciso prima

| | |
|---|---|
| metrica primaria | **MAR** di portafoglio, poi Sharpe |
| soglia | Sharpe annuo del portafoglio **distinguibile da zero al 95%**, cioè SR/SE > 1.96 |
| N per il Deflated Sharpe | **1** |
| si riporta comunque | su quanti mercati su 49 il MAR è positivo |

**Un solo run.** Se il risultato è deludente non si cambia un parametro, non si
toglie un mercato, non si prova il 20/10: si scrive che ha fallito. Qualunque
cosa venga provata dopo entra nel catalogo e alza la soglia, come sempre.

## Limiti dichiarati prima, non dopo

1. **Niente stop intragiornaliero.** Su dati close-only lo stop può essere
   valutato solo in chiusura: code più grasse sui gap di quanto un backtest OHLC
   mostrerebbe. Misurato sui sei asset: vale −0.25 di MAR.
2. **Una sola curatela.** I calendari di rollo e l'aggiustamento sono le scelte di
   una persona. Non c'è una seconda fonte con cui incrociarli, e la regola «una
   sola famiglia di fonti» qui è un vincolo subito, non scelto.
3. **Contaminazione da addestramento.** L'LLM che esegue questa analisi ha visto
   in addestramento l'esito dei mercati fino al 2026. Attenuante: la regola è del
   1983 e i parametri non vengono scelti qui. Resta un difetto, ed è dichiarato.
4. **I dati finiscono al 2024-03-28.** Storico, non operativo.
5. **Sopravvivenza dell'universo.** La lista è dei mercati che *oggi* Carver
   segue: mercati morti o delistati negli anni Settanta non ci sono. È un bias
   verso i mercati sopravvissuti e non è correggibile con questa fonte.
