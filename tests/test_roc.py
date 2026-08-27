import math

import polars as pl
import pytest

from helpers import assert_series_equal

from bartons.indicators import LROC, ROC, ROCP
from refimpl import ref_roc


@pytest.mark.parametrize(
    ("xs", "period"),
    [
        ([10.0, 11.0, 12.0, 9.0, 18.0], 1),
        ([10.0, 11.0, 12.0, 9.0, 18.0], 3),
        ([10.0, 11.0, None, 9.0, 18.0, 21.0], 2),
    ],
)
def test_roc_matches_reference(xs, period):
    frame = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = frame.select(ROC(period, src="x"))["roc"]
    expected = pl.Series(
        "roc",
        [None if value is None else 100.0 * value for value in ref_roc(xs, period)],
        dtype=pl.Float64,
    )
    assert_series_equal(got, expected, check_exact=False, rel_tol=1e-12)


def test_roc_defaults_to_close_and_supports_expression_first_form():
    frame = pl.DataFrame({"close": [10.0, 11.0, 12.0, 15.0]})
    default = frame.select(ROC(2))
    positional = frame.select(ROC(pl.col("close"), 2))
    keyword = frame.select(ROC(2, src=pl.col("close")))
    assert default.equals(positional)
    assert default.equals(keyword)


def test_roc_zero_denominator_follows_float_arithmetic():
    got = pl.DataFrame({"close": [0.0, 1.0, 0.0]}).select(ROC())["roc"]
    assert math.isinf(got[1])
    assert got[2] == -100.0


def test_rocp_preserves_unscaled_fractional_rate_of_change():
    frame = pl.DataFrame({"close": [10.0, 11.0, 12.0, 9.0]})
    got = frame.select(ROCP())
    expected = pl.DataFrame({"rocp": [None, 0.1, 1.0 / 11.0, -0.25]})
    assert got.equals(expected)


def test_lroc_returns_unscaled_logarithmic_rate_of_change():
    frame = pl.DataFrame({"close": [10.0, 11.0, 12.0, 9.0]})
    got = frame.select(LROC())
    expected = pl.DataFrame(
        {
            "lroc": [
                None,
                math.log(11.0) - math.log(10.0),
                math.log(12.0) - math.log(11.0),
                math.log(9.0) - math.log(12.0),
            ]
        }
    )
    assert_series_equal(
        got["lroc"], expected["lroc"], check_exact=False, rel_tol=1e-12
    )


@pytest.mark.parametrize("indicator", [ROC, ROCP, LROC])
def test_rate_of_change_rejects_nonpositive_period(indicator):
    with pytest.raises(ValueError, match="period"):
        indicator(0)
    with pytest.raises(ValueError, match="period"):
        indicator(-1)
