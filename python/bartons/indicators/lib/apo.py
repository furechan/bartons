"""Absolute Price Oscillator composed from generic moving averages."""

import polars as pl

from ...support import expression_factory
from ...typing import IntoExprColumn, MAType
from .ma import MA

__all__ = ("APO",)


@expression_factory(positional_src=True)
def APO(
    fast: int = 12,
    slow: int = 26,
    *,
    matype: MAType = "ema",
    src: IntoExprColumn = "close",
) -> pl.Expr:
    """Absolute Price Oscillator in the source's units.

    Returns ``MA(fast) - MA(slow)``. The moving-average type defaults to EMA,
    matching the MACD-like convention; use ``matype="sma"`` for TA-Lib's
    default behavior.

    Args:
        fast: fast moving-average period.
        slow: slow moving-average period.
        matype: moving-average type accepted by :func:`MA`.
        src: input column expression or name.
    """
    fast_ma = MA(fast, matype=matype, src=src)
    slow_ma = MA(slow, matype=matype, src=src)
    return fast_ma.sub(slow_ma)
