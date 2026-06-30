import polars as pl
import pytest

from bartons.samples import (
    SAMPLE_FREQUENCIES,
    SAMPLE_TICKERS,
    TIMEZONE,
    sample_dataset,
    sample_prices,
)

OHLCV = ["open", "high", "low", "close", "volume"]
# Temporal first-column name per frequency.
TIME_COL = {"daily": "date", "hourly": "datetime", "minute": "datetime"}


def test_frequencies_constant():
    assert SAMPLE_FREQUENCIES == ("daily", "hourly", "minute")


@pytest.mark.parametrize("freq", SAMPLE_FREQUENCIES)
def test_sample_prices_shape_and_columns(freq):
    df = sample_prices(freq)
    assert isinstance(df, pl.DataFrame)
    assert df.height > 0
    assert df.columns == [TIME_COL[freq]] + OHLCV


@pytest.mark.parametrize("freq", SAMPLE_FREQUENCIES)
def test_sample_prices_temporal_dtype(freq):
    df = sample_prices(freq)
    col = df.columns[0]
    dtype = df.schema[col]
    if freq == "daily":
        assert dtype == pl.Date
    else:
        # hourly / minute are tz-aware datetimes in the sample timezone.
        assert isinstance(dtype, pl.Datetime)
        assert dtype.time_zone == TIMEZONE


@pytest.mark.parametrize("freq", SAMPLE_FREQUENCIES)
def test_sample_prices_ohlcv_numeric(freq):
    df = sample_prices(freq)
    for col in OHLCV:
        assert df.schema[col].is_numeric(), f"{col} not numeric in {freq}"


def test_max_bars_returns_most_recent_rows():
    full = sample_prices("daily")
    tail = sample_prices("daily", max_bars=5)
    assert tail.height == 5
    assert tail.equals(full.tail(5))


def test_max_bars_zero_returns_all():
    full = sample_prices("daily")
    assert sample_prices("daily", max_bars=0).height == full.height


def test_unknown_freq_raises():
    with pytest.raises(ValueError, match="Unknown freq"):
        sample_prices("weekly")


def test_results_are_cached():
    # lru_cache returns the identical object for identical arguments.
    assert sample_prices("daily") is sample_prices("daily")


def test_sample_tickers_constant():
    assert len(SAMPLE_TICKERS) == 500
    assert SAMPLE_TICKERS[0] == "T001"
    assert SAMPLE_TICKERS[-1] == "T500"


def test_sample_dataset_stacks_tickers():
    base = sample_prices("daily", max_bars=10)
    ds = sample_dataset(3, freq="daily", max_bars=10)

    # ticker is the leading column (see sample_dataset).
    assert ds.columns == ["ticker"] + base.columns
    assert ds.height == 3 * base.height
    assert ds["ticker"].unique().sort().to_list() == ["T001", "T002", "T003"]


def test_sample_dataset_sorted_by_ticker_then_time():
    ds = sample_dataset(3, freq="daily", max_bars=10)
    time_col = ds.columns[1]  # "date"
    assert ds.equals(ds.sort("ticker", time_col))
