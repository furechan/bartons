import polars as pl

from ..bundle import ExprBundle
from ..prelude import wrap_src_indicator
from ..typing import IntoExprColumn
from .ema import EMA


@wrap_src_indicator
def MACD(
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    *,
    src: IntoExprColumn | None = None,
) -> ExprBundle:
    """Moving Average Convergence/Divergence lines.

    This is native Polars composition over the EMA kernel. It returns the
    independently named ``macd``, ``macdsignal`` and ``macdhist`` expressions.

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

    return ExprBundle(
        macd=line,
        macdsignal=signal_line,
        macdhist=line - signal_line,
    )
