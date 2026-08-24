import polars as pl
from polars.plugins import register_plugin_function

from ...prelude import PLUGIN_PATH, wrap_indicator
from ...typing import IntoExprColumn

__all__ = ("AROON", "AROONOSC")


@wrap_indicator
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


@wrap_indicator
def AROONOSC(
    period: int = 14,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
) -> pl.Expr:
    """Aroon Oscillator — Aroon Up minus Aroon Down."""
    aroon = AROON(period, high=high, low=low)
    return aroon.struct.field("aroonup").sub(aroon.struct.field("aroondown"))
