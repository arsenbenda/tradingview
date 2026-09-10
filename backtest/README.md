# BTC/USD backtest harness

A Python port of the Pine Script strategy in
`strategies/trend_rebalance_map_herman_v1.1.pine`, plus the data pipeline and the
walk-forward test matrix used to produce
[`../results/BTCUSD_backtest.md`](../results/BTCUSD_backtest.md).

| File | Purpose |
|---|---|
| `data_prep.py` | Resamples Bitstamp BTC/USD 1-minute candles to 5m/15m/1h/4h/1d |
| `trm_engine.py` | Bar-by-bar port of the strategy + TradingView's fill model |
| `metrics.py` | Trade statistics, per-year breakdown, drawdown, Sharpe |
| `run_btc.py` | The four test phases (defaults, sweep, deep dive, fragility) |
| `export_report_data.py` | Compact JSON bundle of the results for the report |

```bash
pip install pandas pyarrow
git clone --depth 1 https://github.com/ff137/bitstamp-btcusd-minute-data /tmp/btcsrc
python3 data_prep.py /tmp/btcsrc data     # ~65 MB of parquet, git-ignored
python3 run_btc.py                        # writes ../results/*.csv
```

The engine is not TRM-specific in its fill logic: `Params` + `run()` will take any
SMA-pair mean-reversion variant, and `sl_mode` supports fixed points, percent of
price, ATR multiples and "1R to TP".
