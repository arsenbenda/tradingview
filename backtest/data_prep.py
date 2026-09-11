"""
Build resampled BTC/USD OHLCV bars from Bitstamp 1-minute data.

Source: https://github.com/ff137/bitstamp-btcusd-minute-data
        (Bitstamp BTC/USD 1-minute OHLC, 2012-01-01 -> present, daily updated)

The source guarantees one row per minute; minutes with no trades are filled
with flat zero-volume candles.  We keep those (they do not move H/L) but we
count how many real (volume > 0) minutes each resampled bar contains so that
exchange-outage bars can be identified downstream.

Usage:  python3 data_prep.py <src_repo_dir> <out_dir>
"""
import sys
import os
import pandas as pd

TFS = {
    "5m": "5min",
    "15m": "15min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1D",
    "1w": "W0",
    "1w-sun": "W6",
}


def load_minutes(src: str) -> pd.DataFrame:
    bulk = os.path.join(src, "data/historical/btcusd_bitstamp_1min_2012-2025.csv.gz")
    upd = os.path.join(src, "data/updates/btcusd_bitstamp_1min_latest.csv")
    cols = ["timestamp", "open", "high", "low", "close", "volume"]
    a = pd.read_csv(bulk, usecols=cols)
    b = pd.read_csv(upd, usecols=cols)
    df = pd.concat([a, b], ignore_index=True)
    df = df.drop_duplicates(subset="timestamp", keep="last").sort_values("timestamp")
    df["dt"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    return df.set_index("dt")[["open", "high", "low", "close", "volume"]]


def week_key(index, anchor: int = 0):
    """Start-of-week timestamp; anchor 0 = Monday, 6 = Sunday."""
    return index.normalize() - pd.to_timedelta((index.dayofweek - anchor) % 7, unit="D")


def resample(m: pd.DataFrame, rule: str) -> pd.DataFrame:
    if rule.startswith("W"):                       # "W0" Monday .. "W6" Sunday
        grouper = week_key(m.index, int(rule[1:]))
        out = m.groupby(grouper).agg(
            open=("open", "first"), high=("high", "max"), low=("low", "min"),
            close=("close", "last"), volume=("volume", "sum"))
        out["live_minutes"] = (m["volume"] > 0).groupby(grouper).sum().astype("int32")
        out.index.name = "dt"
        return out.dropna(subset=["open"])
    out = m.resample(rule, label="left", closed="left").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    live = (m["volume"] > 0).resample(rule, label="left", closed="left").sum()
    out["live_minutes"] = live.astype("int32")
    return out.dropna(subset=["open"])


def main() -> None:
    src = sys.argv[1] if len(sys.argv) > 1 else "/home/user/ff137/bitstamp-btcusd-minute-data"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "/home/user/tradingview/backtest/data"
    os.makedirs(out_dir, exist_ok=True)

    m = load_minutes(src)
    print(f"minutes: {len(m):,}  {m.index[0]} -> {m.index[-1]}")

    for name, rule in TFS.items():
        bars = resample(m, rule)
        path = os.path.join(out_dir, f"btcusd_bitstamp_{name}.parquet")
        bars.to_parquet(path)
        print(f"{name:>4}: {len(bars):>9,} bars  {bars.index[0].date()} -> "
              f"{bars.index[-1].date()}  -> {path}")


if __name__ == "__main__":
    main()
