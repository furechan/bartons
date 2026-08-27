"""Price indicators composed from native Polars expressions.

None of these has a kernel behind it. Polars already provides the elementwise
arithmetic and rolling extrema they need, so they live entirely at the
expression layer. They are the single definition of their formulas —
:func:`~bartons.indicators.CCI` takes :func:`TYPPRICE` as its default ``src``
rather than restating it.

Grouped in one module, unlike the kernel-backed indicators which get a file
each, because they are recognized price transforms or price-range studies that
need only native expressions.

Naming follows TA-Lib rather than bearta and mintalib, which call ``(high +
low) / 2`` *midprice*. TA-Lib uses ``MEDPRICE`` for that and reserves
``MIDPRICE`` for the rolling midpoint of the highest high and lowest low over a
period — a different indicator. Since bartons is benchmarked against both
libraries, the unambiguous names win.
"""

import polars as pl

from ...support import expression_factory
from ...typing import IntoExprColumn, into_expr

__all__ = ("AVGPRICE", "MEDPRICE", "MIDPRICE", "TYPPRICE", "WCLPRICE")


@expression_factory
def AVGPRICE(
    *,
    open: IntoExprColumn = "open",
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Average price — ``(open + high + low + close) / 4``.

    Args:
        open: open column expression or name.
        high: high column expression or name.
        low: low column expression or name.
        close: close column expression or name.
    """
    return (
        into_expr(open) + into_expr(high) + into_expr(low) + into_expr(close)
    ) / 4.0


@expression_factory
def MEDPRICE(
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
) -> pl.Expr:
    """Median price — ``(high + low) / 2``.

    Named for TA-Lib's ``MEDPRICE``; see the module docstring on why this is not
    ``MIDPRICE``.

    Args:
        high: high column expression or name.
        low: low column expression or name.
    """
    return (into_expr(high) + into_expr(low)) / 2.0


@expression_factory
def MIDPRICE(
    period: int = 14,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
) -> pl.Expr:
    """Midpoint of the rolling highest high and lowest low.

    Args:
        period: rolling range period.
        high: high column expression or name.
        low: low column expression or name.
    """
    if period <= 0:
        raise ValueError("period must be greater than zero")

    upper = into_expr(high).rolling_max(period, min_samples=period)
    lower = into_expr(low).rolling_min(period, min_samples=period)
    return upper.add(lower).truediv(2.0)


@expression_factory
def TYPPRICE(
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Typical price — ``(high + low + close) / 3``.

    The default ``src`` of :func:`~bartons.indicators.CCI`.

    Args:
        high: high column expression or name.
        low: low column expression or name.
        close: close column expression or name.
    """
    return (into_expr(high) + into_expr(low) + into_expr(close)) / 3.0


@expression_factory
def WCLPRICE(
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Weighted close price — ``(high + low + 2 * close) / 4``.

    Args:
        high: high column expression or name.
        low: low column expression or name.
        close: close column expression or name.
    """
    return (
        into_expr(high) + into_expr(low) + 2.0 * into_expr(close)
    ) / 4.0
