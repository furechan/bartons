import polars as pl
import pytest
from helpers import assert_series_equal

from bartons import plugin
from bartons.expressions import EMA
from refimpl import ref_ema


# (values, period) — covers warmup nulls, a mid-series null (skipped: the EMA
# carries across the gap), leading nulls, a flat series, and period == 1.
CASES = [
    ([100.0, 101.0, 102.0], 2),
    ([1.0, 2.0, 3.0, 4.0, 5.0], 2),
    ([10.0, 11.0, None, 20.0, 21.0, 22.0], 2),
    ([5.0, 5.0, 5.0, 5.0], 3),
    ([None, None, 1.0, 2.0, 3.0], 1),
]


def expected_series(xs, period):
    return pl.Series("ema", ref_ema(xs, period), dtype=pl.Float64)


@pytest.mark.parametrize("xs,period", CASES)
def test_ema_expression(xs, period):
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = df.select(EMA(period, src=pl.col("x")).alias("ema"))["ema"]
    assert_series_equal(got, expected_series(xs, period), check_exact=False, rel_tol=1e-12)


def test_ema_src_defaults_to_close():
    """src=None reads the `close` column by convention."""
    df = pl.DataFrame({"close": pl.Series([100.0, 101.0, 102.0], dtype=pl.Float64)})
    got = df.select(EMA(2).alias("ema"))["ema"]
    assert_series_equal(
        got, expected_series([100.0, 101.0, 102.0], 2), check_exact=False, rel_tol=1e-12
    )


def test_ema_src_accepts_column_name():
    """A bare column-name string works as src."""
    df = pl.DataFrame({"x": pl.Series([100.0, 101.0, 102.0], dtype=pl.Float64)})
    got = df.select(EMA(2, src="x").alias("ema"))["ema"]
    assert_series_equal(
        got, expected_series([100.0, 101.0, 102.0], 2), check_exact=False, rel_tol=1e-12
    )


@pytest.mark.parametrize("xs,period", CASES)
def test_ema_namespace(xs, period):
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = df.select(pl.col("x").bt.ema(period=period).alias("ema"))["ema"]
    assert_series_equal(got, expected_series(xs, period), check_exact=False, rel_tol=1e-12)


@pytest.mark.parametrize("xs,period", CASES)
def test_ema_pyfunction(xs, period):
    s = pl.Series("x", xs, dtype=pl.Float64)
    got = plugin.ema(s, period=period)
    assert_series_equal(
        got, expected_series(xs, period), check_names=False, check_exact=False, rel_tol=1e-12
    )


def test_pyfunction_matches_expression():
    """Both entry points share calc_ema, so they must agree element-for-element."""
    xs = [10.0, 11.0, None, 20.0, 21.0, 22.0]
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    expr_out = df.select(EMA(3, src=pl.col("x")).alias("ema"))["ema"]
    func_out = plugin.ema(df["x"], period=3)
    assert_series_equal(expr_out, func_out, check_names=False)


def test_integer_input_is_cast():
    """Non-f64 input is cast to Float64 rather than panicking."""
    s = pl.Series("x", [1, 2, 3, 4], dtype=pl.Int64)
    got = plugin.ema(s, period=2)
    assert got.dtype == pl.Float64
    assert_series_equal(
        got, expected_series([1.0, 2.0, 3.0, 4.0], 2), check_names=False, check_exact=False, rel_tol=1e-12
    )


def test_invalid_period_expression():
    df = pl.DataFrame({"x": pl.Series([1.0, 2.0, 3.0], dtype=pl.Float64)})
    with pytest.raises(pl.exceptions.PolarsError):
        df.select(EMA(0, src=pl.col("x")).alias("ema"))


def test_invalid_period_pyfunction():
    s = pl.Series("x", [1.0, 2.0, 3.0], dtype=pl.Float64)
    with pytest.raises(Exception):
        plugin.ema(s, period=0)
