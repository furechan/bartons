import polars as pl
import pytest
from helpers import assert_series_equal

from bartons import kernels
from bartons.indicators import KAMA, KER
from refimpl import ref_kama, ref_ker


# (values, period, fastn, slown) — covers warmup nulls, a perfect trend (alpha
# pinned to fast), chop (alpha near slow), a mid-series null (the ratio's window
# resets while the average carries), leading nulls, a flat series, and
# period == 1.
CASES = [
    ([100.0, 101.0, 102.0], 2, 2, 30),
    ([1.0, 2.0, 3.0, 4.0, 5.0], 2, 2, 30),
    ([1.0, 3.0, 2.0, 4.0, 3.0, 5.0], 3, 2, 30),
    ([10.0, 11.0, None, 20.0, 21.0, 22.0], 2, 2, 30),
    ([5.0, 5.0, 5.0, 5.0], 3, 2, 30),
    ([None, None, 1.0, 2.0, 3.0], 1, 2, 30),
    ([1.0, 2.0, 4.0, 8.0, 5.0, 9.0, 3.0], 2, 4, 12),
]


def expected_series(xs, period, fastn, slown):
    return pl.Series("kama", ref_kama(xs, period, fastn, slown), dtype=pl.Float64)


@pytest.mark.parametrize("xs,period,fastn,slown", CASES)
def test_kama_expression(xs, period, fastn, slown):
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = df.select(KAMA(period, fastn, slown, src=pl.col("x")).alias("kama"))["kama"]
    assert_series_equal(
        got, expected_series(xs, period, fastn, slown), check_exact=False, rel_tol=1e-12
    )


def test_kama_src_defaults_to_close():
    """The default src reads the `close` column by convention."""
    df = pl.DataFrame({"close": pl.Series([1.0, 2.0, 3.0, 4.0], dtype=pl.Float64)})
    got = df.select(KAMA(2).alias("kama"))["kama"]
    assert_series_equal(
        got,
        expected_series([1.0, 2.0, 3.0, 4.0], 2, 2, 30),
        check_exact=False,
        rel_tol=1e-12,
    )


def test_kama_src_accepts_column_name():
    """A bare column-name string works as src."""
    df = pl.DataFrame({"x": pl.Series([1.0, 2.0, 3.0, 4.0], dtype=pl.Float64)})
    got = df.select(KAMA(2, src="x").alias("kama"))["kama"]
    assert_series_equal(
        got,
        expected_series([1.0, 2.0, 3.0, 4.0], 2, 2, 30),
        check_exact=False,
        rel_tol=1e-12,
    )


@pytest.mark.parametrize("xs,period,fastn,slown", CASES)
def test_kama_pyfunction(xs, period, fastn, slown):
    s = pl.Series("x", xs, dtype=pl.Float64)
    got = kernels.kama(s, period=period, fastn=fastn, slown=slown)
    assert_series_equal(
        got,
        expected_series(xs, period, fastn, slown),
        check_names=False,
        check_exact=False,
        rel_tol=1e-12,
    )


def test_pyfunction_matches_expression():
    """Both entry points share the same kernel, so they must agree
    element-for-element."""
    xs = [10.0, 11.0, None, 20.0, 21.0, 22.0]
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    expr_out = df.select(KAMA(3, src=pl.col("x")).alias("kama"))["kama"]
    func_out = kernels.kama(df["x"], period=3)
    assert_series_equal(expr_out, func_out, check_names=False)


def test_kama_defaults_match_mintalib():
    """The defaults are period=10, fastn=2, slown=30 on both surfaces.

    mintalib's, not bearta's period=20 — checked by behaviour rather than by
    introspecting the signature, so the expression and eager surfaces are both
    covered and neither can drift.
    """
    xs = [float((i * 7) % 11) + i * 0.5 for i in range(40)]
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = df.select(
        KAMA(src=pl.col("x")).alias("default"),
        KAMA(10, 2, 30, src=pl.col("x")).alias("explicit"),
    )
    assert_series_equal(got["default"], got["explicit"], check_names=False)
    assert_series_equal(
        kernels.kama(df["x"]),
        kernels.kama(df["x"], period=10, fastn=2, slown=30),
    )


@pytest.mark.parametrize("xs,period,fastn,slown", CASES)
def test_kama_nulls_align_with_ker(xs, period, fastn, slown):
    """KAMA emits exactly where the ratio does.

    The average carries its running value across a gap, but it cannot emit
    again until the ratio's window has refilled, so the two null masks are the
    same — including the longer re-warmup after a null.
    """
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = df.select(
        KAMA(period, fastn, slown, src=pl.col("x")).alias("kama"),
        KER(period, src=pl.col("x")).alias("ker"),
    )
    kama_nulls = [v is None for v in got["kama"].to_list()]
    ker_nulls = [v is None for v in got["ker"].to_list()]
    assert kama_nulls == ker_nulls


def test_kama_carries_across_a_gap():
    """The running average is not re-seeded after a null.

    Distinguishes the recursive convention (carry, like EMA/RMA) from a reset:
    on re-seed the first post-gap output would equal the input value.
    """
    xs = [10.0, 11.0, 12.0, 13.0, None, 40.0, 41.0, 42.0, 43.0]
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = df.select(KAMA(2, src=pl.col("x")).alias("kama"))["kama"].to_list()
    resumed = [(i, v) for i, v in enumerate(got) if i > 4 and v is not None]
    assert resumed, "expected output after the gap"
    index, value = resumed[0]
    assert value != xs[index], "re-seeded on the gap instead of carrying"
    assert_series_equal(
        pl.Series("kama", got, dtype=pl.Float64),
        pl.Series("kama", ref_kama(xs, 2), dtype=pl.Float64),
        check_exact=False,
        rel_tol=1e-12,
    )


def test_trend_and_chop_bracket_the_smoothing():
    """The adaptive alpha's whole reason for existing, at both extremes.

    A monotone ramp is perfectly efficient (ER = 1, alpha pinned to `fast`), so
    the average traverses most of the price range. A strict alternation retraces
    every step (ER = 0, alpha pinned to `slow`), so it barely moves at all. The
    span ratio is the observable: how much of the price range the average covers.
    """
    trend = [float(i) for i in range(1, 21)]
    chop = [1.0 + (i % 2) for i in range(20)]

    def measure(xs):
        df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
        got = df.select(
            KAMA(4, src=pl.col("x")).alias("kama"), KER(4, src=pl.col("x")).alias("ker")
        )
        kama = [v for v in got["kama"].to_list() if v is not None]
        ratios = [v for v in got["ker"].to_list() if v is not None]
        return ratios, (max(kama) - min(kama)) / (max(xs) - min(xs))

    trend_ratios, trend_span = measure(trend)
    chop_ratios, chop_span = measure(chop)

    assert trend_ratios == pytest.approx([1.0] * len(trend_ratios)), (
        "a monotone ramp never retraces"
    )
    assert chop_ratios == pytest.approx([0.0] * len(chop_ratios)), (
        "a strict alternation nets out to zero"
    )
    assert trend_span > 0.6, trend_span
    assert chop_span < 0.1, chop_span


def test_integer_input_is_cast():
    """Non-f64 input is cast to Float64 rather than panicking."""
    s = pl.Series("x", [1, 2, 3, 4], dtype=pl.Int64)
    got = kernels.kama(s, period=2)
    assert got.dtype == pl.Float64
    assert_series_equal(
        got,
        expected_series([1.0, 2.0, 3.0, 4.0], 2, 2, 30),
        check_names=False,
        check_exact=False,
        rel_tol=1e-12,
    )


def test_kama_ratio_is_the_ker_kernel():
    """KAMA's alpha is derived from the same ratio KER exposes.

    Recomputing KAMA from the `KER()` column reproduces the kernel exactly, so
    the two surfaces cannot drift apart on the formula.
    """
    xs = [1.0, 3.0, 2.0, 5.0, 4.0, 8.0, 6.0, 9.0, 7.0, 12.0]
    df = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    ratios = df.select(KER(3, src=pl.col("x")).alias("ker"))["ker"].to_list()
    assert ratios == pytest.approx(ref_ker(xs, 3), rel=1e-12, nan_ok=True)

    fast, slow = 2.0 / 3.0, 2.0 / 31.0
    rebuilt, value = [], None
    for x, ratio in zip(xs, ratios):
        if ratio is None:
            rebuilt.append(None)
            continue
        alpha = (slow + ratio * (fast - slow)) ** 2.0
        value = x if value is None else value + alpha * (x - value)
        rebuilt.append(value)

    got = df.select(KAMA(3, src=pl.col("x")).alias("kama"))["kama"]
    assert_series_equal(
        got, pl.Series("kama", rebuilt, dtype=pl.Float64), check_exact=False, rel_tol=1e-12
    )


def test_invalid_period_expression():
    df = pl.DataFrame({"x": pl.Series([1.0, 2.0, 3.0], dtype=pl.Float64)})
    with pytest.raises(pl.exceptions.PolarsError):
        df.select(KAMA(0, src=pl.col("x")).alias("kama"))


def test_invalid_period_pyfunction():
    s = pl.Series("x", [1.0, 2.0, 3.0], dtype=pl.Float64)
    with pytest.raises(ValueError, match="period must be > 0"):
        kernels.kama(s, period=0)


@pytest.mark.parametrize("fastn,slown", [(0, 30), (2, 0), (-1, 30)])
def test_invalid_smoothing_bounds(fastn, slown):
    s = pl.Series("x", [1.0, 2.0, 3.0], dtype=pl.Float64)
    with pytest.raises(ValueError, match="fastn and slown must be > 0"):
        kernels.kama(s, period=2, fastn=fastn, slown=slown)
