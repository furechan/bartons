import math

import polars as pl
import pytest

from helpers import assert_series_equal

from bartons.indicators import CMF


def test_cmf_matches_native_rolling_formula():
    period = 3
    frame = pl.DataFrame(
        {
            "high": [10.0, 12.0, 11.0, 14.0, 13.0, 15.0],
            "low": [8.0, 9.0, 7.0, 10.0, 9.0, 11.0],
            "close": [9.5, 10.0, 8.0, 13.0, 11.0, 14.0],
            "volume": [100, 200, 150, 300, 250, 400],
        }
    )

    got = frame.select(CMF(period))["cmf"]
    multiplier = (
        (frame["close"] * 2.0 - frame["high"] - frame["low"])
        / (frame["high"] - frame["low"])
    )
    expected = (multiplier * frame["volume"]).rolling_sum(period) / frame[
        "volume"
    ].rolling_sum(period)
    assert_series_equal(
        got,
        expected.rename("cmf"),
        check_exact=False,
        rel_tol=1e-12,
    )


def test_cmf_accepts_custom_inputs_and_integer_volume():
    frame = pl.DataFrame(
        {
            "h": [2.0, 3.0, 4.0],
            "l": [0.0, 1.0, 2.0],
            "c": [1.0, 2.5, 3.0],
            "v": [10, 20, 30],
        }
    )
    got = frame.select(CMF(2, high="h", low="l", close="c", volume="v"))["cmf"]
    assert got.dtype == pl.Float64


def test_cmf_zero_range_propagates_nan():
    frame = pl.DataFrame(
        {
            "high": [1.0, 1.0],
            "low": [1.0, 1.0],
            "close": [1.0, 1.0],
            "volume": [10, 20],
        }
    )
    assert math.isnan(frame.select(CMF(2))["cmf"][-1])


@pytest.mark.parametrize("period", [0, -1])
def test_cmf_rejects_invalid_period(period):
    with pytest.raises(ValueError, match="period must be greater than zero"):
        CMF(period)
