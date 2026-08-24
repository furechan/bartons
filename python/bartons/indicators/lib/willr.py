"""Williams %R composed from native Polars rolling expressions."""

import polars as pl

from ...prelude import wrap_indicator
from ...typing import IntoExprColumn, into_expr

__all__ = ("WILLR",)


@wrap_indicator
def WILLR(
    period: int = 14,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Williams %R oscillator.

    Args:
        period: rolling high/low lookback.
        high: high column expression or name.
        low: low column expression or name.
        close: close column expression or name.
    """
    if period <= 0:
        raise ValueError("period must be greater than zero")

    high_expr = into_expr(high)
    low_expr = into_expr(low)
    close_expr = into_expr(close)
    highest = high_expr.rolling_max(period, min_samples=period)
    lowest = low_expr.rolling_min(period, min_samples=period)
    return close_expr.sub(highest).truediv(highest.sub(lowest)).mul(100.0)
