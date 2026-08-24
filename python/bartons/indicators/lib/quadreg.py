import polars as pl

from polars.plugins import register_plugin_function

from ...prelude import PLUGIN_PATH, wrap_src_indicator
from ...typing import IntoExprColumn

__all__ = (
    "QUADREG",
    "QUADREG_CURVE",
    "QUADREG_SLOPE",
    "QUADREG_RVALUE",
    "QUADREG_RMSE",
)


def _quadreg(
    period: int,
    output: str,
    offset: int,
    src: IntoExprColumn | None,
) -> pl.Expr:
    if src is None:
        src = pl.col("close")
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="quadreg_expr",
        is_elementwise=False,
        kwargs=dict(period=period, output=output, offset=offset),
    )


@wrap_src_indicator
def QUADREG(
    period: int = 20,
    offset: int = 0,
    *,
    src: IntoExprColumn | None = None,
) -> pl.Expr:
    """Rolling quadratic-regression forecast.

    Args:
        period: regression-window length.
        offset: number of bars beyond the current bar at which to evaluate the curve.
        src: input column expression; defaults to ``pl.col("close")``.
    """
    return _quadreg(period, "forecast", offset, src)


@wrap_src_indicator
def QUADREG_CURVE(
    period: int = 20,
    *,
    src: IntoExprColumn | None = None,
) -> pl.Expr:
    """Quadratic coefficient of the rolling regression parabola."""
    return _quadreg(period, "curve", 0, src)


@wrap_src_indicator
def QUADREG_SLOPE(
    period: int = 20,
    offset: int = 0,
    *,
    src: IntoExprColumn | None = None,
) -> pl.Expr:
    """Tangent slope of the rolling regression parabola.

    Args:
        period: regression-window length.
        offset: number of bars beyond the current bar at which to evaluate the slope.
        src: input column expression; defaults to ``pl.col("close")``.
    """
    return _quadreg(period, "slope", offset, src)


@wrap_src_indicator
def QUADREG_RVALUE(
    period: int = 20,
    *,
    src: IntoExprColumn | None = None,
) -> pl.Expr:
    """Partial correlation of the quadratic term given the linear term."""
    return _quadreg(period, "rvalue", 0, src)


@wrap_src_indicator
def QUADREG_RMSE(
    period: int = 20,
    *,
    src: IntoExprColumn | None = None,
) -> pl.Expr:
    """Root-mean-square error of the rolling quadratic fit."""
    return _quadreg(period, "rmse", 0, src)
