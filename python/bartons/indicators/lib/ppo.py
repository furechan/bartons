"""Percentage Price Oscillator composed from EMA expressions."""

import polars as pl

from ...prelude import wrap_src_indicator
from ...typing import IntoExprColumn
from .ema import EMA

__all__ = ("PPO",)


@wrap_src_indicator
def PPO(
    fast: int = 12,
    slow: int = 26,
    *,
    src: IntoExprColumn = "close",
) -> pl.Expr:
    """Price Percentage Oscillator in percentage points.

    ``100 * (EMA(fast) - EMA(slow)) / EMA(slow)``.

    Args:
        fast: fast EMA period.
        slow: slow EMA period.
        src: input column expression or name; defaults to ``close``.
    """
    fast_ema = EMA(fast, src=src)
    slow_ema = EMA(slow, src=src)
    return fast_ema.sub(slow_ema).truediv(slow_ema).mul(100.0)
