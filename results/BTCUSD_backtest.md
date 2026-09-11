# Trend Rebalance Map [Herman] — BTC/USD backtest

📉 **[Visual report](https://claude.ai/code/artifact/2b6a6902-5cd1-4d39-86e9-530eeb6236ec)** — charts, the full walk-forward scatter and the fragility screen.

**Verdict: it does not work on BTC/USD.** Not with the published settings, and not with
any of the 1,188 adapted settings tested across six timeframes. The published defaults
lose the entire account on intraday timeframes; the adapted versions that look profitable
in one window fail in the next. **1D is the best of the six** — which is exactly what makes
it the most misleading. **1W cannot be tested at all**: the strategy fires 13 times in
fourteen years.

---

## 1. What was tested

**Strategy** — [Trend Rebalance Map [Herman] v1.1](https://github.com/HermanTrading/Trend-Rebalance-Map-Herman-),
Pine Script v6, ported to Python (`backtest/trm_engine.py`).

It is a **mean-reversion** system, not a trend system:

| | condition | target |
|---|---|---|
| Long | `close` crosses **above** SMA50 while **SMA50 < SMA200** (i.e. in a downtrend) | the SMA200, above |
| Short | `close` crosses **below** SMA50 while **SMA50 > SMA200** (i.e. in an uptrend) | the SMA200, below |

Both sides are gated by a separation filter (`|SMA50 − SMA200| > 30 points`) and
protected by a fixed 125-point stop. One position at a time; opposite signals are
ignored while a trade is open.

**Data** — Bitstamp **BTC/USD spot** 1-minute candles, `2012-01-01 → 2026-09-10`
(7,727,131 minutes), from
[ff137/bitstamp-btcusd-minute-data](https://github.com/ff137/bitstamp-btcusd-minute-data),
resampled to 5m / 15m / 1h / 4h / 1d / 1w. Real USD spot, not a USDT-perp proxy.
Weekly bars open Monday 00:00 UTC (the Sunday-open alternative is tested in §5).

**Fill model** — matches the Pine header: `process_orders_on_close = true` (entry at the
close of the signal bar); stop/limit orders issued at the close of bar *i* are live from
bar *i+1* (no look-ahead); the dynamic 200 SMA target is re-issued every bar;
TradingView's intrabar path assumption (up bar O→L→H→C, down bar O→H→L→C); gaps fill at
the open; slippage on stop fills only; commission charged per side.

**Warm-up** — moving averages are fed from the bars *preceding* each test window, and only
entries are gated to the window. Slicing a window first and computing a 200-period SMA
inside it throws away its first 200 bars — 11 % of a five-year daily window and 77 % of a
five-year weekly one.

The port was verified trade-by-trade against hand-computed signals, SMA values, stop
levels, fills and P&L, plus invariant checks (no overlapping positions, no exit before
entry, the `lastExitBar` no-re-entry guard, no stop fill better than its level).

---

## 2. The published defaults on BTC/USD

Verbatim Pine inputs — 30-point separation, 125-point stop, 200 SMA dynamic target,
1 BTC per trade, $100,000 account, $2.50/contract, 2 ticks slippage:

| Timeframe | Trades | Win rate | Profit factor | Net profit | Max DD |
|---|---|---|---|---|---|
| 5m | 18,941 | 40.9 % | **0.86** | **−187.0 %** | −188.9 % |
| 15m | 8,017 | 32.0 % | **0.85** | **−100.0 %** | −100.8 % |
| 1h | 2,449 | 23.7 % | **0.75** | **−58.8 %** | −58.8 % |
| 4h | 662 | 16.8 % | **0.79** | **−14.3 %** | −16.9 % |
| **1d** | 95 | 8.4 % | **0.66** | **−3.8 %** | −7.8 % |
| **1w** | 13 | 7.7 % | **0.01** | **−1.6 %** | −1.6 % |

*(2017-01-01 → 2026-09-10. Net profit below −100 % means the account was wiped out and
the test kept trading — TradingView's default 0 % margin does the same.)*

**Why:** the defaults are calibrated for index futures, where price is ~20,000 and roughly
constant over a test. `125 points` is 0.6 % of NQ. On BTC it is **0.47 % of the median
close** — and 0.10 % at $126,000. The stop sits inside a single bar's noise, so 82–95 % of
trades stop out. The 30-point separation filter is even more degenerate: **$30 apart on a
$100,000 asset**, so it never filters anything.

---

## 3. Adapting it properly (1,188 configurations)

Both broken inputs were re-expressed as a share of price, and the stop was also tried as
an ATR multiple — the two fixes a quant would actually make. Everything else (signal,
direction rule, one-trade-at-a-time, dynamic 200 SMA target) is unchanged.

* timeframes: 5m, 15m, 1h, 4h, 1d, 1w
* separation filter: 0.15 / 0.5 / 1 / 2 / 3 / 5 % of price
* stop: 0.625 / 1.5 / 3 / 5 / 8 % of price, "1R to TP", or 1 / 1.5 / 2 / 3 / 4 × ATR(14)
* direction: both / long only / short only
* costs: 0.05 % per side (realistic spot taker) + 2 ticks slippage, constant $10k notional

**Walk-forward, not curve-fit:** every configuration was *selected* on **2017–2021** and
then measured on data never used for selection — **2022 → today** (forward) and
**2012–2016** (backward).

| | result |
|---|---|
| Configurations tested | **1,188** |
| Median profit factor, selection window | **0.71** |
| Median profit factor, forward out-of-sample | **0.76** |
| Profitable in the selection window (PF > 1, ≥ 30 trades) | 70 |
| Profitable in the selection window **and** forward | **1** |
| Still profitable after also surviving 2012–2016 **and** deleting its single best trade | **0** |

Per timeframe:

| Timeframe | Configs | PF > 1 in-sample | PF > 1 forward | Median forward PF | Median trades (IS → fwd) |
|---|---|---|---|---|---|
| 5m | 198 | **0** | 11 | 0.68 | 1,291 → 545 |
| 15m | 198 | **0** | 8 | 0.81 | 860 → 468 |
| 1h | 198 | **0** | 15 | 0.88 | 345 → 260 |
| 4h | 198 | 39 | 8 | 0.74 | 106 → 103 |
| 1d | 198 | 121 | 27 | 0.58 | 17 → 22 |
| 1w | 198 | 24 | 108 | *n/a* | **5 → 2** |

**Not one intraday configuration — 594 of them across 5m, 15m and 1h — was profitable in
the window used to pick it.** The 1w row is not a result: with a median of two forward
trades per configuration, "108 profitable" is 108 coin flips (see §5).

Direction matters, and not in the strategy's favour: shorting BTC rallies is the worse
half (median in-sample PF **0.64** short-only against 0.82 long-only), which is what you
would expect from fading an asset that trends up violently.

---

## 4. The best configuration, followed forward

Best in-sample of all 1,188: **daily, both directions, 5 % separation filter, 0.625 %
stop**, PF 3.56 on 2017–2021. What happened next:

| Window | Trades | Win rate | Profit factor | Sum of per-trade returns |
|---|---|---|---|---|
| In-sample 2017–2021 | 38 | 10.5 % | **3.56** | +67.0 % |
| **Forward OOS 2022–2026** | 48 | 2.1 % | **0.14** | **−29.4 %** |
| **Backward OOS 2012–2016** | 38 | 2.6 % | **0.18** | **−182.4 %** |
| Full 2012–2026 | 124 | 4.8 % | **0.49** | −144.8 % |

*(Returns are summed per-trade on the traded notional, so they stay comparable across a
100× change in the price of the asset.)*

Per calendar year (2017+, sum of per-trade returns), the entire profit is three years wide:

| 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|
| −6.0 | −6.8 | **+22.2** | **+35.4** | **+22.2** | −8.8 | −4.4 | −7.3 | −1.6 | −7.3 |

It is a lottery-ticket profile: five winners in 86 trades, with **78 % of all gross profit
from three of them**. Delete the single best trade and the 2017+ profit factor falls from
1.62 to 1.17; delete the best two and it is 0.73 — already a losing system.

Robustness of that same config (2017+): long-only PF 3.61 vs short-only **0.14**; raise
costs from 0.05 % to 0.10 % per side and PF drops 1.62 → 1.42; move the fast average from
50 to 20 and PF falls to **0.40**, move the slow average to 100 or 400 and it rises to
1.89 / 2.22. A real edge has a plateau around it; this has a spike.

**Against buy-and-hold**, same window (2017-01-01 → 2026-09-10):

| | Net | CAGR | Max DD | Time in market |
|---|---|---|---|---|
| Strategy (100 % of equity per trade, compounding) | +31.8 % | 2.9 % | −28.5 % | 7.1 % |
| BTC buy & hold | **+7,731.6 %** | 56.8 % | −83.4 % | 100 % |

---

## 5. 1D and 1W specifically

### 1D — the best of the six, and the most misleading

Daily is the only timeframe where the strategy is not obviously broken, and the only one
where a sweep produces in-sample winners in bulk: **121 of 198 daily configurations clear
break-even in the window used to pick them, and 27 still clear it forward.** That is the
trap. The one you would actually have chosen goes from PF 3.56 to 0.14, every calendar
year since 2022 is negative, and no daily configuration survives the full screen.

Daily also has the smallest sample of the tradeable timeframes — a median of 17 in-sample trades per
configuration, against 106 on 4h and 345 on 1h — which is why so many of them look good by accident.

### 1W — not a result, an empty sample

| | 1D | 1W |
|---|---|---|
| Bars in 14 years | 5,367 | 767 |
| 200-period SMA = | 0.5 years of warm-up | **3.8 years of warm-up** |
| Signals fired (50/200, 2017+) | 97 | **6** |
| Median distance to the 200 SMA target | 16.7 % | **53.2 %** |
| Median bar range | 4.0 % | 11.4 % |

With the published settings the weekly chart produces **13 trades in fourteen years** —
12 stopped out, 1 target hit, profit factor 0.01. Across the whole adapted weekly grid
(198 configurations over the full history): median **7 trades** per configuration, **none
reaches 30**, and only 60 reach 10. In the forward window every single configuration has
between one and three trades. Half of them "win". That is a coin, not a backtest.

**The one weekly variant with a usable sample is not this strategy.** Shortening the pair
to SMA 10/40 with a 5 % stop gives 50 trades over 14 years and PF 1.60 — the least-bad
result in the entire study. It then fails the simplest robustness test there is:

| Where the week is cut | Trades | PF 2012–2019 | PF 2019–2026 | PF full |
|---|---|---|---|---|
| Weeks open **Monday** | 50 | 1.85 | 1.33 | **1.60** |
| Weeks open **Sunday** | 51 | 1.35 | **0.82** | **1.09** |

Shifting the weekly candle by one day — an arbitrary charting convention, not a market
fact — turns a profitable recent half into a losing one. And even at its best it compounds
to +89 % over fourteen years (CAGR 4.5 %, max DD −51 %) against buy-and-hold's
+1,116,183 %.

The honest summary for weekly: **there is not enough data to say anything.** Bitcoin has
had roughly two and a half market cycles of weekly history; a 50/200 weekly pair samples
that a handful of times.

---

## 6. Can it be repaired? (the modified version)

Everything above tests the strategy **as published**. This section asks a different
question: given the three diagnosed failures, can the premise be modified into something
that clears profit factor 1 and stays there. Three changes, each answering one diagnosis:

| Diagnosis | Change |
|---|---|
| Target demands a 4:1–35:1 payoff | **Retrace target** — take a fraction of the way to the SMA200 instead of the whole trip |
| Separation filter encourages entries in a trend | **Separation cap** — stand down above a threshold |
| Fixed stop cannot scale | ATR multiple or percent of price |

960 combinations (4 timeframes × 2 directions × 4 retrace fractions × 5 stops × 2
separation floors × 3 caps), selected on 2017–2021, screened the same way as before.

**33 cleared break-even in-sample with ≥ 40 trades; 8 also cleared 2022–2026; 0 cleared
2012–2016 as well.**

### The selection actually carried information this time

Across all 960, only **8.3 %** are forward-profitable. Among the 33 in-sample winners,
**24.2 %** are — roughly 3× the base rate. In the unmodified study that same test showed no
advantage at all. The separation cap is a real effect on its own: with the cap at 10 %,
15.4 % of configurations are forward-profitable, against 4.9 % with no cap.

### The best candidate

**Daily · both directions · separation > 0.5 % · target 25 % of the way to the SMA200 ·
3 % stop**

| Window | Trades | Win rate | Profit factor | Avg trade |
|---|---|---|---|---|
| In-sample 2017–2021 | 41 | 43.9 % | **1.64** | +0.99 % |
| **Forward 2022–2026** | 54 | 59.3 % | **1.45** | +0.52 % |
| 2017 → today | 95 | 52.6 % | **1.55** | +0.72 % |
| **Backward 2012–2016** | 37 | 18.9 % | **0.19** | −5.66 % |

What holds up:

* **It is a plateau, not a spike.** 11 of 16 neighbouring daily configurations (retrace
  0.15–0.5 × stop 2–5 %) clear both windows, degrading smoothly at the edges. The
  unmodified strategy's best config was a lone spike surrounded by failures.
* **It survives costs.** PF 1.65 → 1.55 → 1.45 → 1.29 at 0 / 0.05 / 0.10 / 0.20 % per side.
* **No single trade carries it.** The best trade is 5.3 % of gross profit; PF without it is
  1.46. Forward profit excluding its best year (2025) is still +9.6 % over 39 trades.
* **Risk control works.** Worst trade since 2017 is −3.18 % against a 3 % stop, and 0 of 95
  trades are worse than −5 %.
* **The short side flips.** In the published version shorts were the disaster (PF 0.14).
  With a 25 % retrace target, shorts are the *better* half (PF 1.82 vs 1.28 long). A modest
  target on a bounce works where riding to the SMA200 did not.

What does not:

* **It fails 2012–2016** (PF 0.19) — the window pre-committed to as part of the screen.
  Three quarters of that damage is 2012 alone: 3 trades, one of them **−66 % on a 3 % stop**,
  a gap through the stop in a $5 market. But excluding 2012 entirely the window is still a
  loser (PF 0.48), so this is not only a data-era artifact.
* **It is the best of 960.** The base-rate test and the plateau argue against pure noise,
  but selection bias is not eliminated.
* **It is no longer this strategy.** The entry is the author's; the exit is not.
* **95 trades in 9.7 years**, 7.9 % of the time in the market. Small sample.
* Compounding 100 % of equity it returns **+84 %** over the period (CAGR 6.5 %, max DD
  −17.4 %, Sharpe 0.60) against buy-and-hold's +7,732 %. It is a low-exposure,
  low-drawdown profile, not a wealth engine.

**Honest verdict:** yes, profit factor above 1 that holds forward is reachable — but by
changing the exit rule, and it still fails one of the three windows the screen was built
around. Treat it as a lead worth more work, not a system to trade.

---

## 7. Why it fails on BTC specifically

1. **Every input is in absolute points.** A 125-point stop and a 30-point separation
   filter cannot mean the same thing at $13 and at $126,000. This alone destroys the
   published version.
2. **The target is structurally far away.** At signal time the 200 SMA sits a median
   **2.1 %** away on 1h, **4.7 %** on 4h, **16.7 %** on daily and **53.2 %** on weekly.
   Combined with any stop tight enough to survive costs, the trade needs a 4:1 to 35:1
   payoff to break even — so the win rate collapses to single digits and the result is
   decided by a handful of outliers.
3. **It fades the strongest trending liquid asset there is.** The short leg — sell when
   price dips under the SMA50 while the SMA50 is *above* the SMA200 — is exactly the bet
   BTC punishes. It loses in essentially every configuration.
4. **Costs.** A 0.05 %/side round turn is 0.1 %. On 5m the strategy takes ~19,000 trades
   over 9 years; the cost drag alone is larger than the edge being sought.
5. **Widening the stop does not fix it** — it converts a 6 % win rate into a 66 % win rate
   with proportionally larger losses, and profit factor stays under 1 (see 15m long-only
   with an 8 % stop: 65.9 % win rate, PF 0.84).
6. **Slowing it down does not fix it either.** Going up the timeframes trades the noise
   problem for a sample-size problem: by the time the stop is wide enough to survive BTC's
   bar range, there are too few trades left to know anything.

---

## 8. What would make it BTC-viable

Not a settings change — a change to the premise:

* Percentage- or ATR-based separation and stop (necessary, not sufficient).
* Long only. The short side has no support in this data.
* A closer target than the 200 SMA — a partial retracement (e.g. 0.5 × the distance to the
  SMA200) — so the payoff needed is 3:1 rather than 35:1.
* A regime filter that stands the strategy down when the 50/200 pair is separated by more
  than ~10 % (a trend, not a stretch), which is where the current filter actively
  encourages entries.
* On daily and above, a faster pair than 50/200. The 200-period average is a
  three-and-a-half-year object on a weekly chart.

Even then, nothing in this data suggests a durable edge — the 4h long-only variants that
survived one out-of-sample window die in the other, and the best weekly variant dies when
the week is cut on a different day.

---

## 9. Caveats

* Bitstamp spot; another venue's feed will move individual trades slightly. Results this
  one-sided are not going to flip on feed choice.
* Missing minutes in the source are flat zero-volume candles (documented upstream); they
  neither create nor mask stop touches.
* Intrabar fill order uses TradingView's OHLC path assumption. With both stop and target
  inside one bar the outcome is an assumption, not a fact — but with 82–95 % of trades
  exiting at the stop, the direction of the result does not depend on it.
* Bitcoin's 2012–2016 era is thin and structurally different; it is reported separately and
  never used to select parameters.
* Weekly results of every kind rest on tens of trades. They are reported for completeness,
  not as evidence.

## Reproducing

```bash
pip install pandas pyarrow
git clone --depth 1 https://github.com/ff137/bitstamp-btcusd-minute-data /tmp/btcsrc
python3 backtest/data_prep.py /tmp/btcsrc backtest/data   # resample 1m -> 5m..1w
python3 backtest/run_btc.py                               # all five phases -> results/
python3 backtest/run_btc_improve.py                       # the repair search -> results/
```

Outputs: `phase1_pine_defaults.csv`, `phase2_sweep.csv` (1,188 rows), `phase3_*.csv`,
`phase4_fragility.csv`, `phase5_*` (daily vs weekly), `phase6_*` (the repair search),
`phase3_trades.csv`.
