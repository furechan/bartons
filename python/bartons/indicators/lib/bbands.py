"""Bollinger Bands expressions composed from native Polars windows."""

import polars as pl

from ...prelude import wrap_src_indicator
from ...typing import IntoExprColumn, into_expr

__all__ = ("BBANDS", "BBP", "BBW")


def _bands(
    src: pl.Expr, period: int, nbdev: float
) -> tuple[pl.Expr, pl.Expr, pl.Expr]:
    if period <= 0:
        raise ValueError("period must be greater than zero")
    middle = src.rolling_mean(period, min_samples=period)
    deviation = src.rolling_std(period, min_samples=period, ddof=0) * nbdev
    return middle + deviation, middle, middle - deviation


@wrap_src_indicator
def BBANDS(
    period: int = 20,
    nbdev: float = 2.0,
    *,
    src: IntoExprColumn | None = None,
) -> pl.Expr:
    """Bollinger Bands as an upper, middle, and lower band struct.

    The bands use population standard deviation, matching the conventional
    technical-analysis definition.

    Args:
        period: rolling window length.
        nbdev: number of standard deviations on either side of the mean.
        src: input column expression or name; defaults to ``close``.
    """
    source = into_expr("close" if src is None else src)
    upper, middle, lower = _bands(source, period, nbdev)
    return pl.struct(
        upper.alias("upperband"),
        middle.alias("middleband"),
        lower.alias("lowerband"),
    )


@wrap_src_indicator
def BBP(
    period: int = 20,
    nbdev: float = 2.0,
    *,
    src: IntoExprColumn | None = None,
) -> pl.Expr:
    """Bollinger Percent B: source position within the lower/upper bands."""
    source = into_expr("close" if src is None else src)
    upper, _, lower = _bands(source, period, nbdev)
    return (source - lower) / (upper - lower)


@wrap_src_indicator
def BBW(
    period: int = 20,
    nbdev: float = 2.0,
    *,
    src: IntoExprColumn | None = None,
) -> pl.Expr:
    """Bollinger BandWidth: band width relative to the middle band."""
    source = into_expr("close" if src is None else src)
    upper, middle, lower = _bands(source, period, nbdev)
    return (upper - lower) / middle
