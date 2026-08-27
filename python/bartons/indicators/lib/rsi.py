import polars as pl

from polars.plugins import register_plugin_function

from ...support import PLUGIN_PATH, expression_factory
from ...typing import IntoExprColumn

__all__ = ("RSI",)


@expression_factory(positional_src=True)
def RSI(period: int, *, src: IntoExprColumn = "close") -> pl.Expr:
    """Wilder's Relative Strength Index.

    Bar-to-bar gains and losses are each smoothed with a Wilder average
    (``alpha = 1 / period``), then ``RSI = 100 * avg_gain / (avg_gain +
    avg_loss)``. A flat run (no gains or losses) yields ``0``, matching TA-Lib.

    Args:
        period: averaging period (conventionally 14).
        src: input column expression; defaults to ``pl.col("close")``.
            A column name string is also accepted.
    """
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="rsi_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
