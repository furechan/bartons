"""Percentage Price Oscillator composed from generic moving averages."""

import polars as pl

from ...support import expression_factory
from ...typing import IntoExprColumn, MAType
from .ma import MA

__all__ = ("PPO",)


@expression_factory(positional_src=True)
def PPO(
    fast: int = 12,
    slow: int = 26,
    *,
    matype: MAType = "ema",
    src: IntoExprColumn = "close",
) -> pl.Expr:
    """Price Percentage Oscillator in percentage points.

    ``100 * (MA(fast) - MA(slow)) / MA(slow)``. The moving-average type
    defaults to EMA, matching the MACD-like convention; use ``matype="sma"``
    for TA-Lib's default behavior.

    Args:
        fast: fast moving-average period.
        slow: slow moving-average period.
        matype: moving-average type accepted by :func:`MA`.
        src: input column expression or name; defaults to ``close``.
    """
    fast_ma = MA(fast, matype=matype, src=src)
    slow_ma = MA(slow, matype=matype, src=src)
    return fast_ma.sub(slow_ma).truediv(slow_ma).mul(100.0)
