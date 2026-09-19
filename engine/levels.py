"""I livelli come oggetti misurabili, non come condizioni dentro una strategia.

Il progetto ha sempre usato Ichimoku e Gann come gate booleani su una barra. Qui
si misura la cosa che quei gate presuppongono senza mai verificarla: **il prezzo
reagisce a questi livelli più di quanto reagirebbe a un livello qualunque messo
alla stessa distanza?**

Ipotesi pre-registrata in `results/prereg_livelli_sr.md`. Primario dichiarato: la
nuvola, perché è il solo livello **fissato 26 barre prima** che il prezzo ci
arrivi (`indicators.ichimoku` restituisce `cloud_top` già spostata) e il solo raro
e lontano. Tenkan, Kijun e gli ottavi di Gann sono secondari esplorativi.

Tre pezzi, e il terzo è quello che conta:

* **tocco**: ``low <= L <= high``, con una pausa minima fra eventi perché un
  prezzo che staziona su un livello non sono dieci prove indipendenti;
* **reazione**: una corsa fra due barriere a 1 ATR — si allontana o attraversa,
  quale viene prima. Nessun orizzonte arbitrario, nessuna soglia sul rendimento;
* **placebo**: lo stesso livello spostato di 0.5-1.5 ATR. È appaiato per
  costruzione su distanza percorsa, volatilità, asset, epoca e direzione, e
  l'unica cosa che cambia è *la posizione esatta*. Senza di lui si misurerebbe
  che il prezzo ha viaggiato, non che il livello esiste.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import indicators as ind

ATR_LEN = 14
PIVOT_K = 20        # barre di conferma per lato; il pivot su t e' noto da t+k
MIN_GAP = 5         # barre senza tocchi che separano due eventi
BARRIER_ATR = 1.0   # distanza delle due barriere della corsa
HORIZON = 20        # barre oltre le quali l'evento e' censurato
N_PLACEBO = 5
SHIFT_MIN, SHIFT_MAX = 0.5, 1.5

REJECT, BREAK, CENSORED = 1, -1, 0


# --------------------------------------------------------------------------
# i livelli
# --------------------------------------------------------------------------

def fractal_pivots(df: pd.DataFrame, k: int = PIVOT_K) -> tuple[np.ndarray, np.ndarray]:
    """Indici dei massimi e minimi frattali confermati da ``k`` barre per lato.

    Il pivot sulla barra ``i`` **non è noto prima di** ``i + k``: chi lo usa deve
    tenerne conto, ed è quello che fa :func:`recent_range`.
    """
    h, l = df["high"].to_numpy(float), df["low"].to_numpy(float)
    n = len(h)
    top = [i for i in range(k, n - k) if h[i] == h[i - k:i + k + 1].max()]
    bot = [i for i in range(k, n - k) if l[i] == l[i - k:i + k + 1].min()]
    return np.asarray(top, int), np.asarray(bot, int)


def recent_range(df: pd.DataFrame, k: int = PIVOT_K) -> tuple[pd.Series, pd.Series]:
    """A ogni barra: l'ultimo massimo e l'ultimo minimo di pivot **già noti**.

    Non una coppia arbitraria di estremi storici — la più recente, che è l'unica
    che un operatore userebbe e l'unica che non introduce un grado di libertà.
    """
    top, bot = fractal_pivots(df, k)
    h, l = df["high"].to_numpy(float), df["low"].to_numpy(float)
    n = len(df)
    hi = np.full(n, np.nan)
    lo = np.full(n, np.nan)

    for idx, src, out in ((top, h, hi), (bot, l, lo)):
        ultimo = np.nan
        j = 0
        for t in range(n):
            while j < len(idx) and idx[j] + k <= t:   # noto solo da pivot+k
                ultimo = src[idx[j]]
                j += 1
            out[t] = ultimo

    return pd.Series(hi, index=df.index), pd.Series(lo, index=df.index)


def level_families(df: pd.DataFrame, k: int = PIVOT_K) -> dict[str, pd.Series]:
    """Tutti i livelli in esame, allineati alla barra e utilizzabili su di essa."""
    ichi = ind.ichimoku(df)
    out = {
        "cloud_top": ichi["cloud_top"],
        "cloud_bot": ichi["cloud_bot"],
        "tenkan": ichi["tenkan"],
        "kijun": ichi["kijun"],
    }

    hi, lo = recent_range(df, k)
    # ottavi in log-price: un ottavo in logaritmo significa la stessa cosa a
    # qualunque prezzo, in lineare no
    lhi, llo = np.log(hi), np.log(lo)
    for n in range(1, 8):
        out[f"gann_{n}_8"] = np.exp(llo + (lhi - llo) * n / 8.0)

    return out


# --------------------------------------------------------------------------
# tocchi e reazione
# --------------------------------------------------------------------------

def touch_events(df: pd.DataFrame, level: pd.Series, *,
                 min_gap: int = MIN_GAP) -> tuple[np.ndarray, np.ndarray]:
    """Indici degli eventi di tocco e direzione di avvicinamento.

    Direzione ``+1``: il prezzo veniva da sotto, il livello è messo alla prova
    come **resistenza**. ``-1``: veniva da sopra, prova di **supporto**.

    Un prezzo che staziona su un livello per dieci barre è un episodio, non dieci
    prove: fra due eventi devono passare ``min_gap`` barre senza tocchi.
    """
    lv = level.to_numpy(float)
    low, high = df["low"].to_numpy(float), df["high"].to_numpy(float)
    close = df["close"].to_numpy(float)

    tocca = (low <= lv) & (lv <= high) & np.isfinite(lv)
    idx, direz, ultimo = [], [], -10**9
    for t in np.flatnonzero(tocca):
        if t == 0 or not np.isfinite(close[t - 1]):
            continue
        if t - ultimo <= min_gap:
            ultimo = t
            continue
        d = 1 if close[t - 1] < lv[t] else -1
        idx.append(t); direz.append(d)
        ultimo = t

    return np.asarray(idx, int), np.asarray(direz, int)


def race(df: pd.DataFrame, level: pd.Series, events: np.ndarray, direz: np.ndarray,
         atr: pd.Series, *, barrier_atr: float = BARRIER_ATR,
         horizon: int = HORIZON) -> np.ndarray:
    """Corsa fra due barriere: rifiuto, rottura, o censura.

    Dal tocco in avanti (**dalla barra successiva**, così la barra del tocco non
    decide da sola l'esito), quale delle due arriva prima:

    * allontanarsi di ``barrier_atr`` dal lato da cui si veniva → ``REJECT``;
    * attraversare di ``barrier_atr`` → ``BREAK``;
    * nessuna delle due entro ``horizon`` barre → ``CENSORED``.

    Se entrambe cadono nella stessa barra l'esito è indeterminato e si censura:
    è la scelta conservativa, e il conteggio viene riportato.
    """
    lv = level.to_numpy(float)
    low, high = df["low"].to_numpy(float), df["high"].to_numpy(float)
    a = atr.to_numpy(float)
    n = len(df)
    out = np.full(len(events), CENSORED, int)

    for e, (t, d) in enumerate(zip(events, direz)):
        L, dist = lv[t], barrier_atr * a[t]
        if not np.isfinite(L) or not np.isfinite(dist) or dist <= 0:
            continue
        sopra, sotto = L + dist, L - dist
        fine = min(t + 1 + horizon, n)
        seg = slice(t + 1, fine)
        if fine <= t + 1:
            continue

        su = high[seg] >= sopra
        giu = low[seg] <= sotto
        # resistenza (d=+1): rifiuto = scende sotto; rottura = sale sopra
        rifiuto, rottura = (giu, su) if d > 0 else (su, giu)

        i_rif = int(np.argmax(rifiuto)) if rifiuto.any() else 10**9
        i_rot = int(np.argmax(rottura)) if rottura.any() else 10**9
        if i_rif == i_rot:            # stessa barra o nessuna delle due
            continue
        out[e] = REJECT if i_rif < i_rot else BREAK

    return out


@dataclass
class Reaction:
    """Esito aggregato su una serie di livelli."""
    eventi: int
    rifiuti: int
    rotture: int
    censurati: int

    @property
    def decisi(self) -> int:
        return self.rifiuti + self.rotture

    @property
    def p_rifiuto(self) -> float:
        return self.rifiuti / self.decisi if self.decisi else float("nan")

    def as_dict(self) -> dict:
        return {"eventi": self.eventi, "rifiuti": self.rifiuti, "rotture": self.rotture,
                "censurati": self.censurati, "decisi": self.decisi,
                "p_rifiuto": self.p_rifiuto}


def measure(df: pd.DataFrame, level: pd.Series, atr: pd.Series,
            **kw) -> tuple[Reaction, np.ndarray]:
    """Reazione su un livello, più gli esiti per evento (servono al bootstrap)."""
    ev, d = touch_events(df, level, min_gap=kw.pop("min_gap", MIN_GAP))
    if len(ev) == 0:
        return Reaction(0, 0, 0, 0), np.empty(0, int)
    esiti = race(df, level, ev, d, atr, **kw)
    return Reaction(
        eventi=len(ev),
        rifiuti=int((esiti == REJECT).sum()),
        rotture=int((esiti == BREAK).sum()),
        censurati=int((esiti == CENSORED).sum()),
    ), esiti


def placebo_levels(level: pd.Series, atr: pd.Series, *, n: int = N_PLACEBO,
                   seed: int = 0) -> list[pd.Series]:
    """Lo stesso livello spostato di ``s · u · ATR``, ``u ~ U(0.5, 1.5)``.

    Lo scostamento è **costante lungo la serie** per ciascuna replica, non
    ridisegnato a ogni barra: un livello che sobbalza ogni giorno non è un
    livello, e il confronto perderebbe senso. La pre-registrazione non fissava
    questo dettaglio, quindi va dichiarato qui.

    Il minimo di 0.5 ATR evita che il placebo sia lo stesso livello con un'altra
    etichetta; il massimo di 1.5 che le condizioni di mercato non siano più
    confrontabili.
    """
    rng = np.random.default_rng(seed)
    fuori = []
    for _ in range(n):
        s = rng.choice((-1.0, 1.0))
        u = rng.uniform(SHIFT_MIN, SHIFT_MAX)
        fuori.append(level + s * u * atr)
    return fuori


def bootstrap_delta(esiti_reali: np.ndarray, esiti_placebo: np.ndarray, *,
                    n_boot: int = 2000, seed: int = 0) -> dict:
    """IC al 95% su ``P(rifiuto|reale) − P(rifiuto|placebo)``.

    I due insiemi di eventi cadono su barre diverse — un livello spostato viene
    toccato altrove — quindi non sono appaiati e si ricampionano separatamente.
    """
    def decisi(x):
        return x[x != CENSORED]

    a, b = decisi(esiti_reali), decisi(esiti_placebo)
    if len(a) == 0 or len(b) == 0:
        return {"delta": float("nan"), "lo": float("nan"), "hi": float("nan"),
                "p_negative": float("nan"), "n_boot": 0}

    rng = np.random.default_rng(seed)
    p = lambda x: float((x == REJECT).mean())
    d = np.empty(n_boot)
    for k in range(n_boot):
        d[k] = (p(rng.choice(a, len(a), replace=True))
                - p(rng.choice(b, len(b), replace=True)))
    return {"delta": p(a) - p(b), "lo": float(np.quantile(d, 0.025)),
            "hi": float(np.quantile(d, 0.975)),
            "p_negative": float((d <= 0).mean()), "n_boot": n_boot}
