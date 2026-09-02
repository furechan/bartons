"""TRIX composed from existing EMA and native Polars expressions."""

import polars as pl

from ...support import expression_factory
from ...typing import IntoExprColumn
from .ema import EMA

__all__ = ("TRIX",)


@expression_factory(positional_src=True)
def TRIX(
    period: int = 30,
    *,
    src: IntoExprColumn = "close",
) -> pl.Expr:
    """Percentage rate of change of a triple-smoothed EMA.

    The source is passed through three sequential EMAs using the same period,
    then its one-row fractional change is multiplied by 100.

    Args:
        period: positive smoothing period for all three EMAs.
        src: input column expression; defaults to ``pl.col("close")``.
            A column name string is also accepted.
    """
    if period <= 0:
        raise ValueError("period must be greater than zero")

    first = EMA(period, src=src)
    second = EMA(period, src=first)
    third = EMA(period, src=second)
    previous = third.shift(1)
    return ((third - previous) / previous).mul(100.0)
