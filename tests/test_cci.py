import polars as pl
import pytest

from helpers import assert_series_equal

from bartons import kernels
from bartons.indicators import CCI, TYPPRICE
from refimpl import ref_cci


HIGHS = [10.0, 12.0, 13.0, 15.0, 14.0, 17.0, 18.0]
LOWS = [8.0, 9.0, 10.0, 11.0, 11.0, 13.0, 15.0]
CLOSES = [9.0, 11.0, 12.0, 14.0, 12.0, 16.0, 17.0]

# (highs, lows, closes, period) — covers warmup and a mid-series missing bar,
# both when all three inputs are missing together and when only one is. period
# == 1 is degenerate for CCI and gets its own test below.
CASES = [
    (HIGHS, LOWS, CLOSES, 3),
    (
        [10.0, 12.0, None, 15.0, 16.0, 17.0],
        [8.0, 9.0, None, 11.0, 12.0, 13.0],
        [9.0, 11.0, None, 14.0, 15.0, 16.0],
        2,
    ),
    (
        [10.0, 12.0, 13.0, 15.0, 14.0],
        [8.0, 9.0, None, 11.0, 11.0],
        [9.0, 11.0, 12.0, 14.0, 12.0],
        2,
    ),
]


def expected_series(highs, lows, closes, period):
    return pl.Series("cci", ref_cci(highs, lows, closes, period), dtype=pl.Float64)


def _df(highs, lows, closes):
    return pl.DataFrame(
        {
            "high": pl.Series(highs, dtype=pl.Float64),
            "low": pl.Series(lows, dtype=pl.Float64),
            "close": pl.Series(closes, dtype=pl.Float64),
        }
    )


def _typical(df):
    """Typical price as an eager Series — the pyfunction's input."""
    return (df["high"] + df["low"] + df["close"]) / 3.0


@pytest.mark.parametrize("highs,lows,closes,period", CASES)
def test_cci_expression(highs, lows, closes, period):
    df = _df(highs, lows, closes)
    got = df.select(CCI(period).alias("cci"))["cci"]
    assert_series_equal(
        got, expected_series(highs, lows, closes, period), check_exact=False, rel_tol=1e-12
    )


@pytest.mark.parametrize("highs,lows,closes,period", CASES)
def test_cci_pyfunction(highs, lows, closes, period):
    """The kernel takes one series; the caller supplies typical price."""
    got = kernels.cci(_typical(_df(highs, lows, closes)), period=period)
    assert_series_equal(
        got, expected_series(highs, lows, closes, period),
        check_names=False, check_exact=False, rel_tol=1e-12,
    )


def test_pyfunction_matches_expression():
    """Both entry points share the cci kernel, so they must agree element-for-element."""
    highs, lows, closes, period = CASES[1]  # the null-reset case
    df = _df(highs, lows, closes)
    expr_out = df.select(CCI(period).alias("cci"))["cci"]
    func_out = kernels.cci(_typical(df), period=period)
    assert_series_equal(expr_out, func_out, check_names=False)


def test_cci_default_src_is_typical_price():
    """`CCI(n)` is exactly `CCI(n, src=TYPPRICE())` — no separate reduction."""
    df = _df(HIGHS, LOWS, CLOSES)
    default = df.select(CCI(3).alias("cci"))["cci"]
    explicit = df.select(CCI(3, src=TYPPRICE()).alias("cci"))["cci"]
    assert_series_equal(default, explicit)


def test_cci_custom_column_names():
    highs = [10.0, 12.0, None, 15.0, 16.0, 17.0]
    lows = [8.0, 9.0, None, 11.0, 12.0, 13.0]
    closes = [9.0, 11.0, None, 14.0, 15.0, 16.0]
    frame = pl.DataFrame({"h": highs, "l": lows, "c": closes})

    src = TYPPRICE(high="h", low="l", close="c")
    got = frame.select(CCI(2, src=src).alias("cci"))["cci"]
    assert_series_equal(
        got, expected_series(highs, lows, closes, 2), check_exact=False, rel_tol=1e-12
    )


def test_cci_runs_over_any_series():
    """Nothing in the kernel is specific to typical price."""
    df = pl.DataFrame({"close": pl.Series(CLOSES, dtype=pl.Float64)})
    got = df.select(CCI(3, src=pl.col("close")).alias("cci"))["cci"]
    expected = kernels.cci(df["close"], period=3)
    assert_series_equal(got, expected, check_names=False)


def test_cci_pipes():
    """CCI is a single-source factory, so it composes with Expr.pipe."""
    df = _df(HIGHS, LOWS, CLOSES)
    piped = df.select(TYPPRICE().pipe(CCI, 3).alias("cci"))["cci"]
    kwarg = df.select(CCI(3, src=TYPPRICE()).alias("cci"))["cci"]
    assert_series_equal(piped, kwarg)


def test_cci_flat_window_is_nan():
    """A flat window has zero deviation, so CCI is 0/0 — NaN, not null."""
    df = _df([5.0, 5.0, 5.0, 5.0], [5.0, 5.0, 5.0, 5.0], [5.0, 5.0, 5.0, 5.0])
    got = df.select(CCI(2).alias("cci"))["cci"]
    assert got.to_list()[0] is None
    assert all(value != value for value in got.to_list()[1:])


def test_cci_period_one_is_all_nan():
    """A one-bar window has zero deviation, so every post-warmup row is 0/0."""
    df = _df([10.0, 12.0, 13.0, 15.0], [8.0, 9.0, 10.0, 11.0], [9.0, 11.0, 12.0, 14.0])
    got = df.select(CCI(1).alias("cci"))["cci"].to_list()
    expected = ref_cci(
        [10.0, 12.0, 13.0, 15.0], [8.0, 9.0, 10.0, 11.0], [9.0, 11.0, 12.0, 14.0], 1
    )
    # All NaN, so compared by NaN-ness: the tolerance helper cannot equate NaNs.
    assert all(value != value for value in got)
    assert all(value != value for value in expected)


def test_integer_input_is_cast():
    """Non-f64 input is cast to Float64 rather than panicking."""
    series = pl.Series("x", [9, 11, 12, 14], dtype=pl.Int64)
    got = kernels.cci(series, period=2)
    assert got.dtype == pl.Float64


def test_cci_rejects_invalid_period():
    frame = pl.DataFrame({"high": HIGHS, "low": LOWS, "close": CLOSES})
    with pytest.raises(pl.exceptions.PolarsError):
        frame.select(CCI(0))


def test_invalid_period_pyfunction():
    series = pl.Series("x", [9.0, 11.0, 12.0], dtype=pl.Float64)
    with pytest.raises(ValueError, match="period must be > 0"):
        kernels.cci(series, period=0)
