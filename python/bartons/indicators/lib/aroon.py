import polars as pl
from polars.plugins import register_plugin_function

from ...support import PLUGIN_PATH, expression_factory
from ...typing import IntoExprColumn

__all__ = ("AROON", "AROONOSC")


@expression_factory
def AROON(
    period: int = 14,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
) -> pl.Expr:
    """Aroon Down and Up as one native Polars struct expression."""
    return register_plugin_function(
        args=[high, low],
        plugin_path=PLUGIN_PATH,
        function_name="aroon_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )


@expression_factory
def AROONOSC(
    period: int = 14,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
) -> pl.Expr:
    """Aroon Oscillator — Aroon Up minus Aroon Down."""
    aroon = AROON(period, high=high, low=low)
    return aroon.struct.field("aroonup").sub(aroon.struct.field("aroondown"))
