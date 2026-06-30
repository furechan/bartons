import polars as pl

from polars.plugins import register_plugin_function

from . import PLUGIN_PATH
from ..typing import IntoExprColumn


def SMA(period: int, *, src: IntoExprColumn | None = None) -> pl.Expr:
    """Simple moving average.

    Args:
        period: averaging period.
        src: input column expression; defaults to ``pl.col("close")``.
            A column name string is also accepted.
    """
    if src is None:
        src = pl.col("close")

    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="sma_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
