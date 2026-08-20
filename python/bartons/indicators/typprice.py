import polars as pl

from ..typing import IntoExprColumn


def TYPPRICE(
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Typical price — ``(high + low + close) / 3``.

    Native polars composition, with no kernel behind it: the reduction is
    elementwise and stateless, so polars already computes it vectorized. It is
    the single definition of the formula, shared by :func:`CCI` and available on
    its own.

    A multi-input indicator: pass the high, low and close columns (names or
    expressions); they default to ``"high"``, ``"low"`` and ``"close"``.

    Args:
        high: high column expression or name.
        low: low column expression or name.
        close: close column expression or name.
    """
    return (_expr(high) + _expr(low) + _expr(close)) / 3.0


def _expr(value: IntoExprColumn) -> pl.Expr:
    if isinstance(value, str):
        return pl.col(value)
    if isinstance(value, pl.Series):
        return pl.lit(value)
    return value
