"""Porting di `strategies/ichimoku_confluence_conservative.pine` (v3.2).

Include macchina a stati Sanyaku, swing A-B-C con target V/N/E, livelli di
struttura e convergenza, finestre temporali kihon/taito/kumo-twist, score a 7
punti con penalità, soglie e rischio asimmetrici per direzione, gate SMA sugli
short, stop sulla nuvola con cap ATR, filtro R:R, breakeven, trail sul Kijun e
uscite scalate 20%/30%.

**Deviazioni dichiarate** — tutte annotate perché un porting che nasconde le
proprie approssimazioni non è verificabile:

1. *Timeframe inferiore assente.* Il Pine deriva un LTF a 6 ore da un grafico
   daily e lo usa in `ltfConfirms`, che entra nello score. Con dati daily quel
   timeframe non esiste, quindi `ltfConfirms` è sempre falso e la componente di
   score si riduce a `nearTimeWindow`. Il timing LTF di ingresso e uscita è
   disattivato per default nel Pine, quindi lì non cambia nulla.
2. *Regime HTF sull'ultimo blocco chiuso.* Il Pine usa `lookahead_off`, che
   espone il blocco a 5 giorni **in formazione**. Qui si usa l'ultimo blocco
   completo: più conservativo, mai anticipatorio, al prezzo di una reattività
   inferiore fino a quattro barre.
3. *`syminfo.mintick` non esiste fuori da TradingView.* I test di "Kijun piatto"
   e "Senkou B piatto" usano una soglia relativa (0.01% del prezzo) al posto di
   due tick.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import indicators as ind
from ..backtest import Intent, State, Strategy

KIHON = (9, 17, 26, 33, 42, 51, 65, 76, 129, 172, 200, 257)


def pivots(series: pd.Series, left: int, right: int, high: bool) -> np.ndarray:
    """``ta.pivothigh`` / ``ta.pivotlow``.

    Il pivot su ``i - right`` viene **confermato** alla barra ``i``: è lì che
    diventa utilizzabile, e assegnarlo prima introdurrebbe lookahead.
    """
    v = series.to_numpy(float)
    n = len(v)
    out = np.full(n, np.nan)
    for i in range(left + right, n):
        c = i - right
        window = np.concatenate([v[c - left:c], v[c + 1:i + 1]])
        if window.size == 0:
            continue
        if (v[c] > window.max()) if high else (v[c] < window.min()):
            out[i] = v[c]
    return out


def htf_blocks(df: pd.DataFrame, size: int = 5) -> pd.DataFrame:
    """Barre di timeframe superiore come blocchi di ``size`` barre.

    Su un grafico daily il Pine chiede "5D". Ogni barra giornaliera vede
    l'ultimo blocco **completo**: la barra HTF in corso non è ancora nota.
    """
    group = np.arange(len(df)) // size
    agg = df.groupby(group).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    ichi = ind.ichimoku(agg)
    atr = ind.atr(agg, 14)
    thick = (ichi["span_a_now"] - ichi["span_b_now"]).abs() / atr.replace(0, np.nan)
    regime = np.where(agg["close"] > ichi["cloud_top"], 1,
                      np.where(agg["close"] < ichi["cloud_bot"], -1, 0))
    slope = np.sign(ichi["kijun"].diff()).fillna(0)
    in_bull = agg["close"] > ind.sma(agg["close"], 200)

    block = pd.DataFrame(
        {"regime": regime, "thick": thick.to_numpy(), "slope": slope.to_numpy(),
         "in_bull_sma": in_bull.to_numpy()},
        index=agg.index,
    ).shift(1)  # solo blocchi chiusi

    return block.reindex(group).set_index(df.index)


class ConfluenceV32(Strategy):
    name = "confluence_v32"

    def __init__(
        self, *,
        tenkan_len: int = 9, kijun_len: int = 26, senkou_b_len: int = 52, disp: int = 26,
        sanyaku_validity: int = 26, use_three_line: bool = True,
        swing_detect_len: int = 6, conv_tol_atr: float = 1.5,
        use_taito: bool = True, use_twist: bool = True, win_half: int = 2,
        tier_hi_min: int = 4, tier_mod_min: int = 2,
        tier_hi_min_short: int = 5, tier_mod_min_short: int = 4,
        risk_hi: float = 2.0, risk_mod: float = 1.2,
        risk_hi_short: float = 1.0, risk_mod_short: float = 0.6,
        trade_moderate: bool = True, reveal_counter: bool = False,
        min_rr: float = 1.2, cap_stop_atr: bool = True, max_stop_atr: float = 2.0,
        fallback_tp_atr: float = 3.0,
        use_sma_bull_gate: bool = True, sma_bull_len: int = 200,
        use_htf_strength: bool = True, htf_thick_min: float = 1.0,
        use_adx_score: bool = True, use_adx_gate: bool = False,
        adx_len: int = 14, adx_min: float = 15.0,
        split_stage1: float = 0.20, split_stage2: float = 0.30,
        use_be_stop: bool = True, be_r_mult: float = 1.5,
        trail_kijun: bool = True, con_trail_kijun: bool = True,
        enable_cont_short: bool = False, cont_cooldown: int = 12,
        htf_block: int = 5,
    ) -> None:
        self.__dict__.update(locals())
        del self.self

    # ------------------------------------------------------------------
    def prepare(self, df: pd.DataFrame) -> None:
        n = len(df)
        ichi = ind.ichimoku(df, self.tenkan_len, self.kijun_len, self.senkou_b_len, self.disp)
        atr = ind.atr(df, 14)
        adx = ind.dmi(df, self.adx_len, self.adx_len)["adx"]
        htf = htf_blocks(df, self.htf_block)

        close, open_, high, low = (df[c] for c in ("close", "open", "high", "low"))
        tenkan, kijun = ichi["tenkan"], ichi["kijun"]
        cloud_top, cloud_bot = ichi["cloud_top"], ichi["cloud_bot"]
        price_above, price_below = ichi["price_above"], ichi["price_below"]
        chikou_above = ichi["chikou_clear"]
        chikou_below = close < low.shift(self.disp)

        three_up = (close > tenkan) & (close > kijun) & (close > cloud_top)
        three_dn = (close < tenkan) & (close < kijun) & (close < cloud_bot)
        break_up = three_up if self.use_three_line else price_above
        break_dn = three_dn if self.use_three_line else price_below

        tk_up, tk_dn = ichi["tk_cross_up"], ichi["tk_cross_down"]
        fwd_twist = (ichi["senkou_a"] > ichi["senkou_b"]) != (
            ichi["senkou_a"].shift(1) > ichi["senkou_b"].shift(1))

        # --- swing A-B-C tramite pivot confermati
        ph = pivots(high, self.swing_detect_len, self.swing_detect_len, True)
        pl = pivots(low, self.swing_detect_len, self.swing_detect_len, False)

        # --- macchina a stati Sanyaku + swing + finestre temporali (sequenziale)
        arr = lambda: np.zeros(n)
        setup_type, tightness = np.zeros(n, int), np.full(n, np.nan)
        tgt_v, tgt_n, tgt_e = arr() * np.nan, arr() * np.nan, arr() * np.nan
        near_window = np.zeros(n, bool)

        s_state, s_bull, s_anchor = 0, True, -1
        p0 = p1 = p2 = np.nan
        t0 = t1 = t2 = False
        b0 = b1 = b2 = -1
        setup_origin = -1
        twist_centers: list[int] = []

        for i in range(n):
            # pivot: aggiorna la finestra a tre punti
            for val, is_high in ((ph[i], True), (pl[i], False)):
                if np.isfinite(val):
                    p0, p1, p2 = p1, p2, val
                    t0, t1, t2 = t1, t2, is_high
                    b0, b1, b2 = b1, b2, i - self.swing_detect_len

            abc_valid = np.isfinite(p0) and np.isfinite(p1) and np.isfinite(p2) and (t0 != t1) and (t1 != t2)
            is_bull = abc_valid and not t2
            if abc_valid:
                sign = 1 if is_bull else -1
                tgt_v[i] = p1 + sign * (p1 - p2)
                tgt_n[i] = p2 + sign * (p1 - p0)
                tgt_e[i] = p1 + sign * (p1 - p0)

            # macchina a stati
            if s_state == 0:
                if tk_up.iloc[i] and price_below.iloc[i]:
                    s_state, s_bull, s_anchor = 1, True, i
                elif tk_dn.iloc[i] and price_above.iloc[i]:
                    s_state, s_bull, s_anchor = 1, False, i
            elif s_state == 1:
                broke = (tenkan.iloc[i] <= kijun.iloc[i]) if s_bull else (tenkan.iloc[i] >= kijun.iloc[i])
                if (i - s_anchor) > self.sanyaku_validity or broke:
                    s_state, s_anchor = 0, -1
                elif s_bull and chikou_above.iloc[i] and price_below.iloc[i]:
                    s_state = 2
                elif (not s_bull) and chikou_below.iloc[i] and price_above.iloc[i]:
                    s_state = 2
            elif s_state == 2:
                broke = (tenkan.iloc[i] <= kijun.iloc[i]) if s_bull else (tenkan.iloc[i] >= kijun.iloc[i])
                ch_broke = (not chikou_above.iloc[i]) if s_bull else (not chikou_below.iloc[i])
                if (i - s_anchor) > self.sanyaku_validity or broke or ch_broke:
                    s_state, s_anchor = 0, -1

            kouten = s_state == 2 and s_bull and bool(break_up.iloc[i])
            gyaku = s_state == 2 and (not s_bull) and bool(break_dn.iloc[i])
            if kouten or gyaku:
                tightness[i] = i - s_anchor
                setup_origin = s_anchor
                s_state, s_anchor = 0, -1
            elif tk_up.iloc[i] or tk_dn.iloc[i]:
                setup_origin = i
            elif setup_origin >= 0 and (i - setup_origin) > self.sanyaku_validity * 2:
                setup_origin = -1

            tk_up_qual = bool(tk_up.iloc[i]) and price_above.iloc[i] and bool(chikou_above.iloc[i])
            tk_dn_qual = bool(tk_dn.iloc[i]) and price_below.iloc[i] and bool(chikou_below.iloc[i])
            setup_type[i] = 1 if kouten else 2 if gyaku else 3 if tk_up_qual else 4 if tk_dn_qual else 0

            # finestre temporali: kihon proiettate dall'origine, taito, kumo twist
            origin = setup_origin if setup_origin >= 0 else b2
            hit = False
            if origin >= 0:
                hit = any(abs(i - (origin + k)) <= self.win_half for k in KIHON)
            if self.use_taito and not hit and b2 >= 0 and b1 >= 0 and b0 >= 0:
                hit = abs(i - (b2 + abs(b1 - b0))) <= self.win_half
            if self.use_twist:
                if bool(fwd_twist.iloc[i]):
                    twist_centers.append(i + self.disp)
                if not hit:
                    hit = any(abs(i - c) <= self.win_half for c in twist_centers[-8:])
            near_window[i] = hit

        # --- livelli di struttura e convergenza dei target
        flat_tol = close * 0.0001          # mintick non esiste fuori da TradingView
        flat_kijun = (kijun - kijun.shift(1)).abs() < flat_tol
        flat_ssb = (ichi["senkou_b"] - ichi["senkou_b"].shift(1)).abs() < flat_tol
        fwd_top = pd.concat([ichi["senkou_a"], ichi["senkou_b"]], axis=1).max(axis=1, skipna=False)
        fwd_bot = pd.concat([ichi["senkou_a"], ichi["senkou_b"]], axis=1).min(axis=1, skipna=False)
        levels = np.column_stack([
            np.where(flat_kijun, kijun, np.nan),
            np.where(flat_ssb, ichi["senkou_b"], np.nan),
            fwd_top.to_numpy(float), fwd_bot.to_numpy(float),
            close.shift(self.disp).to_numpy(float),
        ])

        tol = (self.conv_tol_atr * atr).to_numpy(float)
        setup_bull_arr = np.isin(setup_type, (1, 3))
        primary_tp = np.full(n, np.nan)
        for i in range(n):
            if setup_type[i] == 0 or not np.isfinite(tol[i]):
                continue
            best, best_dist = np.nan, np.inf
            for t in (tgt_v[i], tgt_n[i], tgt_e[i]):
                if not np.isfinite(t):
                    continue
                d = np.nanmin(np.abs(t - levels[i])) if np.isfinite(levels[i]).any() else np.inf
                if d <= tol[i]:
                    dd = abs(t - close.iloc[i])
                    if dd < best_dist:
                        best, best_dist = t, dd
            primary_tp[i] = best

        fallback = close.to_numpy(float) + np.where(setup_bull_arr, 1, -1) * self.fallback_tp_atr * atr.to_numpy(float)
        effective_tp = np.where(np.isfinite(primary_tp), primary_tp, fallback)

        # --- continuazione
        cloud_thick_ok = (ichi["span_a_now"] - ichi["span_b_now"]).abs() >= atr * 0.5
        pulled_long = (low <= tenkan) | (low <= kijun) | (low.shift(1) <= tenkan.shift(1)) | (low.shift(1) <= kijun.shift(1))
        resume_long = (close > tenkan) & (close > open_)
        cont_long = (ichi["cloud_bull"] & price_above & (htf["regime"] == 1)
                     & (kijun > kijun.shift(1)) & cloud_thick_ok & pulled_long
                     & resume_long & chikou_above)
        pulled_short = (high >= tenkan) | (high >= kijun) | (high.shift(1) >= tenkan.shift(1)) | (high.shift(1) >= kijun.shift(1))
        resume_short = (close < tenkan) & (close < open_)
        cont_short = (~ichi["cloud_bull"] & price_below & (htf["regime"] == -1)
                      & (kijun < kijun.shift(1)) & cloud_thick_ok & pulled_short
                      & resume_short & chikou_below) if self.enable_cont_short else pd.Series(False, index=df.index)

        self.d = {
            "close": close.to_numpy(float), "open": open_.to_numpy(float),
            "high": high.to_numpy(float), "low": low.to_numpy(float),
            "atr": atr.to_numpy(float), "adx": adx.to_numpy(float),
            "tenkan": tenkan.to_numpy(float), "kijun": kijun.to_numpy(float),
            "cloud_top": cloud_top.to_numpy(float), "cloud_bot": cloud_bot.to_numpy(float),
            "price_above": price_above.to_numpy(bool), "price_below": price_below.to_numpy(bool),
            "setup_type": setup_type, "setup_bull": setup_bull_arr,
            "tightness": tightness, "near_window": near_window,
            "effective_tp": effective_tp, "has_tp": np.isfinite(effective_tp),
            "htf_regime": htf["regime"].to_numpy(float),
            "htf_thick": htf["thick"].to_numpy(float),
            "htf_slope": htf["slope"].to_numpy(float),
            "htf_in_bull": htf["in_bull_sma"].fillna(False).to_numpy(bool),
            "cont_long": cont_long.fillna(False).to_numpy(bool),
            "cont_short": cont_short.fillna(False).to_numpy(bool),
            "tk_cross_dn": tk_dn.to_numpy(bool), "tk_cross_up": tk_up.to_numpy(bool),
            "close_x_kijun_dn": ind.crossunder(close, kijun).to_numpy(bool),
            "close_x_kijun_up": ind.crossover(close, kijun).to_numpy(bool),
        }

        self.last_con_exit = -10_000
        self.entry_kind = "REV"
        self.fired_s1 = self.fired_s2 = self.fired_be = False
        self.plan_sl = np.nan

    # ------------------------------------------------------------------
    def _score(self, i: int, is_sanyaku: bool, htf_aligned: bool, htf_strong: bool) -> int:
        d = self.d
        s = 0
        s += 1 if is_sanyaku else 0
        s += 1 if (is_sanyaku and np.isfinite(d["tightness"][i]) and d["tightness"][i] <= 17) else 0
        s += 1 if htf_aligned else 0
        s += 1 if (self.use_htf_strength and htf_strong) else 0
        s += 1 if d["has_tp"][i] else 0
        s += 1 if d["near_window"][i] else 0          # ltfConfirms non disponibile: vedi docstring
        s += 1 if (self.use_adx_score and d["adx"][i] >= self.adx_min) else 0
        s -= 1 if d["htf_regime"][i] == 0 else 0
        return max(s, 0)

    def entry(self, state: State) -> Intent | None:
        i, d = state.i, self.d

        # il Pine registra la barra di uscita delle sole operazioni di
        # continuazione, per imporre loro un cooldown dedicato
        if self.entry_kind == "CON" and state.last_exit_index > self.last_con_exit:
            self.last_con_exit = state.last_exit_index
            self.entry_kind = "REV"

        if not np.isfinite(d["cloud_top"][i]) or not np.isfinite(d["atr"][i]) or d["atr"][i] <= 0:
            return None
        if self.use_adx_gate and not d["adx"][i] >= self.adx_min:
            return None

        close, atr = d["close"][i], d["atr"][i]
        setup = d["setup_type"][i]
        setup_active = setup != 0
        setup_bull = bool(d["setup_bull"][i])
        is_sanyaku = setup in (1, 2)

        htf_aligned = setup_active and ((setup_bull and d["htf_regime"][i] == 1)
                                        or (not setup_bull and d["htf_regime"][i] == -1))
        htf_conflict = setup_active and ((setup_bull and d["htf_regime"][i] == -1)
                                          or (not setup_bull and d["htf_regime"][i] == 1))
        htf_strong = (d["htf_thick"][i] >= self.htf_thick_min
                      and ((setup_bull and d["htf_slope"][i] == 1) or (not setup_bull and d["htf_slope"][i] == -1)))

        setup_passes = setup_active and (not htf_conflict or self.reveal_counter)
        score = self._score(i, is_sanyaku, htf_aligned, htf_strong) if setup_passes else 0

        if setup_bull:
            tier = "HIGH" if score >= self.tier_hi_min else "MODERATE" if score >= self.tier_mod_min else "LOW"
            risk_pct = self.risk_hi if tier == "HIGH" else self.risk_mod
        else:
            tier = "HIGH" if score >= self.tier_hi_min_short else "MODERATE" if score >= self.tier_mod_min_short else "LOW"
            risk_pct = self.risk_hi_short if tier == "HIGH" else self.risk_mod_short

        # stop: nuvola, con cap a maxStopATR. Nota: per gli ingressi di
        # continuazione setup_bull e' falso (nessun setup attivo), quindi lo
        # stop finisce su cloud_top invece che su cloud_bot — comportamento del
        # Pine, riprodotto fedelmente.
        raw_sl = d["cloud_bot"][i] if setup_bull else d["cloud_top"][i]
        if self.cap_stop_atr:
            plan_sl = (max(raw_sl, close - self.max_stop_atr * atr) if setup_bull
                       else min(raw_sl, close + self.max_stop_atr * atr))
        else:
            plan_sl = raw_sl
        risk_dist = abs(close - plan_sl)
        if not np.isfinite(risk_dist) or risk_dist <= 0:
            return None

        tp = d["effective_tp"][i]
        rr = abs(tp - close) / risk_dist if np.isfinite(tp) else np.nan
        rr_passes = np.isfinite(rr) and rr >= self.min_rr
        tier_ok = tier == "HIGH" or (tier == "MODERATE" and self.trade_moderate)
        short_gate_ok = (not self.use_sma_bull_gate) or (not d["htf_in_bull"][i])

        rev_long = setup_passes and setup_bull and d["has_tp"][i] and tier_ok and rr_passes
        rev_short = (setup_passes and not setup_bull and d["has_tp"][i] and tier_ok
                     and rr_passes and short_gate_ok)
        cooldown_ok = (i - self.last_con_exit) > self.cont_cooldown
        con_long = d["cont_long"][i] and cooldown_ok
        con_short = d["cont_short"][i] and cooldown_ok and short_gate_ok

        if rev_long or con_long:
            direction, kind = 1, ("REV" if rev_long else "CON")
        elif rev_short or con_short:
            direction, kind = -1, ("REV" if rev_short else "CON")
        else:
            return None

        self.entry_kind = kind
        self.fired_s1 = self.fired_s2 = self.fired_be = False
        self.plan_sl = plan_sl
        return Intent(direction=direction, stop_distance=risk_dist,
                      risk_mult=risk_pct, tag=f"{kind}-{tier}")

    # ------------------------------------------------------------------
    def manage(self, state: State) -> tuple[bool | float, float | None]:
        i, d = state.i, self.d
        long_ = state.direction > 0
        close, kijun = d["close"][i], d["kijun"][i]
        new_stop = None

        if self.entry_kind == "CON":
            if long_:
                floor_ = min(kijun, d["cloud_bot"][i]) if self.con_trail_kijun else d["cloud_bot"][i]
                new_stop = floor_ if np.isfinite(floor_) else None
            else:
                ceil_ = max(kijun, d["cloud_top"][i]) if self.con_trail_kijun else d["cloud_top"][i]
                new_stop = ceil_ if np.isfinite(ceil_) else None
            return False, new_stop

        # REV: breakeven a 1.5R, poi trail sul Kijun quando il Kijun si muove a favore
        if self.use_be_stop and not self.fired_be and np.isfinite(self.plan_sl):
            initial_risk = abs(state.entry_price - self.plan_sl)
            target = state.entry_price + (1 if long_ else -1) * self.be_r_mult * initial_risk
            if (close >= target) if long_ else (close <= target):
                new_stop = state.entry_price
                self.fired_be = True

        if self.trail_kijun and np.isfinite(kijun):
            rising = kijun > d["kijun"][i - 1] if i > 0 else False
            falling = kijun < d["kijun"][i - 1] if i > 0 else False
            if long_ and kijun < close and rising:
                new_stop = kijun if new_stop is None else max(new_stop, kijun)
            elif (not long_) and kijun > close and falling:
                new_stop = kijun if new_stop is None else min(new_stop, kijun)

        # uscita totale se il prezzo perde la nuvola
        if long_ and d["price_below"][i]:
            return True, new_stop
        if (not long_) and close >= d["cloud_bot"][i]:
            return True, new_stop

        # uscite scalate
        if long_ and d["tk_cross_dn"][i] and not self.fired_s1:
            self.fired_s1 = True
            return self.split_stage1, new_stop
        if (not long_) and d["tk_cross_up"][i] and not self.fired_s1:
            self.fired_s1 = True
            return self.split_stage1, new_stop
        if long_ and d["close_x_kijun_dn"][i] and not self.fired_s2:
            self.fired_s2 = True
            return self.split_stage2, new_stop
        if (not long_) and d["close_x_kijun_up"][i] and not self.fired_s2:
            self.fired_s2 = True
            return self.split_stage2, new_stop

        return False, new_stop
