import polars as pl
import pytest
from helpers import assert_series_equal

from bartons import plugin
from bartons.expressions import ATR


def ref_trange(highs, lows, closes):
    """TR = max(h-l, |h-prev_close|, |l-prev_close|), first bar = h-l, null when
    high or low is missing."""
    out = []
    prev_close = None
    for h, l, c in zip(highs, lows, closes):
        if h is None or l is None:
            out.append(None)
        else:
            tr = h - l
            if prev_close is not None:
                tr = max(tr, abs(h - prev_close), abs(l - prev_close))
            out.append(tr)
        prev_close = c
    return out


def ref_rma(xs, period):
    """Wilder smoothing with simple-average seed; null during warmup, reset on null."""
    alpha = 1.0 / period
    rma = None
    total = 0.0
    count = 0
    out = []
    for x in xs:
        if x is None:
            rma = None
            total = 0.0
            count = 0
            out.append(None)
            continue
        count += 1
        if count <= period:
            total += x
            rma = total / count
        else:
            rma += alpha * (x - rma)
        out.append(rma if count >= period else None)
    return out


def ref_atr(highs, lows, closes, period):
    """ATR is Wilder's RMA of the True Range — mirrors calc_atr (trange -> rma)."""
    return ref_rma(ref_trange(highs, lows, closes), period)


# (highs, lows, closes, period) — covers warmup, a flat series (ATR 0), a
# mid-series null reset + re-warm, and period == 1.
CASES = [
    (
        [10.0, 12.0, 11.0, 13.0, 14.0, 12.0],
        [8.0, 9.0, 9.0, 10.0, 11.0, 10.0],
        [9.0, 11.0, 10.0, 12.0, 13.0, 11.0],
        2,
    ),
    ([5.0, 5.0, 5.0, 5.0], [5.0, 5.0, 5.0, 5.0], [5.0, 5.0, 5.0, 5.0], 2),
    (
        [10.0, 12.0, None, 13.0, 14.0, 12.0],
        [8.0, 9.0, 9.0, None, 11.0, 10.0],
        [9.0, 11.0, 10.0, 12.0, 13.0, 11.0],
        2,
    ),
    ([10.0, 12.0, 11.0, 13.0], [8.0, 9.0, 9.0, 10.0], [9.0, 11.0, 10.0, 12.0], 1),
]


def expected_series(highs, lows, closes, period):
    return pl.Series("atr", ref_atr(highs, lows, closes, period), dtype=pl.Float64)


def _df(highs, lows, closes):
    return pl.DataFrame(
        {
            "high": pl.Series(highs, dtype=pl.Float64),
            "low": pl.Series(lows, dtype=pl.Float64),
            "close": pl.Series(closes, dtype=pl.Float64),
        }
    )


@pytest.mark.parametrize("highs,lows,closes,period", CASES)
def test_atr_expression(highs, lows, closes, period):
    df = _df(highs, lows, closes)
    got = df.select(ATR(period).alias("atr"))["atr"]
    assert_series_equal(
        got, expected_series(highs, lows, closes, period), check_exact=False, rel_tol=1e-12
    )


def test_atr_flat_series_is_zero():
    """A dead-flat series has zero true range, so ATR is 0 after warmup."""
    df = _df([5.0, 5.0, 5.0, 5.0], [5.0, 5.0, 5.0, 5.0], [5.0, 5.0, 5.0, 5.0])
    got = df.select(ATR(2).alias("atr"))["atr"]
    assert got.to_list() == [None, 0.0, 0.0, 0.0]


def test_atr_accepts_column_names_and_exprs():
    """Custom column names and explicit expressions both work as inputs."""
    df = pl.DataFrame(
        {
            "h": pl.Series([10.0, 12.0, 11.0, 13.0], dtype=pl.Float64),
            "l": pl.Series([8.0, 9.0, 9.0, 10.0], dtype=pl.Float64),
            "c": pl.Series([9.0, 11.0, 10.0, 12.0], dtype=pl.Float64),
        }
    )
    by_name = df.select(ATR(2, high="h", low="l", close="c").alias("atr"))["atr"]
    by_expr = df.select(
        ATR(2, high=pl.col("h"), low=pl.col("l"), close=pl.col("c")).alias("atr")
    )["atr"]
    expected = expected_series([10.0, 12.0, 11.0, 13.0], [8.0, 9.0, 9.0, 10.0], [9.0, 11.0, 10.0, 12.0], 2)
    assert_series_equal(by_name, expected, check_exact=False, rel_tol=1e-12)
    assert_series_equal(by_expr, expected, check_exact=False, rel_tol=1e-12)


@pytest.mark.parametrize("highs,lows,closes,period", CASES)
def test_atr_pyfunction(highs, lows, closes, period):
    h = pl.Series("high", highs, dtype=pl.Float64)
    l = pl.Series("low", lows, dtype=pl.Float64)
    c = pl.Series("close", closes, dtype=pl.Float64)
    got = plugin.atr(h, l, c, period=period)
    assert_series_equal(
        got, expected_series(highs, lows, closes, period),
        check_names=False, check_exact=False, rel_tol=1e-12,
    )


def test_pyfunction_matches_expression():
    """Both entry points share calc_atr, so they must agree element-for-element."""
    highs, lows, closes, period = CASES[2]  # the null-reset case
    df = _df(highs, lows, closes)
    expr_out = df.select(ATR(period).alias("atr"))["atr"]
    func_out = plugin.atr(df["high"], df["low"], df["close"], period=period)
    assert_series_equal(expr_out, func_out, check_names=False)


def test_integer_input_is_cast():
    """Non-f64 input is cast to Float64 rather than panicking."""
    h = pl.Series("high", [10, 12, 11, 13], dtype=pl.Int64)
    l = pl.Series("low", [8, 9, 9, 10], dtype=pl.Int64)
    c = pl.Series("close", [9, 11, 10, 12], dtype=pl.Int64)
    got = plugin.atr(h, l, c, period=2)
    assert got.dtype == pl.Float64
    assert_series_equal(
        got, expected_series([10.0, 12.0, 11.0, 13.0], [8.0, 9.0, 9.0, 10.0], [9.0, 11.0, 10.0, 12.0], 2),
        check_names=False, check_exact=False, rel_tol=1e-12,
    )


def test_invalid_period_expression():
    df = _df([10.0, 12.0, 11.0], [8.0, 9.0, 9.0], [9.0, 11.0, 10.0])
    with pytest.raises(pl.exceptions.PolarsError):
        df.select(ATR(0).alias("atr"))


def test_invalid_period_pyfunction():
    h = pl.Series("high", [10.0, 12.0, 11.0], dtype=pl.Float64)
    l = pl.Series("low", [8.0, 9.0, 9.0], dtype=pl.Float64)
    c = pl.Series("close", [9.0, 11.0, 10.0], dtype=pl.Float64)
    with pytest.raises(Exception):
        plugin.atr(h, l, c, period=0)
