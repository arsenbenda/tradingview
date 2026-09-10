# Trend Rebalance Map [Herman] — BTC/USD backtest

**Verdict: it does not work on BTC/USD.** Not with the published settings, and not
with any of the 990 adapted settings tested. The published defaults lose the entire
account on intraday timeframes; the adapted versions that look profitable in one
window fail in the next.

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
resampled to 5m / 15m / 1h / 4h / 1d. Real USD spot, not a USDT-perp proxy.

**Fill model** — matches the Pine header:
`process_orders_on_close = true` (entry at the close of the signal bar); stop/limit
orders issued at the close of bar *i* are live from bar *i+1* (no look-ahead); the
dynamic 200 SMA target is re-issued every bar; TradingView's intrabar path
assumption (up bar O→L→H→C, down bar O→H→L→C); gaps fill at the open; slippage on
stop fills only; commission charged per side.

The port was verified trade-by-trade against hand-computed signals, SMA values, stop
levels, fills and P&L, plus invariant checks (no overlapping positions, no exit
before entry, the `lastExitBar` no-re-entry guard, no stop fill better than its
level).

---

## 2. The published defaults on BTC/USD

Verbatim Pine inputs — 30-point separation, 125-point stop, 200 SMA dynamic target,
1 BTC per trade, $100,000 account, $2.50/contract, 2 ticks slippage:

| Timeframe | Trades | Win rate | Profit factor | Net profit | Max DD |
|---|---|---|---|---|---|
| 5m | 18,941 | 40.9 % | **0.86** | **−187.0 %** | −188.9 % |
| 15m | 8,017 | 32.0 % | **0.85** | **−100.0 %** | −100.8 % |
| 1h | 2,448 | 23.7 % | **0.75** | **−58.8 %** | −58.8 % |
| 4h | 660 | 16.5 % | **0.79** | **−14.5 %** | −16.9 % |
| 1d | 92 | 8.7 % | **0.68** | **−3.4 %** | −7.8 % |

*(2017-01-01 → 2026-09-10. Net profit below −100 % means the account was wiped out
and kept trading — TradingView's default 0 % margin does the same.)*

**Why:** the defaults are calibrated for index futures, where price is ~20,000 and
roughly constant over a test. `125 points` is 0.6 % of NQ. On BTC it is **0.47 % of
the median close** — and 0.10 % at $126,000. The stop sits inside a single bar's
noise, so 82–95 % of trades stop out. The 30-point separation filter is even more
degenerate: **$30 apart on a $100,000 asset**, so it never filters anything.

---

## 3. Adapting it properly (990 configurations)

Both broken inputs were re-expressed as a share of price, and the stop was also
tried as an ATR multiple — the two fixes a quant would actually make. Everything
else (signal, direction rule, one-trade-at-a-time, dynamic 200 SMA target) is
unchanged.

* timeframes: 5m, 15m, 1h, 4h, 1d
* separation filter: 0.15 / 0.5 / 1 / 2 / 3 / 5 % of price
* stop: 0.625 / 1.5 / 3 / 5 / 8 % of price, "1R to TP", or 1 / 1.5 / 2 / 3 / 4 × ATR(14)
* direction: both / long only / short only
* costs: 0.05 % per side (realistic spot taker) + 2 ticks slippage, constant $10k notional

**Walk-forward, not curve-fit:** every configuration was *selected* on
**2017–2021** and then measured on data never used for selection —
**2022 → today** (forward) and **2012–2016** (backward).

| | result |
|---|---|
| Configurations tested | **990** |
| Median profit factor, selection window | **0.72** |
| Median profit factor, forward out-of-sample | **0.77** |
| Profitable in the selection window (PF > 1, ≥ 30 trades) | 50 |
| Profitable in the selection window **and** forward | **3** |
| Still profitable after also surviving 2012–2016 **and** deleting its single best trade | **0** |

Per timeframe, configurations with PF > 1:

| Timeframe | Configs | Profitable in-sample | Profitable forward-OOS | Median forward PF |
|---|---|---|---|---|
| 5m | 198 | **0** | 11 | 0.68 |
| 15m | 198 | **0** | 8 | 0.81 |
| 1h | 198 | **0** | 21 | 0.89 |
| 4h | 198 | 28 | 9 | 0.75 |
| 1d | 198 | 162 | 29 | 0.74 |

**Not one intraday configuration (5m/15m/1h — 594 of them) was profitable in the
window used to pick it.** The daily timeframe looks strong in-sample (162/198) and
then collapses forward (29/198) — the signature of a small sample, not an edge:
a daily config gets ~35 trades in five years.

Direction matters, and not in the strategy's favour: shorting BTC rallies is the
worse half (median PF 0.64 in-sample vs 0.82 for long-only), which is what you would
expect from fading an asset that trends up violently.

---

## 4. The best configuration, followed forward

Best in-sample of all 990: **daily, both directions, 5 % separation filter, 0.625 %
stop**, PF 4.14 on 2017–2021. What happened next:

| Window | Trades | Win rate | Profit factor | Sum of per-trade returns |
|---|---|---|---|---|
| In-sample 2017–2021 | 34 | 11.8 % | **4.14** | +70.6 % |
| **Forward OOS 2022–2026** | 43 | 2.3 % | **0.16** | **−25.7 %** |
| **Backward OOS 2012–2016** | 38 | 2.6 % | **0.18** | **−182.4 %** |
| Full 2012–2026 | 124 | 4.8 % | **0.49** | −137.5 % |

*(Returns are summed per-trade on the traded notional, so they are comparable
across a 100× change in the price of the asset.)*

Per calendar year (2017+), the entire profit is three years wide:

| 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|
| −237 | −675 | **+2,216** | **+3,539** | **+2,215** | −879 | −440 | −729 | −163 | −728 |

It is a lottery-ticket profile: a 6 % win rate where **78 % of all gross profit comes
from three trades**. Delete the single best trade and the 2017+ profit factor falls
from 1.73 to 1.24; delete the best **two** and it is 0.78 — already a losing system.

Robustness of that same config (2017+): long-only PF 3.61 vs short-only **0.16**;
raise costs from 0.05 % to 0.10 % per side and PF drops 1.73 → 1.51; move the fast
average from 50 to 20 and PF falls to **0.42**, move the slow average to 100 or 400
and it rises to 1.92 / 2.50. A real edge has a plateau around it; this has a spike.

**Against buy-and-hold**, same window (2017-01-01 → 2026-09-10):

| | Net | CAGR | Max DD | Time in market |
|---|---|---|---|---|
| Strategy (100 % of equity per trade, compounding) | +36.6 % | 3.3 % | −28.5 % | 7.0 % |
| BTC buy & hold | **+7,731.6 %** | 56.8 % | −83.4 % | 100 % |

---

## 5. Why it fails on BTC specifically

1. **Every input is in absolute points.** A 125-point stop and a 30-point separation
   filter cannot mean the same thing at $13 and at $126,000. This alone destroys the
   published version.
2. **The target is structurally far away.** At signal time the 200 SMA sits a median
   **2.1 %** away on 1h, **4.7 %** on 4h and **16.7 %** on daily (90th percentile:
   37 % on daily). Combined with any stop tight enough to survive costs, the trade
   needs a 4:1 to 35:1 payoff to break even — so the win rate collapses to single
   digits and the result is decided by a handful of outliers.
3. **It fades the strongest trending liquid asset there is.** The short leg — sell
   when price dips under the SMA50 while the SMA50 is *above* the SMA200 — is exactly
   the bet BTC punishes. It loses in essentially every configuration.
4. **Costs.** A 0.05 %/side round turn is 0.1 %. On 5m the strategy takes ~19,000
   trades over 9 years; the cost drag alone is larger than the edge being sought.
5. **Widening the stop does not fix it** — it converts a 6 % win rate into a 60 %
   win rate with proportionally larger losses, and profit factor stays under 1
   (see 15m long-only 8 % stop: 65.9 % win rate, PF 0.84).

---

## 6. What would make it BTC-viable

Not a settings change — a change to the premise:

* Percentage- or ATR-based separation and stop (necessary, not sufficient).
* Long only. The short side has no support in this data.
* A closer target than the 200 SMA — a partial retracement (e.g. 0.5 × the distance
  to the SMA200) — so the payoff needed is 3:1 rather than 35:1.
* A regime filter that stands the strategy down when the 50/200 pair is separated by
  more than ~10 % (a trend, not a stretch), which is where the current filter
  actively encourages entries.

Even then, nothing in this data suggests a durable edge — the 4h long-only variants
that survived one out-of-sample window die in the other.

---

## 7. Caveats

* Bitstamp spot; another venue's feed will move individual trades slightly. Results
  this one-sided are not going to flip on feed choice.
* Missing minutes in the source are flat zero-volume candles (documented upstream);
  they neither create nor mask stop touches.
* Intrabar fill order uses TradingView's OHLC path assumption. With both stop and
  target inside one bar the outcome is an assumption, not a fact — but with 82–95 %
  of trades exiting at the stop, the direction of the result does not depend on it.
* Bitcoin's 2012–2016 era is thin and structurally different; it is reported
  separately and never used to select parameters.

## Reproducing

```bash
pip install pandas pyarrow
git clone --depth 1 https://github.com/ff137/bitstamp-btcusd-minute-data /tmp/btcsrc
python3 backtest/data_prep.py /tmp/btcsrc backtest/data   # resample 1m -> 5m..1d
python3 backtest/run_btc.py                               # all four phases -> results/
```

Outputs: `phase1_pine_defaults.csv`, `phase2_sweep.csv` (990 rows),
`phase3_*.csv`, `phase4_fragility.csv`, `phase3_trades.csv`.
