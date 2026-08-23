import polars as pl

from ..prelude import wrap_src_indicator
from ..typing import IntoExprColumn
from .ema import EMA

__all__ = ("MACD",)


@wrap_src_indicator
def MACD(
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    *,
    src: IntoExprColumn | None = None,
) -> pl.Expr:
    """Moving Average Convergence/Divergence lines.

    This is native Polars composition over the EMA kernel. It returns one
    struct expression with ``macd``, ``macdsignal`` and ``macdhist`` fields.

    Args:
        fast: period of the fast EMA.
        slow: period of the slow EMA.
        signal: period of the EMA applied to the MACD line.
        src: input column expression; defaults to ``pl.col("close")``.
            A column name string is also accepted.
    """
    if src is None:
        src = pl.col("close")

    line = EMA(fast, src=src) - EMA(slow, src=src)
    signal_line = EMA(signal, src=line)

    return pl.struct(
        line.alias("macd"),
        signal_line.alias("macdsignal"),
        (line - signal_line).alias("macdhist"),
    )
