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

from ..typing import IntoExprColumn

__all__ = ["AVGPRICE", "MEDPRICE", "TYPPRICE", "WCLPRICE"]


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
    return (_expr(open) + _expr(high) + _expr(low) + _expr(close)) / 4.0


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
    return (_expr(high) + _expr(low)) / 2.0


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
    return (_expr(high) + _expr(low) + _expr(close)) / 3.0


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
    return (_expr(high) + _expr(low) + 2.0 * _expr(close)) / 4.0


def _expr(value: IntoExprColumn) -> pl.Expr:
    if isinstance(value, str):
        return pl.col(value)
    if isinstance(value, pl.Series):
        return pl.lit(value)
    return value
