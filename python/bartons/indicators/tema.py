import polars as pl

from polars.plugins import register_plugin_function

from ..prelude import PLUGIN_PATH, wrap_src_indicator
from ..typing import IntoExprColumn

__all__ = ("TEMA",)


@wrap_src_indicator
def TEMA(period: int = 20, *, src: IntoExprColumn | None = None) -> pl.Expr:
    """Triple exponential moving average."""
    if src is None:
        src = pl.col("close")
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="tema_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
