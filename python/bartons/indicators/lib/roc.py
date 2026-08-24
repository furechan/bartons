"""Rate of Change composed from native Polars expressions."""

import polars as pl

from ...prelude import wrap_src_indicator
from ...typing import IntoExprColumn, into_expr

__all__ = ("ROC",)


@wrap_src_indicator
def ROC(
    period: int = 1,
    *,
    src: IntoExprColumn | None = None,
) -> pl.Expr:
    """Raw fractional rate of change over ``period`` rows.

    Args:
        period: positive lookback distance.
        src: input column expression or name; defaults to ``close``.
    """
    if period <= 0:
        raise ValueError("period must be greater than zero")
    source = into_expr("close" if src is None else src)
    return source.pct_change(period)
