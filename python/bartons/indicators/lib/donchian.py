"""Donchian Channels composed from native Polars rolling expressions."""

import polars as pl

from ...prelude import wrap_indicator
from ...typing import IntoExprColumn, into_expr

__all__ = ("DONCHIAN",)


@wrap_indicator
def DONCHIAN(
    period: int = 20,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
) -> pl.Expr:
    """Donchian Channels as an upper, middle, and lower band struct.

    Args:
        period: rolling channel period.
        high: high column expression or name.
        low: low column expression or name.
    """
    if period <= 0:
        raise ValueError("period must be greater than zero")

    upper = into_expr(high).rolling_max(period, min_samples=period)
    lower = into_expr(low).rolling_min(period, min_samples=period)
    middle = upper.add(lower).truediv(2.0)
    return pl.struct(
        upper.alias("upperband"),
        middle.alias("middleband"),
        lower.alias("lowerband"),
    )
