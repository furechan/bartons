import polars as pl
import pytest

from helpers import assert_series_equal

from bartons.indicators import WILLR


PRICES = {
    "high": [12.0, 13.0, 15.0, 14.0, 16.0, 18.0, 17.0, 20.0],
    "low": [9.0, 10.0, 11.0, 10.0, 12.0, 13.0, 12.0, 15.0],
    "close": [11.0, 12.0, 14.0, 11.0, 15.0, 17.0, 13.0, 19.0],
}


def ref_willr(highs, lows, closes, period):
    result = []
    for index, close in enumerate(closes):
        start = index + 1 - period
        window_highs = highs[max(start, 0) : index + 1]
        window_lows = lows[max(start, 0) : index + 1]
        if start < 0 or any(value is None for value in window_highs + window_lows):
            result.append(None)
            continue
        highest = max(window_highs)
        lowest = min(window_lows)
        result.append(100.0 * (close - highest) / (highest - lowest))
    return result


def test_willr_matches_reference():
    frame = pl.DataFrame(PRICES)
    got = frame.select(WILLR(4))["willr"]
    expected = pl.Series(
        "willr",
        ref_willr(
            **{f"{key}s": value for key, value in PRICES.items()}, period=4
        ),
    )
    assert_series_equal(got, expected, check_exact=False, rel_tol=1e-12)


def test_willr_accepts_custom_expressions():
    frame = pl.DataFrame({f"x_{name}": values for name, values in PRICES.items()})
    got = frame.select(
        WILLR(4, high="x_high", low="x_low", close=pl.col("x_close"))
    )
    expected = frame.rename(
        {"x_high": "high", "x_low": "low", "x_close": "close"}
    ).select(WILLR(4))
    assert got.equals(expected)


def test_willr_rejects_invalid_period():
    with pytest.raises(ValueError, match="period must be greater than zero"):
        WILLR(0)
