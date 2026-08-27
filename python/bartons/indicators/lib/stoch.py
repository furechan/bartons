"""Stochastic Oscillator composed from native Polars rolling expressions."""

import polars as pl

from ...support import expression_factory
from ...typing import IntoExprColumn, into_expr

__all__ = ("STOCH",)


@expression_factory
def STOCH(
    period: int = 14,
    fastn: int = 3,
    slown: int = 3,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Stochastic Oscillator as a ``slowk`` and ``slowd`` struct.

    Args:
        period: high/low lookback for fast %K.
        fastn: moving-average period that smooths fast %K into slow %K.
        slown: moving-average period that smooths slow %K into slow %D.
        high: high column expression or name.
        low: low column expression or name.
        close: close column expression or name.
    """
    if period <= 0 or fastn <= 0 or slown <= 0:
        raise ValueError("period, fastn, and slown must be greater than zero")

    high_expr = into_expr(high)
    low_expr = into_expr(low)
    close_expr = into_expr(close)
    lowest = low_expr.rolling_min(period, min_samples=period)
    highest = high_expr.rolling_max(period, min_samples=period)
    fastk = 100.0 * (close_expr - lowest) / (highest - lowest)
    slowk = fastk.rolling_mean(fastn, min_samples=fastn)
    slowd = slowk.rolling_mean(slown, min_samples=slown)
    return pl.struct(slowk.alias("slowk"), slowd.alias("slowd"))
