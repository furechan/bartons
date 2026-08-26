import polars as pl

from polars.plugins import register_plugin_function

from ...prelude import PLUGIN_PATH, wrap_src_indicator
from ...typing import IntoExprColumn

__all__ = ("DEMA",)


@wrap_src_indicator
def DEMA(period: int, *, src: IntoExprColumn = "close") -> pl.Expr:
    """Double exponential moving average: ``2*EMA(src)-EMA(EMA(src))``."""
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="dema_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
