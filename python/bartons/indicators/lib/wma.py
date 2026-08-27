import polars as pl

from polars.plugins import register_plugin_function

from ...support import PLUGIN_PATH, expression_factory
from ...typing import IntoExprColumn

__all__ = ("WMA",)


@expression_factory(positional_src=True)
def WMA(period: int, *, src: IntoExprColumn = "close") -> pl.Expr:
    """Weighted moving average (linear weights).

    Each window value is weighted by its recency: the oldest gets weight 1 and
    the newest gets weight ``period``, divided by ``period*(period+1)/2``.

    Args:
        period: averaging period.
        src: input column expression; defaults to ``pl.col("close")``.
            A column name string is also accepted.
    """
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="wma_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
