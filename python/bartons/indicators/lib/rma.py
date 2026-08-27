import polars as pl

from polars.plugins import register_plugin_function

from ...support import PLUGIN_PATH, expression_factory
from ...typing import IntoExprColumn

__all__ = ("RMA",)


@expression_factory(positional_src=True)
def RMA(period: int, *, src: IntoExprColumn = "close") -> pl.Expr:
    """Wilder's moving average (RSI-style smoothing).

    Exponential average with ``alpha = 1 / period``, seeded with the simple
    average of the first ``period`` values.

    Args:
        period: averaging period.
        src: input column expression; defaults to ``pl.col("close")``.
            A column name string is also accepted.
    """
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="rma_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
