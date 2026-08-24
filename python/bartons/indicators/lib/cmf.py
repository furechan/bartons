"""Chaikin Money Flow composed from native Polars expressions."""

import polars as pl

from ...prelude import wrap_indicator
from ...typing import IntoExprColumn, into_expr

__all__ = ("CMF",)


@wrap_indicator
def CMF(
    period: int = 20,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
    volume: IntoExprColumn = "volume",
) -> pl.Expr:
    """Chaikin Money Flow.

    Args:
        period: rolling money-flow period.
        high: high column expression or name.
        low: low column expression or name.
        close: close column expression or name.
        volume: volume column expression or name.
    """
    if period <= 0:
        raise ValueError("period must be greater than zero")

    high = into_expr(high).cast(pl.Float64)
    low = into_expr(low).cast(pl.Float64)
    close = into_expr(close).cast(pl.Float64)
    volume = into_expr(volume).cast(pl.Float64)

    multiplier = close.mul(2.0).sub(high).sub(low).truediv(high.sub(low))
    flow = multiplier.mul(volume)
    return flow.rolling_sum(period, min_samples=period).truediv(
        volume.rolling_sum(period, min_samples=period)
    )
