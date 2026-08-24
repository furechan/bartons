"""Keltner Channels composed from existing indicator expressions."""

import polars as pl

from ...prelude import wrap_indicator
from ...typing import IntoExprColumn
from .atr import ATR
from .ema import EMA
from .price import TYPPRICE

__all__ = ("KELTNER",)


@wrap_indicator
def KELTNER(
    period: int = 20,
    nbatr: float = 2.0,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Keltner Channels as an upper, middle, and lower band struct.

    The middle band is an EMA of typical price by default. The channel width
    is ``nbatr`` times ATR.

    Args:
        period: EMA and ATR period.
        nbatr: ATR multiplier on either side of the middle band.
        high: high column expression or name.
        low: low column expression or name.
        close: close column expression or name.
    """
    middle = EMA(period, src=TYPPRICE(high=high, low=low, close=close))
    width = nbatr * ATR(period, high=high, low=low, close=close)
    return pl.struct(
        middle.add(width).alias("upperband"),
        middle.alias("middleband"),
        middle.sub(width).alias("lowerband"),
    )
