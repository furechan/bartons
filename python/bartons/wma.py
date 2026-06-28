import polars as pl
from pathlib import Path

from polars.plugins import register_plugin_function

from .typing import IntoExprColumn

PLUGIN_PATH = Path(__file__).parent


def WMA(period: int, *, src: IntoExprColumn | None = None) -> pl.Expr:
    """Weighted moving average (linear weights).

    Each window value is weighted by its recency: the oldest gets weight 1 and
    the newest gets weight ``period``, divided by ``period*(period+1)/2``.

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
        function_name="wma_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
