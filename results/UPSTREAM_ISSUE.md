# Ready-to-post upstream contribution

**Target:** https://github.com/HermanTrading/Trend-Rebalance-Map-Herman-/issues/new
**Title:** `BTC/USD backtest: 6 timeframes, 1,188 parameter sets, 14 years of spot data (code + data included)`

Everything below the line is the issue body. Post it as-is, or edit first — it is
deliberately framed as a data contribution about an instrument the script was never
calibrated for, not as a defect report.

---

Hi — thanks for publishing this under MPL-2.0 with the repaint statement and the engine
notes. Having the actual source made it straightforward to port, which is why this was
worth doing at all.

I ran Trend Rebalance Map v1.1 against **BTC/USD** and wanted to share the results, since
the README says nothing about crypto and the answer turned out to be clear enough to be
useful to anyone who tries it. **This is not a bug report** — the tooltips are explicit
that `Price Units Per Point` is calibrated for index futures such as NQ/MNQ, and the
script does exactly what it says it does. It is a note about what happens off that
instrument, and about one small change that would make the script portable.

Everything below is reproducible: the port, the data pipeline and every result CSV are
linked at the end.

## Setup

| | |
|---|---|
| Data | Bitstamp **BTC/USD spot**, 1-minute candles, 2012-01-01 → 2026-09-10 (7,727,131 minutes) |
| Source | https://github.com/ff137/bitstamp-btcusd-minute-data |
| Timeframes | 5m · 15m · 1h · 4h · 1d · 1w (resampled from the 1-minute series) |
| Port | Pine v6 → Python, bar-by-bar |

The port reproduces the execution model described in your header, as closely as I could:

- `process_orders_on_close = true` — entry fills at the close of the signal bar.
- Stop/limit orders issued at the close of bar *i* are live from bar *i+1*. No look-ahead.
- The **Dynamic** 200 SMA target is re-issued every bar, as the script does.
- TradingView's intrabar path assumption: up bar O→L→H→C, down bar O→H→L→C. Gaps fill at
  the open.
- Slippage on market/stop fills only (not on limit fills); commission charged per side.
- The `lastEntryBar` / `lastExitBar` guards, and one position at a time.

I checked it trade-by-trade against hand-computed crossovers, SMA values, stop levels,
fills and P&L before trusting any of it, plus invariants (no overlapping positions, no
exit before entry, no stop fill better than its own level). Moving averages are warmed up
on bars *preceding* each test window, so no window silently loses its first 200 bars.

## 1 · The published defaults on BTC/USD

Verbatim inputs — 30-point separation, 125-point stop, 200 SMA dynamic target — with
1 BTC per trade on a $100,000 account, $2.50/contract and 2 ticks slippage,
2017-01-01 → 2026-09-10:

| Timeframe | Trades | Win rate | Profit factor | Net | Stopped out |
|---|---|---|---|---|---|
| 5m | 18,941 | 40.9 % | 0.86 | −187.0 % | 54 % |
| 15m | 8,017 | 32.0 % | 0.85 | −100.0 % | 63 % |
| 1h | 2,449 | 23.7 % | 0.75 | −58.8 % | 72 % |
| 4h | 662 | 16.8 % | 0.79 | −14.3 % | 79 % |
| 1d | 95 | 8.4 % | 0.66 | −3.8 % | 89 % |
| 1w | 13 | 7.7 % | 0.01 | −1.6 % | 92 % |

The mechanism is just scale. `125 points` is ~0.6 % of NQ. On BTC it is **0.47 % of the
median close over this window — and 0.10 % at $126,000**, i.e. inside a single bar's
noise. `Minimum Separation = 30` is $30 on a six-figure asset, so the filter never
excludes anything.

`Price Units Per Point` is the intended lever here, and it does rescale both inputs — but
it cannot fix this one on its own, because BTC ran from $13 to $126,000 *inside a single
backtest*. Any constant `pointSize` that makes the stop sane in 2017 makes it absurd in
2025. That is the substantive finding, and it is the basis for the suggestion at the end.

## 2 · Rescaled properly, then walked forward

To separate "the defaults don't fit BTC" from "the premise doesn't work on BTC", I
re-expressed the two point-based inputs as a **share of price**, and also tried the stop as
an **ATR(14) multiple**. Signal, direction rule, one-trade-at-a-time and the dynamic 200
SMA target are untouched.

- separation filter: 0.15 / 0.5 / 1 / 2 / 3 / 5 % of price
- stop: 0.625 / 1.5 / 3 / 5 / 8 % of price, `1R to TP`, or 1 / 1.5 / 2 / 3 / 4 × ATR
- direction: both / long only / short only
- costs: 0.05 % per side (realistic spot taker) + 2 ticks slippage, constant $10k notional

Each of the 1,188 combinations was **selected on 2017–2021**, then measured on data that
never touched the selection: **2022 → today** forward, and **2012–2016** backward.

| | |
|---|---|
| Configurations tested | **1,188** |
| Median profit factor, selection window | **0.71** |
| Median profit factor, forward out-of-sample | **0.76** |
| Profitable in the selection window (PF > 1, ≥ 30 trades) | 70 |
| …and also profitable forward | **1** |
| …and also profitable 2012–2016, and without its single best trade | **0** |

Per timeframe:

| TF | Configs | PF > 1 in-sample | PF > 1 forward | Median forward PF | Median trades (IS → fwd) |
|---|---|---|---|---|---|
| 5m | 198 | 0 | 11 | 0.68 | 1,291 → 545 |
| 15m | 198 | 0 | 8 | 0.81 | 860 → 468 |
| 1h | 198 | 0 | 15 | 0.88 | 345 → 260 |
| 4h | 198 | 39 | 8 | 0.74 | 106 → 103 |
| 1d | 198 | 121 | 27 | 0.58 | 17 → 22 |
| 1w | 198 | 24 | 108 | n/a | 5 → 2 |

**No intraday configuration — 594 of them across 5m, 15m and 1h — was profitable even in
the window used to choose it.** The 1w row is not a result: with a median of two forward
trades per configuration, "108 profitable" is 108 coin flips.

The best single configuration in-sample (daily, 5 % filter, 0.625 % stop) went **PF 3.56 →
0.14** forward, with 78 % of its gross profit coming from three trades out of 86.

## 3 · Daily and weekly

Daily is the strongest timeframe here, which is also what makes it the most misleading:
121 of 198 daily configurations clear break-even in the window that picked them, because
daily gives only ~17 trades per configuration in five years.

Weekly cannot be evaluated at all. A 200-week average is **3.8 years of warm-up** on a
chart with 767 bars in fourteen years, and at signal time the target sits a median **53 %**
away. The only weekly variant with a usable sample needed a different pair (SMA 10/40,
5 % stop → 50 trades, PF 1.60), and even that flips on the calendar:

| Where the week is cut | Trades | PF 2012–19 | PF 2019–26 | PF full |
|---|---|---|---|---|
| Weeks open Monday | 50 | 1.85 | 1.33 | 1.60 |
| Weeks open Sunday | 51 | 1.35 | 0.82 | 1.09 |

## 4 · Why, structurally

1. Absolute-point inputs cannot hold their meaning across a 100× price range inside one
   test.
2. The 200 SMA target is far away on this instrument: a median 2.1 % on 1h, 4.7 % on 4h,
   16.7 % on daily, 53.2 % on weekly. With a stop tight enough to survive costs, the
   required payoff is 4:1 to 35:1, so the win rate collapses into single digits and a
   handful of outliers decide the outcome.
3. The short leg fades an asset that trends up violently — it loses in essentially every
   configuration tested (median in-sample PF 0.64 short-only vs 0.82 long-only).

## 5 · The one change that would help

Everything above is downstream of a single portability limit: the separation filter and
the stop are fixed distances. A **mode switch on those two inputs** — points (today's
behaviour, default, nothing changes for NQ/MNQ users) vs. **percent of price** or an **ATR
multiple** — would let the script run unmodified on instruments whose price scale moves,
crypto included. It touches two `input.float`s and two expressions, and it needs no
plan-gated API, so it stays inside the constraints you set out in the header.

To be clear about what that would and would not achieve: on this data it makes the script
*testable* on BTC rather than *profitable* on it. I could not find a durable edge here on
any timeframe. But it would stop the script from silently misbehaving for anyone who loads
it on a symbol priced far from ~20,000.

## Caveats

- Bitstamp spot; another venue's candles will move individual trades. Nothing this
  one-sided flips on feed choice, but the exact figures would shift.
- Where the stop and target both sit inside one bar, the outcome is TradingView's path
  assumption, not a fact. 82–95 % of trades exit at the stop, so the conclusion does not
  rest on it.
- **This is my port, not your script.** It agrees with the Pine source as I read it and it
  is verified against hand-computed trades, but if you spot a place where it diverges from
  the broker emulator I would genuinely like to know — the code is public and I will fix
  and re-run.
- 2012–2016 Bitcoin is thin and structurally different; it is reported separately and
  never used to select parameters.

## Reproducing

Port, data pipeline, five-phase test matrix and every result CSV (all 1,188 sweep rows,
every individual trade):

- Code and results: https://github.com/arsenbenda/tradingview/tree/claude/btc-usd-backtest-0indhb
- Write-up: https://github.com/arsenbenda/tradingview/blob/claude/btc-usd-backtest-0indhb/results/BTCUSD_backtest.md

```bash
pip install pandas pyarrow
git clone --depth 1 https://github.com/ff137/bitstamp-btcusd-minute-data /tmp/btcsrc
python3 backtest/data_prep.py /tmp/btcsrc backtest/data
python3 backtest/run_btc.py
```

Happy to send the percent/ATR mode as a PR against `Trend Rebalance Map [Herman].txt` if
that is useful, or to re-run anything here with different assumptions. Thanks again for
open-sourcing it.

---
_Generated by [Claude Code](https://claude.ai/code)_
