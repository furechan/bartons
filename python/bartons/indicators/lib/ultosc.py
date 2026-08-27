"""Ultimate Oscillator composed from native Polars expressions."""

import polars as pl

from ...support import expression_factory
from ...typing import IntoExprColumn, into_expr

__all__ = ("ULTOSC",)


@expression_factory
def ULTOSC(
    fast: int = 7,
    medium: int = 14,
    slow: int = 28,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Ultimate Oscillator on a 0–100 scale.

    Buying pressure and true range are accumulated over three periods, then
    their ratios are combined with 4:2:1 weights from fastest to slowest.

    Args:
        fast: shortest rolling period.
        medium: middle rolling period.
        slow: longest rolling period.
        high: high column expression or name.
        low: low column expression or name.
        close: close column expression or name.
    """
    if fast <= 0 or medium <= 0 or slow <= 0:
        raise ValueError("fast, medium, and slow must be greater than zero")

    high_expr = into_expr(high)
    low_expr = into_expr(low)
    close_expr = into_expr(close)
    previous_close = close_expr.shift(1)
    complete = (
        high_expr.is_not_null()
        & low_expr.is_not_null()
        & close_expr.is_not_null()
        & previous_close.is_not_null()
    )
    buying_pressure = pl.when(complete).then(
        close_expr - pl.min_horizontal(low_expr, previous_close)
    )
    true_range = pl.when(complete).then(
        pl.max_horizontal(high_expr, previous_close)
        - pl.min_horizontal(low_expr, previous_close)
    )

    def average(period: int) -> pl.Expr:
        pressure = buying_pressure.rolling_sum(period, min_samples=period)
        range_ = true_range.rolling_sum(period, min_samples=period)
        return pressure / range_

    return 100.0 * (
        4.0 * average(fast) + 2.0 * average(medium) + average(slow)
    ) / 7.0
