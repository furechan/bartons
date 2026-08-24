"""Price transforms — OHLC combinations, native polars composition.

None of these has a kernel behind it. Each is an elementwise, stateless
reduction that polars already computes vectorized, so they live entirely at the
expression layer; see `Elementwise reductions stay out of Rust
<../../../docs/architecture.md>`_. They are the single definition of their
formulas — :func:`~bartons.indicators.CCI` takes :func:`TYPPRICE` as its default
``src`` rather than restating it.

Grouped in one module, unlike the kernel-backed indicators which get a file
each, because they share one shape and are one line apiece. Mirrors bearta's
``indicators/lib/price.py``.

Naming follows TA-Lib rather than bearta and mintalib, which call ``(high +
low) / 2`` *midprice*. TA-Lib uses ``MEDPRICE`` for that and reserves
``MIDPRICE`` for the rolling midpoint of the highest high and lowest low over a
period — a different indicator. Since bartons is benchmarked against both
libraries, the unambiguous name wins, and ``MIDPRICE`` stays free for the
indicator TA-Lib gives it to.
"""

import polars as pl

from ...prelude import wrap_indicator
from ...typing import IntoExprColumn, into_expr

__all__ = ("AVGPRICE", "MEDPRICE", "TYPPRICE", "WCLPRICE")


@wrap_indicator
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


@wrap_indicator
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


@wrap_indicator
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


@wrap_indicator
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
