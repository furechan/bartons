import polars as pl

from polars.plugins import register_plugin_function

from ...support import PLUGIN_PATH, expression_factory
from ...typing import IntoExprColumn

__all__ = ("LINREG", "LINREG_SLOPE", "LINREG_RVALUE", "LINREG_RMSE")


def _linreg(
    period: int,
    output: str,
    offset: int,
    src: IntoExprColumn,
) -> pl.Expr:
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="linreg_expr",
        is_elementwise=False,
        kwargs=dict(period=period, output=output, offset=offset),
    )


@expression_factory(positional_src=True)
def LINREG(
    period: int = 20,
    offset: int = 0,
    *,
    src: IntoExprColumn = "close",
) -> pl.Expr:
    """Rolling linear-regression forecast.

    Args:
        period: regression-window length.
        offset: number of bars beyond the current bar at which to evaluate the line.
        src: input column expression; defaults to ``pl.col("close")``.
    """
    return _linreg(period, "forecast", offset, src)


@expression_factory(positional_src=True)
def LINREG_SLOPE(
    period: int = 20,
    *,
    src: IntoExprColumn = "close",
) -> pl.Expr:
    """Rolling linear-regression slope."""
    return _linreg(period, "slope", 0, src)


@expression_factory(positional_src=True)
def LINREG_RVALUE(
    period: int = 20,
    *,
    src: IntoExprColumn = "close",
) -> pl.Expr:
    """Rolling linear-regression correlation coefficient."""
    return _linreg(period, "rvalue", 0, src)


@expression_factory(positional_src=True)
def LINREG_RMSE(
    period: int = 20,
    *,
    src: IntoExprColumn = "close",
) -> pl.Expr:
    """Typical size of the regression's fitting errors.

    This is the root-mean-square error (RMSE), expressed in the same units as
    the input values.
    """
    return _linreg(period, "rmse", 0, src)
