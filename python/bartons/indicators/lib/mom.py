"""Momentum composed from native Polars expressions."""

import polars as pl

from ...support import expression_factory
from ...typing import IntoExprColumn, into_expr

__all__ = ("MOM",)


@expression_factory(positional_src=True)
def MOM(
    period: int = 1,
    *,
    src: IntoExprColumn = "close",
) -> pl.Expr:
    """Difference from the value ``period`` rows earlier.

    Args:
        period: positive lookback distance.
        src: input column expression or name; defaults to ``close``.
    """
    if period <= 0:
        raise ValueError("period must be greater than zero")
    return into_expr(src).diff(period)
