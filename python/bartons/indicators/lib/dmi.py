import polars as pl

from polars.plugins import register_plugin_function

from ...support import PLUGIN_PATH, expression_factory
from ...typing import IntoExprColumn

__all__ = ("DMI", "ADX", "PDI", "MDI")


@expression_factory
def DMI(
    period: int = 14,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Directional Movement Index lines from one fused struct kernel.

    Returns one native Polars struct expression with ``adx``, ``pdi``, and
    ``mdi`` fields. Keep the struct intact through grouped computation, then
    unnest the resulting frame when top-level columns are wanted.
    """
    return register_plugin_function(
        args=[high, low, close],
        plugin_path=PLUGIN_PATH,
        function_name="dmi_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )


@expression_factory
def ADX(
    period: int = 14,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Average Directional Index selected from :func:`DMI`."""
    return DMI(period, high=high, low=low, close=close).struct.field("adx")


@expression_factory
def PDI(
    period: int = 14,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Positive Directional Indicator selected from :func:`DMI`."""
    return DMI(period, high=high, low=low, close=close).struct.field("pdi")


@expression_factory
def MDI(
    period: int = 14,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Negative Directional Indicator selected from :func:`DMI`."""
    return DMI(period, high=high, low=low, close=close).struct.field("mdi")
