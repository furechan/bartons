"""Volume-Weighted Moving Average composed from native Polars expressions."""

import polars as pl

from ...prelude import wrap_src_indicator
from ...typing import IntoExprColumn, into_expr

__all__ = ("VWMA",)


@wrap_src_indicator
def VWMA(
    period: int = 20,
    *,
    src: IntoExprColumn = "close",
    volume: IntoExprColumn = "volume",
) -> pl.Expr:
    """Volume-Weighted Moving Average over ``period`` rows.

    Returns ``sum(src * volume) / sum(volume)`` over each complete rolling
    window.

    Args:
        period: positive rolling period.
        src: price column expression or name.
        volume: volume column expression or name.
    """
    if period <= 0:
        raise ValueError("period must be greater than zero")

    source = into_expr(src).cast(pl.Float64)
    volume = into_expr(volume).cast(pl.Float64)
    weights = pl.when(source.is_null()).then(None).otherwise(volume)
    weighted_sum = source.mul(weights).rolling_sum(period, min_samples=period)
    weight_sum = weights.rolling_sum(period, min_samples=period)
    return weighted_sum.truediv(weight_sum)
