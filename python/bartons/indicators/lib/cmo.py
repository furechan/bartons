"""Chande Momentum Oscillator composed from native Polars expressions."""

import polars as pl

from ...prelude import wrap_src_indicator
from ...typing import IntoExprColumn, into_expr

__all__ = ("CMO",)


@wrap_src_indicator
def CMO(
    period: int = 14,
    *,
    src: IntoExprColumn = "close",
) -> pl.Expr:
    """Original rolling-window Chande Momentum Oscillator.

    Returns ``100 * (sum(gains) - sum(losses)) / (sum(gains) + sum(losses))``
    over the most recent ``period`` changes. This is the original rolling-sum
    formulation, not TA-Lib's Wilder-smoothed variant. A flat window returns
    zero.

    Args:
        period: positive rolling period.
        src: input column expression or name; defaults to ``close``.
    """
    if period <= 0:
        raise ValueError("period must be greater than zero")

    change = into_expr(src).diff()
    gains = change.clip(lower_bound=0.0)
    losses = change.neg().clip(lower_bound=0.0)
    gain_sum = gains.rolling_sum(period, min_samples=period)
    loss_sum = losses.rolling_sum(period, min_samples=period)
    total = gain_sum + loss_sum
    return (
        pl.when(total == 0.0)
        .then(0.0)
        .otherwise(100.0 * (gain_sum - loss_sum) / total)
    )
