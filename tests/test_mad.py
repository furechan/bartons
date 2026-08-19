import polars as pl
import pytest

from helpers import assert_series_equal

from bartons import kernels
from bartons.indicators import MAD
from refimpl import ref_mad


CASES = [
    ([1.0, 2.0, 3.0, 4.0, 5.0], 3),
    ([10.0, 11.0, None, 20.0, 21.0, 22.0], 2),
    ([5.0, 5.0, 5.0, 5.0], 3),
    ([None, 1.0, 3.0], 1),
]


def expected_series(xs, period):
    return pl.Series("mad", ref_mad(xs, period), dtype=pl.Float64)


@pytest.mark.parametrize("xs,period", CASES)
def test_mad_expression(xs, period):
    frame = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = frame.select(MAD(period, src="x").alias("mad"))["mad"]
    assert_series_equal(got, expected_series(xs, period), check_exact=False, rel_tol=1e-12)


@pytest.mark.parametrize("xs,period", CASES)
def test_mad_eager(xs, period):
    got = kernels.mad(pl.Series("x", xs, dtype=pl.Float64), period=period)
    assert_series_equal(
        got,
        expected_series(xs, period),
        check_names=False,
        check_exact=False,
        rel_tol=1e-12,
    )


def test_mad_defaults_to_close():
    frame = pl.DataFrame({"close": [1.0, 2.0, 3.0]})
    assert frame.select(MAD(2)).columns == ["close"]


@pytest.mark.parametrize("period", [0, -1])
def test_mad_rejects_invalid_period(period):
    series = pl.Series("x", [1.0, 2.0])
    with pytest.raises(ValueError, match="period must be > 0"):
        kernels.mad(series, period=period)
