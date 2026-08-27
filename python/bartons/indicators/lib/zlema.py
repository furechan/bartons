import polars as pl

from polars.plugins import register_plugin_function

from ...support import PLUGIN_PATH, expression_factory
from ...typing import IntoExprColumn

__all__ = ("ZLEMA",)


@expression_factory(positional_src=True)
def ZLEMA(period: int, *, src: IntoExprColumn = "close") -> pl.Expr:
    """Zero-lag EMA using lag ``(period - 1) // 2``."""
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="zlema_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
