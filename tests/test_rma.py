import polars as pl
import pytest
from helpers import assert_series_equal

from bartons import plugin
from bartons.indicators import RMA
from refimpl import ref_rma


# (values, period) — covers warmup nulls, a mid-series null (skipped: the RMA
# carries across the gap), leading nulls, a flat series, and period == 1.
CASES = [
    ([100.0, 101.0, 102.0], 2),
    ([1.0, 2.0, 3.0, 4.0, 5.0], 2),
    ([10.0, 11.0, None, 20.0, 21.0, 22.0], 2),
    ([5.0, 5.0, 5.0, 5.0], 3),
    ([None, None, 1.0, 2.0, 3.0], 1),
]


def expected_series(xs, period):
    return pl.Series("rma", ref_rma(xs, period), dtype=pl.Float64)


@pytest.mark.parametrize("xs,period", CASES)
def test_rma_expression(xs, period):
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = df.select(RMA(period, src=pl.col("x")).alias("rma"))["rma"]
    assert_series_equal(got, expected_series(xs, period), check_exact=False, rel_tol=1e-12)


def test_rma_src_defaults_to_close():
    """src=None reads the `close` column by convention."""
    df = pl.DataFrame({"close": pl.Series([100.0, 101.0, 102.0], dtype=pl.Float64)})
    got = df.select(RMA(2).alias("rma"))["rma"]
    assert_series_equal(
        got, expected_series([100.0, 101.0, 102.0], 2), check_exact=False, rel_tol=1e-12
    )


def test_rma_src_accepts_column_name():
    """A bare column-name string works as src."""
    df = pl.DataFrame({"x": pl.Series([100.0, 101.0, 102.0], dtype=pl.Float64)})
    got = df.select(RMA(2, src="x").alias("rma"))["rma"]
    assert_series_equal(
        got, expected_series([100.0, 101.0, 102.0], 2), check_exact=False, rel_tol=1e-12
    )


@pytest.mark.parametrize("xs,period", CASES)
def test_rma_pyfunction(xs, period):
    s = pl.Series("x", xs, dtype=pl.Float64)
    got = plugin.rma(s, period=period)
    assert_series_equal(
        got, expected_series(xs, period), check_names=False, check_exact=False, rel_tol=1e-12
    )


def test_pyfunction_matches_expression():
    """Both entry points share calc_rma, so they must agree element-for-element."""
    xs = [10.0, 11.0, None, 20.0, 21.0, 22.0]
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    expr_out = df.select(RMA(3, src=pl.col("x")).alias("rma"))["rma"]
    func_out = plugin.rma(df["x"], period=3)
    assert_series_equal(expr_out, func_out, check_names=False)


def test_integer_input_is_cast():
    """Non-f64 input is cast to Float64 rather than panicking."""
    s = pl.Series("x", [1, 2, 3, 4], dtype=pl.Int64)
    got = plugin.rma(s, period=2)
    assert got.dtype == pl.Float64
    assert_series_equal(
        got, expected_series([1.0, 2.0, 3.0, 4.0], 2), check_names=False, check_exact=False, rel_tol=1e-12
    )


def test_invalid_period_expression():
    df = pl.DataFrame({"x": pl.Series([1.0, 2.0, 3.0], dtype=pl.Float64)})
    with pytest.raises(pl.exceptions.PolarsError):
        df.select(RMA(0, src=pl.col("x")).alias("rma"))


def test_invalid_period_pyfunction():
    s = pl.Series("x", [1.0, 2.0, 3.0], dtype=pl.Float64)
    with pytest.raises(ValueError, match="period must be > 0"):
        plugin.rma(s, period=0)
