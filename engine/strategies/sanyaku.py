"""Porting di `strategies/ichimoku_sanyaku_v55.pine`.

Fedele ai default del Pine. Le opzioni disattivate per default (Chikou stretto,
stop largo sul cloud reclaim, reclaim decisivo, cooldown adattivo, blocco per
sovraestensione, filtro sulla curva equity) sono implementate ma spente, così il
confronto misura la strategia come verrebbe deployata.

Due differenze dichiarate rispetto al Pine, entrambe correzioni di difetti
misurati e non scelte estetiche:

* la quantità è derivata dal prezzo di fill, non dal close della barra di
  segnale — il motore può riprodurre il comportamento Pine con
  ``size_at_signal=True``, così la differenza si misura;
* lo slippage è in percentuale per asset invece che in tick.

Il regime HTF replica l'idioma non-repainting del Pine
(``request.security(..., expr[1], lookahead=barmerge.lookahead_on)``): su ogni
barra giornaliera si usa l'ultima settimana **chiusa**.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import indicators as ind
from ..backtest import Intent, State, Strategy


def htf_weekly(df: pd.DataFrame, kijun_len: int = 26) -> pd.DataFrame:
    """Regime settimanale visto da una barra giornaliera, senza repainting.

    A ogni giorno viene associata l'ultima settimana **chiusa**: la settimana in
    corso non è ancora nota mentre la si sta vivendo. Sbagliare questo punto
    regala alla strategia informazione che non poteva avere.
    """
    weekly = df.resample("W").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()

    prev_close = weekly["close"].shift(1)
    prev_kijun = ind.donchian_mid(weekly, kijun_len).shift(1)
    prev_close.index = prev_close.index.to_period("W")
    prev_kijun.index = prev_kijun.index.to_period("W")

    labels = df.index.to_period("W")
    return pd.DataFrame(
        {"htf_close": labels.map(prev_close), "htf_kijun": labels.map(prev_kijun)},
        index=df.index,
    )


class SanyakuV55(Strategy):
    name = "sanyaku_v55"

    def __init__(
        self,
        *,
        tenkan_len: int = 9,
        kijun_len: int = 26,
        senkou_b_len: int = 52,
        disp: int = 26,
        atr_len: int = 14,
        min_cloud_thick: float = 0.75,
        min_atr_pct: float = 0.5,
        reclaim_bars: int = 10,
        cr_window: int = 60,
        cooldown_bars: int = 5,
        cooldown_loss_bars: int = 15,
        adaptive_cooldown: bool = False,
        zone_lock: bool = True,
        zone_range_atr: float = 2.0,
        zone_directional: bool = True,
        htf_gate: bool = True,
        strict_chikou: bool = False,
        e4_bypass_lock: bool = True,
        e4_bypass_cooldown: bool = True,
        use_overext: bool = False,
        overext_atr: float = 3.0,
        use_risk_mgmt: bool = True,
        use_loss_pause: bool = True,
        max_consec_loss: int = 5,
        pause_bars: int = 10,
        use_dd_breaker: bool = True,
        dd_threshold: float = 15.0,
        dd_risk_factor: float = 0.5,
        weak_risk_mult: float = 0.5,
        reclaim_risk_mult: float = 0.5,
        cr_risk_mult: float = 0.75,
        cr_delay_trail: bool = True,
        cr_trail_act_atr: float = 1.25,
        cr_wide_stop: bool = False,
        cr_stop_buf: float = 1.0,
        cr_decisive: bool = False,
        cr_buf: float = 0.25,
        min_stop_atr: float = 1.5,
        be_atr: float = 2.0,
        enabled_entries: tuple[int, ...] = (1, 2, 3, 4, 5),
    ) -> None:
        self.__dict__.update(locals())
        del self.self

    # ------------------------------------------------------------------
    def prepare(self, df: pd.DataFrame) -> None:
        ichi = ind.ichimoku(df, self.tenkan_len, self.kijun_len, self.senkou_b_len, self.disp)
        atr = ind.atr(df, self.atr_len)
        htf = htf_weekly(df, self.kijun_len)

        close, low, high, open_ = df["close"], df["low"], df["high"], df["open"]
        cloud_top, cloud_bot = ichi["cloud_top"], ichi["cloud_bot"]

        chikou = (close > high.rolling(self.disp).max().shift(1)) if self.strict_chikou else ichi["chikou_clear"]
        thick_ok = (ichi["span_a_now"] - ichi["span_b_now"]).abs() >= self.min_cloud_thick * atr
        atr_pct_ok = (atr / close * 100.0) >= self.min_atr_pct if self.min_atr_pct > 0 else pd.Series(True, index=df.index)

        trinity = (close > cloud_top) & ichi["tk_bull"] & chikou & thick_ok
        cr_level = cloud_top + self.cr_buf * atr if self.cr_decisive else cloud_top

        htf_regime = np.where(htf["htf_close"] > htf["htf_kijun"], 1,
                              np.where(htf["htf_close"] < htf["htf_kijun"], -1, 0))
        htf_regime = pd.Series(htf_regime, index=df.index)

        self.d = {
            "close": close.to_numpy(float), "open": open_.to_numpy(float),
            "low": low.to_numpy(float), "high": high.to_numpy(float),
            "atr": atr.to_numpy(float),
            "kijun": ichi["kijun"].to_numpy(float),
            "cloud_top": cloud_top.to_numpy(float), "cloud_bot": cloud_bot.to_numpy(float),
            # e1: sanyaku, primo bar in cui la trinità si forma
            "e1": (trinity & ~trinity.shift(1, fill_value=False)).to_numpy(bool),
            # e2: rimbalzo sul Kijun in trend
            "e2": ((close > cloud_top) & ichi["tk_bull"] & (low <= ichi["kijun"])
                   & (close > ichi["kijun"]) & (close > open_)).to_numpy(bool),
            # e3: TK cross precoce sotto la nuvola
            "e3": (ichi["tk_cross_up"] & (close < cloud_bot)).to_numpy(bool),
            # e4: riconquista della nuvola subito dopo un'uscita
            "e4_cross": (ind.crossover(close, cloud_top) & chikou).to_numpy(bool),
            # e5: cloud reclaim dopo un periodo sotto la nuvola
            "e5": ((ind.rolling_sum((close < cloud_bot).astype(float), self.cr_window) > 0)
                   & (close > cr_level) & (close.shift(1) <= cr_level.shift(1))
                   & chikou & thick_ok).to_numpy(bool),
            "htf_ok": ((htf_regime == 1) | ((htf_regime == -1) & (close > cloud_top))).to_numpy(bool)
            if self.htf_gate else np.ones(len(df), bool),
            "atr_pct_ok": atr_pct_ok.to_numpy(bool),
        }

        # stato della macchina, reinizializzato a ogni esecuzione
        self.zone_locked = False
        self.zone_anchor = np.nan
        self.pause_until = -10_000
        self.seen_trades = 0
        self.consec_losses = 0
        self.entry_type = 0
        self.entry_atr = np.nan
        self.trail_active = False

    # ------------------------------------------------------------------
    def entry(self, state: State) -> Intent | None:
        i, d = state.i, self.d
        if not np.isfinite(d["cloud_top"][i]) or not np.isfinite(d["atr"][i]):
            return None

        close, atr, cloud_top, cloud_bot = d["close"][i], d["atr"][i], d["cloud_top"][i], d["cloud_bot"][i]

        # rilascio direzionale della zona
        if self.zone_locked and self.zone_directional:
            upper = (self.zone_anchor if np.isfinite(self.zone_anchor) else close) + self.zone_range_atr * atr
            if close > upper or close < cloud_bot:
                self.zone_locked = False

        upper = (self.zone_anchor if np.isfinite(self.zone_anchor) else close) + self.zone_range_atr * atr
        in_locked_zone = self.zone_lock and self.zone_locked and (close <= upper if self.zone_directional else True)

        cooldown_len = self.cooldown_loss_bars if (self.adaptive_cooldown and state.last_trade_was_loss) else self.cooldown_bars
        in_cooldown = state.closed_trades > 0 and state.bars_since_exit < cooldown_len

        # Il Pine valuta questo blocco alla chiusura di un trade, non a ogni
        # barra, e azzera il contatore quando arma la pausa (righe 133-137 di
        # ichimoku_sanyaku_v55.pine). Senza quel reset la condizione resta vera
        # per sempre: ogni barra riarma pause_until, nessun trade si apre,
        # nessuna perdita si azzera, e la strategia si blocca definitivamente.
        if self.use_risk_mgmt and self.use_loss_pause and state.closed_trades != self.seen_trades:
            self.seen_trades = state.closed_trades
            self.consec_losses = self.consec_losses + 1 if state.last_trade_was_loss else 0
            if self.consec_losses >= self.max_consec_loss:
                self.pause_until = i + self.pause_bars
                self.consec_losses = 0
        paused = self.use_risk_mgmt and self.use_loss_pause and i <= self.pause_until

        if not d["atr_pct_ok"][i] or paused:
            return None
        if self.use_overext and close > d["kijun"][i] + self.overext_atr * atr:
            return None

        std_block = in_cooldown or in_locked_zone
        e4_block = ((not self.e4_bypass_cooldown) and in_cooldown) or ((not self.e4_bypass_lock) and in_locked_zone)

        within_reclaim = state.closed_trades > 0 and state.bars_since_exit <= self.reclaim_bars
        htf_ok = d["htf_ok"][i]

        # priorità del Pine: e1, e4, e5, e2, e3
        fired = 0
        if 1 in self.enabled_entries and d["e1"][i] and htf_ok and not std_block:
            fired = 1
        elif 4 in self.enabled_entries and within_reclaim and d["e4_cross"][i] and not e4_block:
            fired = 4
        elif 5 in self.enabled_entries and d["e5"][i] and not std_block:
            fired = 5
        elif 2 in self.enabled_entries and d["e2"][i] and htf_ok and not std_block:
            fired = 2
        elif 3 in self.enabled_entries and d["e3"][i] and not std_block:
            fired = 3
        if fired == 0:
            return None

        if fired == 5 and self.cr_wide_stop:
            stop_base = cloud_bot - self.cr_stop_buf * atr
        elif close > cloud_top:
            stop_base = cloud_bot
        else:
            stop_base = min(d["kijun"][i], d["low"][i])
        stop_dist = max(close - stop_base, self.min_stop_atr * atr)

        mult = {3: self.weak_risk_mult, 4: self.reclaim_risk_mult, 5: self.cr_risk_mult}.get(fired, 1.0)
        if self.use_risk_mgmt and self.use_dd_breaker and state.drawdown_pct > self.dd_threshold:
            mult *= self.dd_risk_factor

        self.entry_type = fired
        self.entry_atr = atr
        self.trail_active = not (fired == 3 or (fired == 5 and self.cr_delay_trail))
        self.zone_locked = True
        self.zone_anchor = cloud_top
        return Intent(direction=1, stop_distance=stop_dist, risk_mult=mult, tag=f"E{fired}")

    # ------------------------------------------------------------------
    def manage(self, state: State) -> tuple[bool, float | None]:
        i, d = state.i, self.d
        open_profit = d["close"][i] - state.entry_price
        new_stop = None

        if np.isfinite(self.entry_atr) and open_profit >= self.be_atr * self.entry_atr:
            new_stop = state.entry_price  # breakeven

        if not self.trail_active:
            if self.entry_type == 3 and d["close"][i] > d["cloud_top"][i]:
                self.trail_active = True
            elif self.entry_type == 5 and self.cr_delay_trail and np.isfinite(self.entry_atr) \
                    and open_profit >= self.cr_trail_act_atr * self.entry_atr:
                self.trail_active = True

        if self.trail_active and np.isfinite(d["cloud_bot"][i]):
            new_stop = d["cloud_bot"][i] if new_stop is None else max(new_stop, d["cloud_bot"][i])

        return False, new_stop  # nessuna uscita a segnale: solo stop, BE e trail
