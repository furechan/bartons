"""Accumulation/Distribution expressions."""

import polars as pl

from ...support import expression_factory
from ...typing import IntoExprColumn, into_expr
from .ema import EMA

__all__ = ("ADL", "ADOSC")


@expression_factory
def ADL(
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
    volume: IntoExprColumn = "volume",
) -> pl.Expr:
    """Accumulation/Distribution Line.

    Args:
        high: high column expression or name.
        low: low column expression or name.
        close: close column expression or name.
        volume: volume column expression or name.
    """
    high = into_expr(high).cast(pl.Float64)
    low = into_expr(low).cast(pl.Float64)
    close = into_expr(close).cast(pl.Float64)
    volume = into_expr(volume).cast(pl.Float64)
    multiplier = close.mul(2.0).sub(high).sub(low).truediv(high.sub(low))
    return multiplier.mul(volume).cum_sum()


@expression_factory
def ADOSC(
    fast: int = 3,
    slow: int = 10,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
    volume: IntoExprColumn = "volume",
) -> pl.Expr:
    """Chaikin A/D Oscillator — fast EMA minus slow EMA of ADL.

    Args:
        fast: fast EMA period.
        slow: slow EMA period.
        high: high column expression or name.
        low: low column expression or name.
        close: close column expression or name.
        volume: volume column expression or name.
    """
    adl = ADL(high=high, low=low, close=close, volume=volume)
    return EMA(fast, src=adl).sub(EMA(slow, src=adl))
