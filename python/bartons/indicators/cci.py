import polars as pl

from ..typing import IntoExprColumn
from .mad import MAD
from .sma import SMA


def CCI(
    period: int = 20,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Commodity Channel Index.

    Native composition of typical price, SMA and rolling mean absolute
    deviation: ``(typical - SMA) / (0.015 * MAD)``.
    """
    typical = (_expr(high) + _expr(low) + _expr(close)) / 3.0
    return (typical - SMA(period, src=typical)) / (0.015 * MAD(period, src=typical))


def _expr(value: IntoExprColumn) -> pl.Expr:
    if isinstance(value, str):
        return pl.col(value)
    if isinstance(value, pl.Series):
        return pl.lit(value)
    return value
