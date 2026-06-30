"""Sample OHLCV prices bundled with bartons — polars only."""

from functools import lru_cache
from importlib import resources

import polars as pl


TIMEZONE = "America/New_York"
SAMPLE_FREQUENCIES = ("daily", "hourly", "minute")
SAMPLE_TICKERS = tuple(f"T{i:03d}" for i in range(1, 501))


@lru_cache
def sample_prices(freq: str = "daily", *, max_bars: int = 0) -> pl.DataFrame:
    """Load bundled sample OHLCV prices for testing and examples.

    Results are cached after the first call (per unique combination of
    arguments).

    Args:
        freq: Data frequency. One of ``"daily"``, ``"hourly"``, or
            ``"minute"``. Defaults to ``"daily"``.
        max_bars: If greater than 0, return only the most recent
            ``max_bars`` rows. Defaults to 0 (return all rows).

    Returns:
        Polars DataFrame with a temporal first column
        (``date`` for daily, ``datetime`` for hourly / minute) plus
        ``open``, ``high``, ``low``, ``close``, ``volume``.
    """

    if freq not in SAMPLE_FREQUENCIES:
        raise ValueError(f"Unknown freq {freq!r}; expected one of {SAMPLE_FREQUENCIES}")

    fname = f"{freq}-prices.csv"
    path = resources.files(__name__).joinpath(fname)

    with path.open("rb") as file:
        prices = pl.read_csv(file, try_parse_dates=True)

    col = prices.columns[0]  # "date" (daily) or "datetime" (hourly/minute)

    if freq != "daily":
        tz = getattr(prices.schema[col], "time_zone", None)
        if tz is None:
            prices = prices.with_columns(
                pl.col(col).dt.replace_time_zone("UTC").dt.convert_time_zone(TIMEZONE)
            )
        else:
            prices = prices.with_columns(pl.col(col).dt.convert_time_zone(TIMEZONE))

    if max_bars > 0:
        prices = prices.tail(max_bars)

    return prices


@lru_cache
def sample_dataset(
    n_tickers: int = 500,
    *,
    freq: str = "daily",
    max_bars: int = 0,
) -> pl.DataFrame:
    """Synthetic multi-ticker dataset for benchmarking `.over()` expressions.

    Stacks ``n_tickers`` copies of :func:`sample_prices` with a synthetic
    ``ticker`` column (``"T001"`` … ``"T500"``), sorted by ``(ticker, date)``
    so it is ready for ``.over("ticker")`` use.

    Results are cached after the first call (per unique combination of
    arguments).

    Args:
        n_tickers: Number of synthetic tickers to generate. Defaults to 500.
        freq: Data frequency passed to :func:`sample_prices`. Defaults to
            ``"daily"``.
        max_bars: Passed to :func:`sample_prices`. Defaults to 0 (all rows).

    Returns:
        Polars DataFrame with a leading ``ticker`` column followed by the same
        temporal and OHLCV columns as :func:`sample_prices`.
    """
    prices = sample_prices(freq=freq, max_bars=max_bars)
    date_col = prices.columns[0]
    tickers = SAMPLE_TICKERS[:n_tickers]
    frames = [
        prices.select(pl.lit(t).alias("ticker"), pl.all()) for t in tickers
    ]
    return pl.concat(frames).sort("ticker", date_col)
