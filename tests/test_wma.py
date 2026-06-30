import polars as pl
import pytest
from helpers import assert_series_equal

from bartons import plugin
from bartons.wma import WMA


def ref_wma(xs, period):
    """Independent oracle: weighted mean of the last `period` values (oldest
    weight 1 .. newest weight `period`); null during warmup, reset on a null.
    Computed directly (not incrementally) to catch kernel bugs."""
    wdiv = period * (period + 1) / 2
    out = []
    window = []
    for x in xs:
        if x is None:
            window = []
            out.append(None)
            continue
        window.append(x)
        if len(window) > period:
            window.pop(0)
        if len(window) == period:
            wsum = sum((i + 1) * window[i] for i in range(period))
            out.append(wsum / wdiv)
        else:
            out.append(None)
    return out


# (values, period) — covers warmup nulls, a mid-series null reset + re-warmup,
# leading nulls, a flat series, and period == 1.
CASES = [
    ([100.0, 101.0, 102.0], 2),
    ([1.0, 2.0, 3.0, 4.0, 5.0], 2),
    ([10.0, 11.0, None, 20.0, 21.0, 22.0], 2),
    ([5.0, 5.0, 5.0, 5.0], 3),
    ([None, None, 1.0, 2.0, 3.0], 1),
]


def expected_series(xs, period):
    return pl.Series("wma", ref_wma(xs, period), dtype=pl.Float64)


@pytest.mark.parametrize("xs,period", CASES)
def test_wma_expression(xs, period):
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = df.select(WMA(period, src=pl.col("x")).alias("wma"))["wma"]
    assert_series_equal(got, expected_series(xs, period), check_exact=False, rel_tol=1e-12)


def test_wma_src_defaults_to_close():
    """src=None reads the `close` column by convention."""
    df = pl.DataFrame({"close": pl.Series([100.0, 101.0, 102.0], dtype=pl.Float64)})
    got = df.select(WMA(2).alias("wma"))["wma"]
    assert_series_equal(
        got, expected_series([100.0, 101.0, 102.0], 2), check_exact=False, rel_tol=1e-12
    )


def test_wma_src_accepts_column_name():
    """A bare column-name string works as src."""
    df = pl.DataFrame({"x": pl.Series([100.0, 101.0, 102.0], dtype=pl.Float64)})
    got = df.select(WMA(2, src="x").alias("wma"))["wma"]
    assert_series_equal(
        got, expected_series([100.0, 101.0, 102.0], 2), check_exact=False, rel_tol=1e-12
    )


@pytest.mark.parametrize("xs,period", CASES)
def test_wma_namespace(xs, period):
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = df.select(pl.col("x").bt.wma(period=period).alias("wma"))["wma"]
    assert_series_equal(got, expected_series(xs, period), check_exact=False, rel_tol=1e-12)


@pytest.mark.parametrize("xs,period", CASES)
def test_wma_pyfunction(xs, period):
    s = pl.Series("x", xs, dtype=pl.Float64)
    got = plugin.wma(s, period=period)
    assert_series_equal(
        got, expected_series(xs, period), check_names=False, check_exact=False, rel_tol=1e-12
    )


def test_pyfunction_matches_expression():
    """Both entry points share calc_wma, so they must agree element-for-element."""
    xs = [10.0, 11.0, None, 20.0, 21.0, 22.0]
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    expr_out = df.select(WMA(3, src=pl.col("x")).alias("wma"))["wma"]
    func_out = plugin.wma(df["x"], period=3)
    assert_series_equal(expr_out, func_out, check_names=False)


def test_integer_input_is_cast():
    """Non-f64 input is cast to Float64 rather than panicking."""
    s = pl.Series("x", [1, 2, 3, 4], dtype=pl.Int64)
    got = plugin.wma(s, period=2)
    assert got.dtype == pl.Float64
    assert_series_equal(
        got, expected_series([1.0, 2.0, 3.0, 4.0], 2), check_names=False, check_exact=False, rel_tol=1e-12
    )


def test_invalid_period_expression():
    df = pl.DataFrame({"x": pl.Series([1.0, 2.0, 3.0], dtype=pl.Float64)})
    with pytest.raises(pl.exceptions.PolarsError):
        df.select(WMA(0, src=pl.col("x")).alias("wma"))


def test_invalid_period_pyfunction():
    s = pl.Series("x", [1.0, 2.0, 3.0], dtype=pl.Float64)
    with pytest.raises(Exception):
        plugin.wma(s, period=0)
