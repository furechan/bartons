import polars as pl

from polars.plugins import register_plugin_function

from ..prelude import PLUGIN_PATH, wrap_src_indicator
from ..typing import IntoExprColumn


@wrap_src_indicator
def EMA(period: int, *, src: IntoExprColumn | None = None) -> pl.Expr:
    """Exponential moving average.

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
        function_name="ema_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
