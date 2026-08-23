import math

import polars as pl
import pytest

from helpers import assert_series_equal

from bartons import kernels
from bartons.indicators import MFI
from refimpl import ref_mfi


HIGHS = [10.0, 11.0, 12.0, 11.0, 13.0, None, 14.0, 15.0, 14.0, 16.0]
LOWS = [8.0, 9.0, 10.0, 9.0, 11.0, None, 12.0, 13.0, 12.0, 14.0]
CLOSES = [9.0, 10.0, 11.0, 10.0, 12.0, None, 13.0, 14.0, 13.0, 15.0]
VOLUMES = [100, 110, 120, 130, 140, 150, 160, None, 180, 190]
TYPICAL = [
    None if h is None or l is None or c is None else (h + l + c) / 3.0
    for h, l, c in zip(HIGHS, LOWS, CLOSES)
]


def test_mfi_expression_and_eager_match_reference():
    df = pl.DataFrame(
        {"high": HIGHS, "low": LOWS, "close": CLOSES, "volume": VOLUMES}
    )
    expression = df.select(MFI(3))["mfi"]
    eager = kernels.mfi(pl.Series(TYPICAL), df["volume"], period=3)
    expected = pl.Series("mfi", ref_mfi(TYPICAL, VOLUMES, 3))

    assert_series_equal(expression, expected, check_exact=False, rel_tol=1e-12)
    assert_series_equal(expression, eager)


def test_mfi_accepts_custom_inputs_and_integer_volume():
    df = pl.DataFrame(
        {
            "c": [1.0, 2.0, 3.0, 2.0],
            "v": [10, 20, 30, 40],
        }
    )
    got = df.select(MFI(2, src="c", volume="v"))["mfi"]
    expected = pl.Series("mfi", ref_mfi(df["c"], df["v"], 2))

    assert got.dtype == pl.Float64
    assert_series_equal(got, expected, check_exact=False, rel_tol=1e-12)


def test_flat_money_flow_is_nan():
    df = pl.DataFrame(
        {
            "high": [2.0] * 4,
            "low": [0.0] * 4,
            "close": [1.0] * 4,
            "volume": [10] * 4,
        }
    )
    got = df.select(MFI(2))["mfi"]

    assert math.isnan(got[-1])


@pytest.mark.parametrize("period", [0, -1])
def test_invalid_period_rejected(period):
    series = pl.Series("x", [1.0, 2.0])
    with pytest.raises(ValueError, match="period must be > 0"):
        kernels.mfi(series, series, period=period)


def test_eager_input_lengths_must_match():
    short = pl.Series("short", [1.0])
    long = pl.Series("long", [1.0, 2.0])
    with pytest.raises(ValueError, match="input lengths differ"):
        kernels.mfi(long, short, period=1)
