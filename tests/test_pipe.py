"""The single-source factories accept their source column as the leading
positional arg (via the wrap_src_indicator decorator), so they compose with Expr.pipe."""

import polars as pl
import pytest
from helpers import assert_series_equal

from bartons.indicators import ALMA, DEMA, EMA, HMA, MA, RMA, RSI, SMA, TEMA, WMA, ZLEMA
from bartons.prelude import wrap_src_indicator

UNARY = [EMA, DEMA, TEMA, HMA, ZLEMA, ALMA, SMA, RMA, WMA, MA, RSI]


def test_wrap_src_indicator_requires_src_param():
    """Decorating a factory with no `src` keyword fails fast at decoration time."""
    with pytest.raises(TypeError, match="src"):

        @wrap_src_indicator
        def NoSrc(period):  # no src kwarg to route the leading expr into
            return pl.lit(period)

XS = [float(i) for i in (3, 1, 4, 1, 5, 9, 2, 6, 5, 3)]


@pytest.mark.parametrize("factory", UNARY)
def test_pipe_matches_src_kwarg(factory):
    """`col.pipe(F, n)` is exactly `F(n, src=col)`."""
    df = pl.DataFrame({"x": pl.Series(XS, dtype=pl.Float64)})
    via_pipe = df.select(pl.col("x").pipe(factory, 3).alias("o"))["o"]
    via_kwarg = df.select(factory(3, src=pl.col("x")).alias("o"))["o"]
    assert_series_equal(via_pipe, via_kwarg)


@pytest.mark.parametrize("factory", UNARY)
def test_leading_expr_with_src_kwarg_raises(factory):
    """Passing both a leading expression and an explicit src is a conflict."""
    with pytest.raises(ValueError, match="src"):
        pl.col("x").pipe(factory, 3, src=pl.col("y"))


@pytest.mark.parametrize("factory", UNARY)
def test_plain_call_unaffected(factory):
    """`F(n)` still reads `close` by default; `F(n, src=...)` still works."""
    df = pl.DataFrame({"close": pl.Series(XS, dtype=pl.Float64)})
    default = df.select(factory(3).alias("o"))["o"]
    explicit = df.select(factory(3, src=pl.col("close")).alias("o"))["o"]
    assert_series_equal(default, explicit)


def test_pipe_chaining_composes():
    """`col.pipe(EMA, 3).pipe(SMA, 2)` == SMA(2) of EMA(3) of the column."""
    df = pl.DataFrame({"close": pl.Series(XS, dtype=pl.Float64)})
    chained = df.select(pl.col("close").pipe(EMA, 3).pipe(SMA, 2).alias("o"))["o"]
    nested = df.select(SMA(2, src=EMA(3, src=pl.col("close"))).alias("o"))["o"]
    assert_series_equal(chained, nested)
