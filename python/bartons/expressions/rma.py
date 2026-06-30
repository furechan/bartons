import polars as pl

from polars.plugins import register_plugin_function

from . import PLUGIN_PATH, wrap_src_expression
from ..typing import IntoExprColumn


@wrap_src_expression
def RMA(period: int, *, src: IntoExprColumn | None = None) -> pl.Expr:
    """Wilder's moving average (RSI-style smoothing).

    Exponential average with ``alpha = 1 / period``, seeded with the simple
    average of the first ``period`` values.

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
        function_name="rma_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
