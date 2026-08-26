import polars as pl

from polars.plugins import register_plugin_function

from ...prelude import PLUGIN_PATH, wrap_src_indicator
from ...typing import IntoExprColumn

__all__ = ("MAD",)


@wrap_src_indicator
def MAD(period: int = 20, *, src: IntoExprColumn = "close") -> pl.Expr:
    """Rolling mean absolute deviation.

    For each full window, computes the mean absolute distance from that
    window's arithmetic mean. A null resets the window.
    """
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="mad_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
