"""Balance of Power as a native Polars expression."""

import polars as pl

from ...prelude import wrap_indicator
from ...typing import IntoExprColumn, into_expr

__all__ = ("BOP",)


@wrap_indicator
def BOP(
    *,
    open: IntoExprColumn = "open",
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Balance of Power — ``(close - open) / (high - low)``.

    This is the unsmoothed per-bar indicator. Apply a moving average explicitly
    when a smoother series is desired.

    Args:
        open: open column expression or name.
        high: high column expression or name.
        low: low column expression or name.
        close: close column expression or name.
    """
    open = into_expr(open).cast(pl.Float64)
    high = into_expr(high).cast(pl.Float64)
    low = into_expr(low).cast(pl.Float64)
    close = into_expr(close).cast(pl.Float64)
    return close.sub(open).truediv(high.sub(low))
