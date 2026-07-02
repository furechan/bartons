import polars as pl
import pytest
from helpers import assert_series_equal

from bartons import plugin
from bartons.expressions import TRANGE
from refimpl import ref_trange


# (highs, lows, closes)
CASES = [
    ([10.0, 12.0, 11.0, 13.0], [8.0, 9.0, 9.0, 10.0], [9.0, 11.0, 10.0, 12.0]),
    ([5.0, 5.0, 5.0], [5.0, 5.0, 5.0], [5.0, 5.0, 5.0]),  # flat -> all zero
    ([10.0, None, 11.0, 13.0], [8.0, 9.0, None, 10.0], [9.0, 11.0, 10.0, 12.0]),  # nulls
]


def expected_series(highs, lows, closes):
    return pl.Series("trange", ref_trange(highs, lows, closes), dtype=pl.Float64)


def _df(highs, lows, closes):
    return pl.DataFrame(
        {
            "high": pl.Series(highs, dtype=pl.Float64),
            "low": pl.Series(lows, dtype=pl.Float64),
            "close": pl.Series(closes, dtype=pl.Float64),
        }
    )


@pytest.mark.parametrize("highs,lows,closes", CASES)
def test_trange_expression(highs, lows, closes):
    df = _df(highs, lows, closes)
    got = df.select(TRANGE().alias("trange"))["trange"]
    assert_series_equal(got, expected_series(highs, lows, closes), check_exact=False, rel_tol=1e-12)


def test_trange_accepts_column_names_and_exprs():
    """Custom column names and explicit expressions both work as inputs."""
    df = pl.DataFrame(
        {
            "h": pl.Series([10.0, 12.0, 11.0], dtype=pl.Float64),
            "l": pl.Series([8.0, 9.0, 9.0], dtype=pl.Float64),
            "c": pl.Series([9.0, 11.0, 10.0], dtype=pl.Float64),
        }
    )
    by_name = df.select(TRANGE("h", "l", "c").alias("trange"))["trange"]
    by_expr = df.select(
        TRANGE(pl.col("h"), pl.col("l"), pl.col("c")).alias("trange")
    )["trange"]
    expected = expected_series([10.0, 12.0, 11.0], [8.0, 9.0, 9.0], [9.0, 11.0, 10.0])
    assert_series_equal(by_name, expected, check_exact=False, rel_tol=1e-12)
    assert_series_equal(by_expr, expected, check_exact=False, rel_tol=1e-12)


@pytest.mark.parametrize("highs,lows,closes", CASES)
def test_trange_pyfunction(highs, lows, closes):
    h = pl.Series("high", highs, dtype=pl.Float64)
    l = pl.Series("low", lows, dtype=pl.Float64)
    c = pl.Series("close", closes, dtype=pl.Float64)
    got = plugin.trange(h, l, c)
    assert_series_equal(
        got, expected_series(highs, lows, closes), check_names=False, check_exact=False, rel_tol=1e-12
    )


def test_pyfunction_matches_expression():
    highs, lows, closes = CASES[0]
    df = _df(highs, lows, closes)
    expr_out = df.select(TRANGE().alias("trange"))["trange"]
    func_out = plugin.trange(df["high"], df["low"], df["close"])
    assert_series_equal(expr_out, func_out, check_names=False)


def test_integer_input_is_cast():
    """Non-f64 input is cast to Float64 rather than panicking."""
    h = pl.Series("high", [10, 12, 11], dtype=pl.Int64)
    l = pl.Series("low", [8, 9, 9], dtype=pl.Int64)
    c = pl.Series("close", [9, 11, 10], dtype=pl.Int64)
    got = plugin.trange(h, l, c)
    assert got.dtype == pl.Float64
    assert_series_equal(
        got,
        expected_series([10.0, 12.0, 11.0], [8.0, 9.0, 9.0], [9.0, 11.0, 10.0]),
        check_names=False, check_exact=False, rel_tol=1e-12,
    )
