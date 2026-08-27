"""Stochastic RSI composed from existing indicator and Polars expressions."""

import polars as pl

from ...support import expression_factory
from ...typing import IntoExprColumn
from .rsi import RSI

__all__ = ("STOCHRSI",)


@expression_factory(positional_src=True)
def STOCHRSI(
    period: int = 14,
    fastn: int = 3,
    slown: int = 3,
    *,
    src: IntoExprColumn = "close",
) -> pl.Expr:
    """Stochastic RSI as a ``fastk`` and ``fastd`` struct.

    Wilder RSI and the stochastic normalization both use ``period``. The raw
    stochastic RSI is smoothed over ``fastn`` observations to produce fast K,
    then fast K is smoothed over ``slown`` observations to produce fast D.

    Args:
        period: RSI smoothing and stochastic lookback period.
        fastn: moving-average period that smooths raw stochastic RSI.
        slown: moving-average period that smooths fast K into fast D.
        src: input column expression; defaults to ``pl.col("close")``.
            A column name string is also accepted.
    """
    if period <= 0 or fastn <= 0 or slown <= 0:
        raise ValueError("period, fastn, and slown must be greater than zero")

    rsi = RSI(period, src=src)
    lowest = rsi.rolling_min(period, min_samples=period)
    highest = rsi.rolling_max(period, min_samples=period)
    raw = 100.0 * (rsi - lowest) / (highest - lowest)
    fastk = raw.rolling_mean(fastn, min_samples=fastn)
    fastd = fastk.rolling_mean(slown, min_samples=slown)
    return pl.struct(fastk.alias("fastk"), fastd.alias("fastd"))
