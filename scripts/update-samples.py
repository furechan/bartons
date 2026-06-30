"""Download and update bundled sample prices (AAPL OHLCV via yfinance).

Requires pandas + yfinance, which live in the optional `samples` dependency
group (kept out of the default dev sync). Install and run with:

    uv sync --group samples
    python scripts/update-samples.py
"""

from functools import lru_cache
from pathlib import Path

import pandas as pd
import yfinance as yf  # type: ignore

ROOTDIR = Path(__file__).parent.parent
SAMPLES = ROOTDIR.joinpath("python/bartons/samples").resolve(strict=True)

TICKER = "AAPL"

INTERVAL  = dict(daily="1d",  hourly="1h", minute="1m")
PERIOD    = dict(daily="max", hourly="2Y", minute="7d")

EXPECTED_COLUMNS = ["open", "high", "low", "close", "volume"]
EXPECTED_INDEX   = dict(daily="date", hourly="datetime", minute="datetime")
NUMERIC_COLS     = ["open", "high", "low", "close"]
MIN_ROWS         = dict(daily=5000, hourly=500, minute=100)


def check(prices: pd.DataFrame, freq: str) -> None:
    errors = []

    if list(prices.columns) != EXPECTED_COLUMNS:
        errors.append(f"columns: expected {EXPECTED_COLUMNS}, got {list(prices.columns)}")

    expected_index = EXPECTED_INDEX[freq]
    if prices.index.name != expected_index:
        errors.append(f"index name: expected {expected_index!r}, got {prices.index.name!r}")

    for col in NUMERIC_COLS:
        if col in prices.columns:
            if not pd.api.types.is_numeric_dtype(prices[col]):
                errors.append(f"column {col!r}: expected numeric, got {prices[col].dtype}")

    min_rows = MIN_ROWS[freq]
    if len(prices) < min_rows:
        errors.append(f"row count: expected >= {min_rows}, got {len(prices)}")

    if errors:
        raise ValueError(f"Sanity check failed for {freq!r}:\n" + "\n".join(f"  - {e}" for e in errors))


@lru_cache
def fetch_prices(ticker: str, *, freq: str = "daily") -> pd.DataFrame:
    interval = INTERVAL[freq]
    period   = PERIOD[freq]

    prices = yf.download(ticker, interval=interval, period=period,
                         auto_adjust=True, progress=False)

    if prices is None or prices.empty:
        raise ValueError(f"No data for {ticker!r} freq={freq!r}")

    prices = prices.filter(["Open", "High", "Low", "Close", "Volume"])
    prices = prices.rename(columns=str.lower).rename_axis(index=str.lower)

    return prices


if __name__ == "__main__":
    for freq in INTERVAL:
        prices = fetch_prices(TICKER, freq=freq)

        check(prices, freq)

        outfile = SAMPLES / f"{freq}-prices.csv"
        data = prices.to_csv(lineterminator="\n")
        print(f"Updating {outfile.name} ... ({len(prices)} rows)")
        outfile.write_text(data)
