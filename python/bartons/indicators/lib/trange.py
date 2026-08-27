import polars as pl

from polars.plugins import register_plugin_function

from ...support import PLUGIN_PATH, expression_factory
from ...typing import IntoExprColumn

__all__ = ("TRANGE",)


@expression_factory
def TRANGE(
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """True Range.

    ``TR = max(high - low, |high - prev_close|, |low - prev_close|)``, with the
    first bar using ``high - low``. A multi-input indicator: pass the high, low
    and close columns (names or expressions); they default to ``"high"``,
    ``"low"`` and ``"close"``.
    """
    return register_plugin_function(
        args=[high, low, close],
        plugin_path=PLUGIN_PATH,
        function_name="trange_expr",
        is_elementwise=False,
    )
