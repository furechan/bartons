import polars as pl

from polars.plugins import register_plugin_function

from ...support import PLUGIN_PATH, expression_factory
from ...typing import IntoExprColumn

__all__ = ("TEMA",)


@expression_factory(positional_src=True)
def TEMA(period: int = 20, *, src: IntoExprColumn = "close") -> pl.Expr:
    """Triple exponential moving average."""
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="tema_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
