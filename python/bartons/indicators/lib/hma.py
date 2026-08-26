import polars as pl

from polars.plugins import register_plugin_function

from ...prelude import PLUGIN_PATH, wrap_src_indicator
from ...typing import IntoExprColumn

__all__ = ("HMA",)


@wrap_src_indicator
def HMA(period: int, *, src: IntoExprColumn = "close") -> pl.Expr:
    """Hull moving average using ``period//2`` and ``floor(sqrt(period))``."""
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="hma_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
