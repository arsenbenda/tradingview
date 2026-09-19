"""Validazione fuori campione: walk-forward, k-fold purgato, Deflated Sharpe.

Tutti i numeri prodotti dal progetto fino a ora vengono da un periodo unico, su
cui sono state provate N ipotesi ed è stata scelta la migliore. Quel
numero — il MAR del vincitore — non è una stima di quanto renderà il vincitore:
è il massimo di N variabili rumorose, e il massimo di N variabili rumorose è
alto anche quando nessuna delle N vale niente. Questo modulo
serve a misurare quanta parte del vantaggio sopravvive quando si toglie al
candidato il vantaggio di essere stato scelto guardando i dati su cui viene poi
misurato.

Tre strumenti, che rispondono a tre domande diverse:

**Walk-forward.** Il vantaggio regge in periodi che non sono stati usati per
sceglierlo? Attenzione a cosa si sta validando: con un solo set di parametri
fisso, far girare il candidato su finestre successive misura la *stabilità*, non
la selezione — non c'è niente che venga adattato in-sample. La selezione qui è
avvenuta a monte, sul catalogo: la variante è stata scelta perché era la migliore
delle N. Il walk-forward che mette alla prova *quella* decisione deve
quindi rieseguire la scelta dentro ogni finestra di training e misurare fuori
campione ciò che la scelta ha prodotto. Il modulo supporta entrambi i protocolli
perché rispondono a due domande legittime e diverse, ma solo il secondo è un
test della procedura che ha prodotto il candidato.

**K-fold purgato con embargo** (López de Prado). Il walk-forward usa solo il
passato per decidere, il che è realistico ma spreca dati: ogni finestra di test
è valutata su un training corto. Il k-fold usa tutto il resto della serie come
training, al prezzo di guardare anche in avanti — accettabile qui, dove serve a
stimare la dispersione, non a simulare un deployment. Due contaminazioni vanno
tolte: un trade aperto prima del fold di test può chiudersi dentro, quindi le
barre di training entro ``purge_days`` prima del test vanno eliminate; e i
rendimenti subito dopo il test sono correlati a quelli del test, quindi ne va
tolto un embargo. Senza queste due potature il risultato è contaminato e
sistematicamente troppo bello.

**Deflated Sharpe Ratio** (Bailey & López de Prado). Quanto Sharpe ci si aspetta
dal migliore di N strategie che non hanno alcun vantaggio? Quella soglia, ``sr0``,
cresce con N e con la dispersione degli Sharpe provati. Il DSR è la probabilità
che lo Sharpe vero del candidato superi quella soglia: se non è distinguibile da
zero, il candidato è indistinguibile dal miglior rumore di N tentativi.

Un avvertimento sul DSR, che va detto invece che nascosto: la formula assume
prove indipendenti. Le N ipotesi qui condividono base, dati e periodo, e sono
quindi fortemente correlate; il numero di prove *indipendenti* è minore di N.
Questo rende ``sr0`` più alto del dovuto e quindi il DSR
**conservativo** — un DSR alto resta un risultato affidabile, un DSR basso è
in parte imputabile alla correlazione fra le prove. La direzione dell'errore è
nota, ed è quella prudente.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict, field

import numpy as np
import pandas as pd

from . import backtest, metrics

CAPITAL = 100_000.0

#: barre di riscaldamento prima di ogni segmento valutato.
#:
#: Gli indicatori non possono partire dal primo giorno della finestra, o le
#: prime settimane di ogni finestra sarebbero prive di segnale e il confronto
#: fra finestre misurerebbe soprattutto il riscaldamento. Senkou B guarda 52
#: barre indietro e la nuvola è spostata di 26, quindi servono almeno 78 barre;
#: 400 giorni di calendario le coprono con margine su ogni calendario, crypto a
#: sette giorni compreso. Il riscaldamento serve solo a scaldare: il rendimento
#: viene misurato esclusivamente dentro la finestra.
WARMUP_DAYS = 400

#: quanto può durare al massimo un trade, in giorni di calendario.
#:
#: Misurato, non assunto: il trade più lungo osservato sulle varianti candidate
#: dura 198 giorni. È l'orizzonte di cui va purgato il training prima di un fold
#: di test, perché è la distanza massima entro cui un'osservazione di training
#: può avere il proprio esito dentro il test.
MAX_HOLDING_DAYS = 200

#: embargo dopo il fold di test, in giorni: l'1% circa della serie.
EMBARGO_DAYS = 40

EULER_GAMMA = 0.5772156649015329


# --------------------------------------------------------------------------
# normale standard, senza scipy
# --------------------------------------------------------------------------

def norm_cdf(x: float) -> float:
    """Funzione di ripartizione della normale standard."""
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def norm_ppf(p: float) -> float:
    """Inversa della normale standard (Acklam, con un raffinamento di Halley).

    Il raffinamento porta l'errore relativo sotto 1e-15: serve perché il DSR
    valuta la quantile a ``1 - 1/N``, cioè molto vicino a uno, dove le
    approssimazioni razionali grezze perdono cifre proprio dove contano.
    """
    if not 0.0 < p < 1.0:
        raise ValueError(f"p deve stare in (0,1), ricevuto {p}")

    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00)
    p_low, p_high = 0.02425, 1 - 0.02425

    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        x = (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
            ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    elif p <= p_high:
        q, r = p - 0.5, (p - 0.5) ** 2
        x = (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5])*q / \
            (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1)
    else:
        q = math.sqrt(-2 * math.log(1 - p))
        x = -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
            ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)

    err = norm_cdf(x) - p
    u = err * math.sqrt(2 * math.pi) * math.exp(x * x / 2)
    return x - u / (1 + x * u / 2)


# --------------------------------------------------------------------------
# Sharpe probabilistico e deflazionato
# --------------------------------------------------------------------------

def sharpe_per_bar(returns: pd.Series | np.ndarray) -> float:
    """Sharpe non annualizzato. Il DSR lavora per osservazione, non per anno."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    sd = r.std(ddof=1)
    return float(r.mean() / sd) if len(r) > 1 and sd > 0 else float("nan")


def probabilistic_sharpe_ratio(sr: float, n_obs: int, skew: float,
                               kurtosis: float, sr_star: float = 0.0) -> float:
    """Probabilità che lo Sharpe vero superi ``sr_star``.

    ``sr`` e ``sr_star`` per osservazione; ``kurtosis`` **non** in eccesso (3 per
    una normale). Asimmetria negativa e code grasse gonfiano l'errore standard
    dello Sharpe: è il motivo per cui una curva di equity a scalini con rari
    crolli profondi ha uno Sharpe molto meno affidabile di quanto il solo valore
    puntuale suggerisca.
    """
    if not np.isfinite(sr) or n_obs < 2:
        return float("nan")
    var = 1.0 - skew * sr + (kurtosis - 1.0) / 4.0 * sr * sr
    if var <= 0:
        return float("nan")
    return norm_cdf((sr - sr_star) * math.sqrt(n_obs - 1) / math.sqrt(var))


def expected_max_sharpe(n_trials: int, trials_std: float) -> float:
    """Sharpe atteso del migliore di ``n_trials`` strategie senza alcun vantaggio.

    È la soglia ``sr0`` del Deflated Sharpe: il massimo di N variabili normali a
    media nulla cresce come la deviazione standard delle prove per un fattore
    che dipende solo da N. Provare più cose alza l'asticella, e questa funzione
    dice di quanto.
    """
    if n_trials < 2 or not np.isfinite(trials_std) or trials_std <= 0:
        return 0.0
    return trials_std * ((1 - EULER_GAMMA) * norm_ppf(1 - 1.0 / n_trials)
                         + EULER_GAMMA * norm_ppf(1 - 1.0 / (n_trials * math.e)))


@dataclass
class DeflatedSharpe:
    sr: float             # per barra
    sr_annual: float
    sr0: float            # soglia sotto l'ipotesi nulla, per barra
    sr0_annual: float
    psr: float            # P(Sharpe vero > 0)
    dsr: float            # P(Sharpe vero > sr0)
    n_trials: int
    n_obs: int
    skew: float
    kurtosis: float
    trials_std: float

    def as_dict(self) -> dict:
        return asdict(self)


def deflated_sharpe(returns: pd.Series, trial_sharpes, *,
                    n_trials: int | None = None,
                    bars_per_year: float | None = None) -> DeflatedSharpe:
    """Deflated Sharpe Ratio del candidato.

    ``trial_sharpes`` sono gli Sharpe **per barra** di tutte le ipotesi provate,
    sulla stessa serie e sullo stesso periodo: la loro dispersione è ciò che
    determina quanto è facile ottenere per caso uno Sharpe alto in questo
    esperimento. ``n_trials`` può essere passato a parte quando il numero di
    ipotesi provate è maggiore del numero di Sharpe disponibili — ma il caso
    normale, e quello corretto, è che coincidano.
    """
    r = pd.Series(returns).dropna()
    trials = np.asarray([s for s in trial_sharpes if np.isfinite(s)], dtype=float)
    n = int(n_trials if n_trials is not None else len(trials))

    sr = sharpe_per_bar(r)
    skew = float(r.skew())
    kurt = float(r.kurtosis()) + 3.0          # pandas restituisce l'eccesso
    std = float(trials.std(ddof=1)) if len(trials) > 1 else float("nan")
    sr0 = expected_max_sharpe(n, std)
    ppy = bars_per_year if bars_per_year is not None else metrics.bars_per_year(r.index)
    scale = math.sqrt(ppy)

    return DeflatedSharpe(
        sr=sr, sr_annual=sr * scale, sr0=sr0, sr0_annual=sr0 * scale,
        psr=probabilistic_sharpe_ratio(sr, len(r), skew, kurt, 0.0),
        dsr=probabilistic_sharpe_ratio(sr, len(r), skew, kurt, sr0),
        n_trials=n, n_obs=len(r), skew=skew, kurtosis=kurt, trials_std=std,
    )


# --------------------------------------------------------------------------
# segmenti temporali
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Segment:
    start: pd.Timestamp
    end: pd.Timestamp

    @property
    def days(self) -> int:
        return int((self.end - self.start).days)

    @property
    def years(self) -> float:
        return self.days / 365.25

    def __str__(self) -> str:
        return f"{self.start.date()}→{self.end.date()}"


@dataclass(frozen=True)
class Window:
    """Una finestra di walk-forward: si decide sul training, si misura sul test."""

    train: Segment
    test: Segment

    @property
    def label(self) -> str:
        return f"{self.test.start.date()}→{self.test.end.date()}"


@dataclass(frozen=True)
class Fold:
    """Un fold di k-fold purgato: training a pezzi, test contiguo."""

    test: Segment
    train: tuple[Segment, ...]
    index: int = 0

    @property
    def label(self) -> str:
        return f"fold {self.index + 1} {self.test}"

    @property
    def train_years(self) -> float:
        return sum(s.years for s in self.train)


def rolling_windows(start, end, *, train_years: int = 3, test_years: int = 1,
                    step_years: int = 1, min_test_days: int = 300) -> list[Window]:
    """Finestre rolling: ``train_years`` di training, ``test_years`` di test.

    Le finestre di test sono contigue e non si sovrappongono, quindi i loro
    rendimenti possono essere concatenati senza contare due volte lo stesso
    giorno. L'ultima finestra viene scartata se il test è più corto di
    ``min_test_days``: un MAR calcolato su due mesi non è un dato, è rumore con
    un nome.
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    windows, train_start = [], start
    while True:
        train_end = train_start + pd.DateOffset(years=train_years)
        test_end = min(train_end + pd.DateOffset(years=test_years), end)
        if train_end >= end or (test_end - train_end).days < min_test_days:
            break
        windows.append(Window(Segment(train_start, train_end), Segment(train_end, test_end)))
        train_start = train_start + pd.DateOffset(years=step_years)
    return windows


def purged_folds(start, end, *, n_splits: int = 5,
                 purge_days: int = MAX_HOLDING_DAYS,
                 embargo_days: int = EMBARGO_DAYS) -> list[Fold]:
    """K-fold su blocchi temporali contigui, purgato e con embargo.

    Il training di ogni fold è tutto il resto della serie **meno** i
    ``purge_days`` che precedono il test — dove stanno le osservazioni il cui
    trade può finire dentro il test — **meno** l'embargo che lo segue, dove i
    rendimenti sono ancora correlati a quelli del test. I fold agli estremi
    hanno un solo segmento di training, gli altri due.
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if n_splits < 2:
        raise ValueError("servono almeno due fold")
    edges = pd.date_range(start, end, periods=n_splits + 1)

    folds = []
    for k in range(n_splits):
        test = Segment(edges[k], edges[k + 1])
        train: list[Segment] = []
        left_end = test.start - pd.Timedelta(days=purge_days)
        if (left_end - start).days > 0:
            train.append(Segment(start, left_end))
        right_start = test.end + pd.Timedelta(days=embargo_days)
        if (end - right_start).days > 0:
            train.append(Segment(right_start, end))
        folds.append(Fold(test=test, train=tuple(train), index=k))
    return folds


# --------------------------------------------------------------------------
# valutazione su segmenti
# --------------------------------------------------------------------------

@dataclass
class PeriodResult:
    """Esito di una strategia su un insieme di segmenti."""

    stats: metrics.Stats
    per_asset: dict[str, metrics.Stats] = field(default_factory=dict)
    returns: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))

    @property
    def mar(self) -> float:
        return self.stats.mar

    def assets_better_than(self, other: "PeriodResult") -> int:
        """Su quanti asset questa strategia ha un MAR migliore dell'altra."""
        return sum(1 for a, s in self.per_asset.items()
                   if a in other.per_asset and np.isfinite(s.mar)
                   and np.isfinite(other.per_asset[a].mar)
                   and s.mar > other.per_asset[a].mar)


def evaluate(universe: dict[str, pd.DataFrame], runner, segments,
             *, warmup_days: int = WARMUP_DAYS, cost_mult: float = 1.0,
             capital: float = CAPITAL) -> PeriodResult:
    """Esegue ``runner`` e misura **solo** dentro i segmenti indicati.

    Il backtest parte ``warmup_days`` prima dell'inizio di ogni segmento, così
    gli indicatori sono già caldi alla prima barra misurata e una posizione
    aperta prima dell'inizio resta aperta — che è quello che farebbe un sistema
    in funzione. Del risultato si tiene però solo la parte dentro il segmento:
    il riscaldamento non contribuisce né ai rendimenti né ai trade contati.

    Per i segmenti non contigui — il training di un fold purgato — gli anni
    trascorsi sono la **somma** delle durate dei segmenti, non la distanza fra
    la prima e l'ultima data, che includerebbe i buchi.
    """
    segments = list(segments)
    total_years = sum(s.years for s in segments)
    per_asset_returns: dict[str, pd.Series] = {}
    per_asset: dict[str, metrics.Stats] = {}
    all_trades: list[backtest.Trade] = []

    for asset, df in universe.items():
        chunks, trades = [], []
        for seg in segments:
            sub = df.loc[seg.start - pd.Timedelta(days=warmup_days):seg.end]
            if len(sub) < 2:
                continue
            res = runner(asset, sub, cost_mult)
            eq = res.equity.loc[seg.start:seg.end]
            if len(eq) < 2:
                continue
            chunks.append(eq.pct_change().iloc[1:])
            trades += [t for t in res.trades
                       if not t.is_open and seg.start <= t.entry_date <= seg.end]
        if not chunks:
            continue
        r = pd.concat(chunks).sort_index()
        per_asset_returns[asset] = r
        all_trades += trades
        eq = capital * (1 + r).cumprod()
        per_asset[asset] = metrics.compute(
            backtest.Result(equity=eq, trades=trades, exposure=float("nan")),
            capital, years=total_years)

    if not per_asset_returns:
        empty = pd.Series(dtype=float)
        return PeriodResult(metrics.compute(
            backtest.Result(equity=pd.Series([capital, capital],
                                             index=pd.to_datetime(["2000-01-01", "2000-01-02"])),
                            trades=[], exposure=float("nan")), capital, years=total_years),
            {}, empty)

    # stessa aggregazione di metrics.portfolio_equity, e non una copia: un
    # portafoglio calcolato in due modi diversi nel benchmark e nella
    # validazione renderebbe incomparabili i due numeri che servono a confronto
    pf_returns = metrics.equal_weight_returns(per_asset_returns)
    pf_equity = capital * (1 + pf_returns).cumprod()
    stats = metrics.compute(
        backtest.Result(equity=pf_equity, trades=all_trades, exposure=float("nan")),
        capital, years=total_years)
    return PeriodResult(stats, per_asset, pf_returns)


def select_best(universe: dict[str, pd.DataFrame], pool: dict, segments,
                *, key=lambda pr: pr.mar, **kwargs) -> tuple[str, dict[str, PeriodResult]]:
    """Sceglie dal ``pool`` la variante migliore sui segmenti dati.

    È la procedura di ricerca vera e propria, ridotta a funzione, in modo da
    poterla applicare dentro una finestra di training invece che su tutto il
    periodo. Il valore che restituisce va misurato altrove: applicarla e
    valutarla sugli stessi dati è esattamente l'errore che si vuole quantificare.
    """
    results = {name: evaluate(universe, runner, segments, **kwargs)
               for name, runner in pool.items()}
    valid = {n: r for n, r in results.items() if np.isfinite(key(r))}
    best = max(valid or results, key=lambda n: key((valid or results)[n]))
    return best, results


def differential_returns(strategy: pd.Series, benchmark: pd.Series) -> pd.Series:
    """Rendimento attivo: quanto la strategia fa *in più* del benchmark, giorno per giorno.

    Serve perché la domanda di questo progetto non è mai "il candidato ha uno
    Sharpe significativo" — ce l'hanno tutte le varianti del catalogo, e ce l'ha
    anche il benchmark che non è stato scelto da nessuno: undici anni di
    esposizione a un trend follower bastano a renderlo significativo. La domanda
    è se il *vantaggio* sul benchmark è reale. Applicare lo Sharpe deflazionato
    alla serie differenziale sposta il test su quella domanda, che è quella a cui
    la selezione fra le ipotesi del catalogo ha risposto guardando i dati.

    Non è il rendimento di un portafoglio realizzabile — comprare il candidato e
    vendere il benchmark richiederebbe il doppio del capitale e costi doppi — ma
    è la grandezza di cui si vuole sapere il segno.
    """
    frame = pd.concat({"s": strategy, "b": benchmark}, axis=1).sort_index().fillna(0.0)
    return frame["s"] - frame["b"]


def volatility_matched(strategy: pd.Series, benchmark: pd.Series) -> pd.Series:
    """``strategy`` riscalata alla volatilità di ``benchmark``.

    Serve prima di differenziare due strategie che non lavorano alla stessa
    scala. Il differenziale grezzo di una strategia che gira a tre volte la
    volatilità del benchmark ha una media positiva **per costruzione**, e uno
    Sharpe differenziale che misura la scala invece del vantaggio: è la stessa
    trappola del MAR che lusinga la leva, spostata di una formula.

    Il fattore è costante e stimato su tutto il periodo, quindi **non** è una
    serie realizzabile in tempo reale: è una normalizzazione dichiarata, per
    rendere confrontabile un differenziale, non una strategia.

    Per le varianti che girano allo stesso ``risk_pct`` del benchmark il fattore
    è vicino a 1 e non cambia nulla — che è il motivo per cui si può applicare a
    tutte senza trattarne una in modo speciale.
    """
    sd_s, sd_b = strategy.std(), benchmark.std()
    if not np.isfinite(sd_s) or sd_s <= 0 or not np.isfinite(sd_b):
        return strategy
    return strategy * (sd_b / sd_s)


def rank_correlation(a: dict[str, float], b: dict[str, float]) -> float:
    """Correlazione di rango di Spearman fra due classifiche sugli stessi nomi.

    È il test più diretto della procedura di selezione: se l'ordine delle
    le varianti dentro il training non predice il loro ordine fuori
    campione, scegliere la migliore in-sample non è meglio che scegliere a caso,
    e il vantaggio del vincitore è il vantaggio del fortunato.
    """
    nomi = [k for k in a if k in b and np.isfinite(a[k]) and np.isfinite(b[k])]
    if len(nomi) < 3:
        return float("nan")
    ra = pd.Series({k: a[k] for k in nomi}).rank()
    rb = pd.Series({k: b[k] for k in nomi}).rank()
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(ra.corr(rb))


# --------------------------------------------------------------------------
# bootstrap a blocchi circolari
# --------------------------------------------------------------------------

def _mar_from_returns(r: np.ndarray, bars_per_year: float) -> float:
    eq = np.cumprod(1.0 + r)
    total = eq[-1]
    years = len(r) / bars_per_year
    if total <= 0 or years <= 0:
        return float("nan")
    cagr = total ** (1.0 / years) - 1.0
    peak = np.maximum.accumulate(eq)
    dd = float(((peak - eq) / peak).max())
    return cagr / dd if dd > 0 else float("nan")


@dataclass
class BootstrapCI:
    mean: float
    lo: float
    hi: float
    p_negative: float
    n_boot: int
    block_bars: int

    def as_dict(self) -> dict:
        return asdict(self)


def block_bootstrap_delta(candidate: pd.Series, benchmark: pd.Series, *,
                          block_bars: int = 21, n_boot: int = 2000,
                          seed: int = 0, alpha: float = 0.05) -> BootstrapCI:
    """Intervallo di confidenza sul delta di MAR, bootstrap a blocchi circolari.

    I blocchi servono perché i rendimenti giornalieri di un trend follower non
    sono indipendenti: un drawdown è una sequenza, e ricampionare giorno per
    giorno la spezzerebbe, producendo intervalli assurdamente stretti. Il
    ricampionamento è **appaiato** — gli stessi blocchi di calendario per
    candidato e benchmark — perché la domanda è sul loro divario, non sui due
    livelli separatamente: le finestre in cui tutto il mercato va bene non
    devono contribuire alla varianza del delta.
    """
    frame = pd.concat({"cand": candidate, "base": benchmark}, axis=1).sort_index().fillna(0.0)
    a = frame["cand"].to_numpy(float)
    b = frame["base"].to_numpy(float)
    n = len(a)
    if n < block_bars * 2:
        raise ValueError("serie troppo corta per questa lunghezza di blocco")
    ppy = metrics.bars_per_year(frame.index)

    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block_bars))
    deltas = np.full(n_boot, np.nan)
    for k in range(n_boot):
        starts = rng.integers(0, n, size=n_blocks)
        idx = (starts[:, None] + np.arange(block_bars)[None, :]).ravel()[:n] % n
        deltas[k] = _mar_from_returns(a[idx], ppy) - _mar_from_returns(b[idx], ppy)

    good = deltas[np.isfinite(deltas)]
    return BootstrapCI(
        mean=float(good.mean()), lo=float(np.quantile(good, alpha / 2)),
        hi=float(np.quantile(good, 1 - alpha / 2)),
        p_negative=float((good <= 0).mean()), n_boot=len(good), block_bars=block_bars,
    )
