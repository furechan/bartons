import polars as pl

from polars.plugins import register_plugin_function

from ...prelude import PLUGIN_PATH, wrap_src_indicator
from ...typing import IntoExprColumn

__all__ = ("ZLEMA",)


@wrap_src_indicator
def ZLEMA(period: int, *, src: IntoExprColumn = "close") -> pl.Expr:
    """Zero-lag EMA using lag ``(period - 1) // 2``."""
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="zlema_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
