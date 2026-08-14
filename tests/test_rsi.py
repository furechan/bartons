import polars as pl
import pytest
from helpers import assert_series_equal

from bartons import plugin
from bartons.indicators import RSI
from refimpl import ref_rsi


# (values, period) — covers warmup nulls (delta + average), a steady uptrend
# (RSI 100), an oscillating series, a mid-series null (skipped: averages and prev
# carry across the gap), a flat series (RSI 0), and period == 1.
CASES = [
    ([1.0, 2.0, 3.0, 4.0, 5.0], 2),
    ([10.0, 11.0, 10.0, 11.0, 10.0, 11.0], 2),
    ([10.0, 11.0, None, 20.0, 21.0, 22.0], 2),
    ([5.0, 5.0, 5.0, 5.0, 5.0], 2),
    ([None, None, 1.0, 2.0, 3.0], 1),
]


def expected_series(xs, period):
    return pl.Series("rsi", ref_rsi(xs, period), dtype=pl.Float64)


@pytest.mark.parametrize("xs,period", CASES)
def test_rsi_expression(xs, period):
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = df.select(RSI(period, src=pl.col("x")).alias("rsi"))["rsi"]
    assert_series_equal(got, expected_series(xs, period), check_exact=False, rel_tol=1e-12)


def test_rsi_flat_series_is_zero():
    """A dead-flat run has no gains or losses; RSI is 0 (matching TA-Lib)."""
    xs = [5.0, 5.0, 5.0, 5.0]
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = df.select(RSI(2, src=pl.col("x")).alias("rsi"))["rsi"]
    assert got.to_list() == [None, None, 0.0, 0.0]


def test_rsi_steady_uptrend_is_hundred():
    """All gains, no losses; RSI saturates at 100."""
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = df.select(RSI(2, src=pl.col("x")).alias("rsi"))["rsi"]
    assert got.to_list() == [None, None, 100.0, 100.0, 100.0]


def test_rsi_src_defaults_to_close():
    """src=None reads the `close` column by convention."""
    xs = [10.0, 11.0, 10.0, 11.0, 10.0, 11.0]
    df = pl.DataFrame({"close": pl.Series(xs, dtype=pl.Float64)})
    got = df.select(RSI(2).alias("rsi"))["rsi"]
    assert_series_equal(got, expected_series(xs, 2), check_exact=False, rel_tol=1e-12)


def test_rsi_src_accepts_column_name():
    """A bare column-name string works as src."""
    xs = [10.0, 11.0, 10.0, 11.0, 10.0, 11.0]
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = df.select(RSI(2, src="x").alias("rsi"))["rsi"]
    assert_series_equal(got, expected_series(xs, 2), check_exact=False, rel_tol=1e-12)


@pytest.mark.parametrize("xs,period", CASES)
def test_rsi_pyfunction(xs, period):
    s = pl.Series("x", xs, dtype=pl.Float64)
    got = plugin.rsi(s, period=period)
    assert_series_equal(
        got, expected_series(xs, period), check_names=False, check_exact=False, rel_tol=1e-12
    )


def test_pyfunction_matches_expression():
    """Both entry points share calc_rsi, so they must agree element-for-element."""
    xs = [10.0, 11.0, None, 20.0, 21.0, 22.0]
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    expr_out = df.select(RSI(3, src=pl.col("x")).alias("rsi"))["rsi"]
    func_out = plugin.rsi(df["x"], period=3)
    assert_series_equal(expr_out, func_out, check_names=False)


def test_integer_input_is_cast():
    """Non-f64 input is cast to Float64 rather than panicking."""
    s = pl.Series("x", [1, 2, 3, 4], dtype=pl.Int64)
    got = plugin.rsi(s, period=2)
    assert got.dtype == pl.Float64
    assert_series_equal(
        got, expected_series([1.0, 2.0, 3.0, 4.0], 2), check_names=False, check_exact=False, rel_tol=1e-12
    )


def test_invalid_period_expression():
    df = pl.DataFrame({"x": pl.Series([1.0, 2.0, 3.0], dtype=pl.Float64)})
    with pytest.raises(pl.exceptions.PolarsError):
        df.select(RSI(0, src=pl.col("x")).alias("rsi"))


def test_invalid_period_pyfunction():
    s = pl.Series("x", [1.0, 2.0, 3.0], dtype=pl.Float64)
    with pytest.raises(Exception):
        plugin.rsi(s, period=0)
