"""TYPPRICE is native polars composition with no kernel behind it — the single
definition of `(high + low + close) / 3`, shared with CCI's default src."""

import polars as pl
import pytest

from helpers import assert_series_equal

from bartons.indicators import TYPPRICE


HIGHS = [10.0, 12.0, None, 15.0, 16.0]
LOWS = [8.0, 9.0, None, 11.0, 12.0]
CLOSES = [9.0, 11.0, None, 14.0, 15.0]


def _df(highs=HIGHS, lows=LOWS, closes=CLOSES, names=("high", "low", "close")):
    high, low, close = names
    return pl.DataFrame(
        {
            high: pl.Series(highs, dtype=pl.Float64),
            low: pl.Series(lows, dtype=pl.Float64),
            close: pl.Series(closes, dtype=pl.Float64),
        }
    )


def _expected(highs=HIGHS, lows=LOWS, closes=CLOSES):
    return pl.Series(
        "typprice",
        [
            None if h is None or l is None or c is None else (h + l + c) / 3
            for h, l, c in zip(highs, lows, closes)
        ],
        dtype=pl.Float64,
    )


def test_typprice_defaults_to_hlc_columns():
    got = _df().select(TYPPRICE().alias("typprice"))["typprice"]
    assert_series_equal(got, _expected(), check_exact=False, rel_tol=1e-12)


def test_typprice_custom_column_names():
    frame = _df(names=("h", "l", "c"))
    got = frame.select(TYPPRICE(high="h", low="l", close="c").alias("typprice"))["typprice"]
    assert_series_equal(got, _expected(), check_exact=False, rel_tol=1e-12)


def test_typprice_accepts_expressions():
    frame = _df()
    names = frame.select(TYPPRICE().alias("typprice"))
    expressions = frame.select(
        TYPPRICE(
            high=pl.col("high"), low=pl.col("low"), close=pl.col("close")
        ).alias("typprice")
    )
    assert names.equals(expressions)


def test_null_in_any_input_propagates():
    """A missing bar yields null, which is what resets a downstream window."""
    got = _df().select(TYPPRICE().alias("typprice"))["typprice"]
    assert got[2] is None


def test_matches_eager_series_arithmetic():
    """The eager counterpart the kernel docstring points at gives the same values."""
    frame = _df()
    lazy = frame.select(TYPPRICE().alias("typprice"))["typprice"]
    eager = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    assert_series_equal(lazy, eager, check_names=False)


def test_integer_input_yields_float():
    frame = pl.DataFrame({"high": [10, 12], "low": [8, 9], "close": [9, 11]})
    got = frame.select(TYPPRICE().alias("typprice"))["typprice"]
    assert got.dtype == pl.Float64
    assert got.to_list() == pytest.approx([27 / 3, 32 / 3])
