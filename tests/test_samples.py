import polars as pl
import pytest

from bartons.samples import (
    SAMPLE_FREQUENCIES,
    SAMPLE_TICKERS,
    TIMEZONE,
    random_prices,
    sample_dataset,
    sample_prices,
    with_n_chunks,
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


@pytest.mark.parametrize("freq", SAMPLE_FREQUENCIES)
def test_sample_prices_is_contiguous(freq):
    assert {series.n_chunks() for series in sample_prices(freq)} == {1}


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


def test_random_prices_is_deterministic_and_has_valid_ohlc():
    left = random_prices(100, seed=42)
    right = random_prices(100, seed=42)

    assert left.equals(right)
    assert left.columns == ["date"] + OHLCV
    assert left.select((pl.col("high") >= pl.max_horizontal("open", "close")).all()).item()
    assert left.select((pl.col("low") <= pl.min_horizontal("open", "close")).all()).item()


@pytest.mark.parametrize("n_chunks", [1, 2, 7, 100])
def test_random_prices_has_exact_chunk_count(n_chunks):
    df = random_prices(100, n_chunks=n_chunks)
    assert {series.n_chunks() for series in df} == {n_chunks}


def test_with_n_chunks_replaces_existing_layout():
    original = random_prices(100, n_chunks=7)
    fragmented = with_n_chunks(original, 3)
    contiguous = with_n_chunks(fragmented, 1)

    assert {series.n_chunks() for series in fragmented} == {3}
    assert {series.n_chunks() for series in contiguous} == {1}
    assert original.equals(fragmented)
    assert original.equals(contiguous)


def test_random_prices_multiple_tickers_and_first_null():
    df = random_prices(10, n_tickers=3, n_chunks=6, null_first=True)

    assert df.height == 30
    assert df.columns == ["ticker", "date"] + OHLCV
    assert df["ticker"].unique(maintain_order=True).to_list() == ["T001", "T002", "T003"]
    assert df.group_by("ticker", maintain_order=True).agg(pl.col("close").first().is_null())["close"].to_list() == [True] * 3
    assert {series.n_chunks() for series in df} == {6}


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"n_rows": 0}, "n_rows"),
        ({"n_tickers": 0}, "n_tickers"),
        ({"n_rows": 2, "n_chunks": 3}, "n_chunks"),
    ],
)
def test_random_prices_rejects_invalid_shape(kwargs, message):
    with pytest.raises(ValueError, match=message):
        random_prices(**kwargs)
