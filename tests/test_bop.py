import math

import polars as pl

from helpers import assert_series_equal

from bartons.indicators import BOP, SMA


def test_bop_matches_unsmoothed_per_bar_formula():
    frame = pl.DataFrame(
        {
            "open": [9.0, 10.0, 12.0, 11.0],
            "high": [11.0, 13.0, 14.0, 15.0],
            "low": [8.0, 9.0, 10.0, 10.0],
            "close": [10.0, 12.0, 11.0, 14.0],
        }
    )

    got = frame.select(BOP())["bop"]
    expected = (
        (frame["close"] - frame["open"]) / (frame["high"] - frame["low"])
    ).rename("bop")
    assert_series_equal(got, expected)


def test_bop_accepts_custom_integer_inputs():
    frame = pl.DataFrame({"o": [1, 2], "h": [4, 5], "l": [0, 1], "c": [3, 1]})
    got = frame.select(BOP(open="o", high="h", low="l", close="c"))["bop"]
    assert got.dtype == pl.Float64
    assert_series_equal(got, pl.Series("bop", [0.5, -0.25]))


def test_bop_leaves_smoothing_to_composition():
    frame = pl.DataFrame(
        {
            "open": [1.0, 2.0, 1.0],
            "high": [3.0, 4.0, 3.0],
            "low": [0.0, 1.0, 0.0],
            "close": [2.0, 1.0, 3.0],
        }
    )
    explicit = frame.select(SMA(2, src=BOP()))["sma"]
    expected = frame.select(BOP())["bop"].rolling_mean(2).rename("sma")
    assert_series_equal(explicit, expected)


def test_bop_zero_range_is_nan():
    frame = pl.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]})
    assert math.isnan(frame.select(BOP())["bop"][0])
