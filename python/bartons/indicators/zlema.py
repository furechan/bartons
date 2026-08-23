import polars as pl

from polars.plugins import register_plugin_function

from ..prelude import PLUGIN_PATH, wrap_src_indicator
from ..typing import IntoExprColumn


@wrap_src_indicator
def ZLEMA(period: int, *, src: IntoExprColumn | None = None) -> pl.Expr:
    """Zero-lag EMA using lag ``(period - 1) // 2``."""
    if src is None:
        src = pl.col("close")
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="zlema_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
