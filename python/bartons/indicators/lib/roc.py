"""Rate of Change composed from native Polars expressions."""

import polars as pl

from ...prelude import wrap_src_indicator
from ...typing import IntoExprColumn, into_expr

__all__ = ("ROC", "ROCP", "LROC")


@wrap_src_indicator
def ROC(
    period: int = 1,
    *,
    src: IntoExprColumn = "close",
) -> pl.Expr:
    """Rate of Change over ``period`` rows.

    Returns ``100 * (source / source.shift(period) - 1)`` in percentage points.

    Args:
        period: positive lookback distance.
        src: input column expression or name; defaults to ``close``.
    """
    if period <= 0:
        raise ValueError("period must be greater than zero")
    source = into_expr(src)
    return 100.0 * source.pct_change(period)


@wrap_src_indicator
def ROCP(
    period: int = 1,
    *,
    src: IntoExprColumn = "close",
) -> pl.Expr:
    """Rate of Change Percentage over ``period`` rows.

    Returns ``source / source.shift(period) - 1`` as an unscaled fraction.

    Args:
        period: positive lookback distance.
        src: input column expression or name; defaults to ``close``.
    """
    if period <= 0:
        raise ValueError("period must be greater than zero")
    source = into_expr(src)
    return source.pct_change(period)


@wrap_src_indicator
def LROC(
    period: int = 1,
    *,
    src: IntoExprColumn = "close",
) -> pl.Expr:
    """Logarithmic Rate of Change over ``period`` rows.

    Returns ``log(source) - log(source.shift(period))`` without scaling.

    Args:
        period: positive lookback distance.
        src: input column expression or name; defaults to ``close``.
    """
    if period <= 0:
        raise ValueError("period must be greater than zero")
    source = into_expr(src)
    return source.log() - source.shift(period).log()
