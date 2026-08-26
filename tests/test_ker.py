import polars as pl
import pytest
from helpers import assert_series_equal

from bartons import kernels
from bartons.indicators import KER
from refimpl import ref_ker


# (values, period) — covers warmup nulls, a perfect trend (ratio 1), chop
# (ratio < 1), a mid-series null (window and prev both reset), leading nulls,
# a flat series (zero path length), and period == 1.
CASES = [
    ([100.0, 101.0, 102.0], 2),
    ([1.0, 2.0, 3.0, 4.0, 5.0], 2),
    ([1.0, 3.0, 2.0, 4.0, 3.0, 5.0], 3),
    ([10.0, 11.0, None, 20.0, 21.0, 22.0], 2),
    ([5.0, 5.0, 5.0, 5.0], 3),
    ([None, None, 1.0, 2.0, 3.0], 1),
]


def expected_series(xs, period):
    return pl.Series("ker", ref_ker(xs, period), dtype=pl.Float64)


@pytest.mark.parametrize("xs,period", CASES)
def test_ker_expression(xs, period):
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = df.select(KER(period, src=pl.col("x")).alias("ker"))["ker"]
    assert_series_equal(got, expected_series(xs, period), check_exact=False, rel_tol=1e-12)


def test_ker_src_defaults_to_close():
    """The default src reads the `close` column by convention."""
    df = pl.DataFrame({"close": pl.Series([1.0, 2.0, 3.0, 4.0], dtype=pl.Float64)})
    got = df.select(KER(2).alias("ker"))["ker"]
    assert_series_equal(
        got, expected_series([1.0, 2.0, 3.0, 4.0], 2), check_exact=False, rel_tol=1e-12
    )


def test_ker_src_accepts_column_name():
    """A bare column-name string works as src."""
    df = pl.DataFrame({"x": pl.Series([1.0, 2.0, 3.0, 4.0], dtype=pl.Float64)})
    got = df.select(KER(2, src="x").alias("ker"))["ker"]
    assert_series_equal(
        got, expected_series([1.0, 2.0, 3.0, 4.0], 2), check_exact=False, rel_tol=1e-12
    )


@pytest.mark.parametrize("xs,period", CASES)
def test_ker_pyfunction(xs, period):
    s = pl.Series("x", xs, dtype=pl.Float64)
    got = kernels.ker(s, period=period)
    assert_series_equal(
        got, expected_series(xs, period), check_names=False, check_exact=False, rel_tol=1e-12
    )


def test_pyfunction_matches_expression():
    """Both entry points share the same kernel, so they must agree
    element-for-element."""
    xs = [10.0, 11.0, None, 20.0, 21.0, 22.0]
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    expr_out = df.select(KER(3, src=pl.col("x")).alias("ker"))["ker"]
    func_out = kernels.ker(df["x"], period=3)
    assert_series_equal(expr_out, func_out, check_names=False)


def _native_ker(src: pl.Expr, period: int) -> pl.Expr:
    """KER spelled with native polars rolling expressions.

    Deliberately not the kernel's algorithm: the running sums here telescope
    over `diff()` rather than reading the window's endpoints, and polars decides
    the null propagation on its own.
    """
    changes = src.diff()
    direction = changes.rolling_sum(period, min_samples=period).abs()
    volatility = changes.abs().rolling_sum(period, min_samples=period)
    return pl.when(volatility == 0).then(1.0).otherwise(direction / volatility)


@pytest.mark.parametrize("xs,period", CASES)
def test_ker_matches_native_polars(xs, period):
    """The kernel's null convention is pinned to the native polars spelling.

    KER is windowed, so a null resets it — unlike mintalib and bearta, which
    carry the previous value across a gap and let the window span it. Resetting
    is what makes the kernel and `diff().rolling_sum(...)` agree row for row,
    including which rows are null, which is what lets `KER()` and the ratio
    inside `KAMA()` be the same definition rather than two that drift.
    """
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = df.select(KER(period, src=pl.col("x")).alias("ker"))["ker"]
    native = df.select(_native_ker(pl.col("x"), period).alias("ker"))["ker"]
    assert_series_equal(got, native, check_exact=False, rel_tol=1e-12)


def test_ker_is_bounded_by_zero_and_one():
    """The absolute definition keeps the ratio in 0..=1 — the property KAMA's
    smoothing constant relies on."""
    df = pl.DataFrame({"x": pl.Series([1.0, 3.0, 2.0, 5.0, 1.0, 4.0, 2.0, 6.0])})
    got = df.select(KER(3, src=pl.col("x")).alias("ker"))["ker"]
    values = [v for v in got.to_list() if v is not None]
    assert values, "expected at least one non-null ratio"
    assert all(0.0 <= v <= 1.0 for v in values), values


def test_integer_input_is_cast():
    """Non-f64 input is cast to Float64 rather than panicking."""
    s = pl.Series("x", [1, 2, 3, 4], dtype=pl.Int64)
    got = kernels.ker(s, period=2)
    assert got.dtype == pl.Float64
    assert_series_equal(
        got,
        expected_series([1.0, 2.0, 3.0, 4.0], 2),
        check_names=False,
        check_exact=False,
        rel_tol=1e-12,
    )


def test_invalid_period_expression():
    df = pl.DataFrame({"x": pl.Series([1.0, 2.0, 3.0], dtype=pl.Float64)})
    with pytest.raises(pl.exceptions.PolarsError):
        df.select(KER(0, src=pl.col("x")).alias("ker"))


def test_invalid_period_pyfunction():
    s = pl.Series("x", [1.0, 2.0, 3.0], dtype=pl.Float64)
    with pytest.raises(ValueError, match="period must be > 0"):
        kernels.ker(s, period=0)
