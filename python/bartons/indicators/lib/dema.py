import polars as pl

from polars.plugins import register_plugin_function

from ...support import PLUGIN_PATH, expression_factory
from ...typing import IntoExprColumn

__all__ = ("DEMA",)


@expression_factory(positional_src=True)
def DEMA(period: int, *, src: IntoExprColumn = "close") -> pl.Expr:
    """Double exponential moving average: ``2*EMA(src)-EMA(EMA(src))``."""
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="dema_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
