import polars as pl
import pytest

from helpers import assert_series_equal

from bartons.indicators import MOM


@pytest.mark.parametrize(
    ("values", "period", "expected"),
    [
        ([10.0, 11.0, 12.0, 9.0], 1, [None, 1.0, 1.0, -3.0]),
        ([10.0, 11.0, 12.0, 9.0], 2, [None, None, 2.0, -2.0]),
        ([10.0, None, 12.0, 9.0], 2, [None, None, 2.0, None]),
    ],
)
def test_mom_matches_difference(values, period, expected):
    frame = pl.DataFrame({"x": pl.Series(values, dtype=pl.Float64)})
    got = frame.select(MOM(period, src="x"))["mom"]
    assert_series_equal(got, pl.Series("mom", expected, dtype=pl.Float64))


def test_mom_defaults_to_close_and_supports_expression_first_form():
    frame = pl.DataFrame({"close": [10.0, 11.0, 12.0, 15.0]})
    default = frame.select(MOM(2))
    positional = frame.select(MOM(pl.col("close"), 2))
    keyword = frame.select(MOM(2, src=pl.col("close")))
    assert default.equals(positional)
    assert default.equals(keyword)


def test_mom_rejects_nonpositive_period():
    with pytest.raises(ValueError, match="period must be greater than zero"):
        MOM(0)
