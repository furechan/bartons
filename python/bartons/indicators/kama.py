import polars as pl

from polars.plugins import register_plugin_function

from ..prelude import PLUGIN_PATH, wrap_src_indicator
from ..typing import IntoExprColumn

__all__ = ("KAMA",)


@wrap_src_indicator
def KAMA(
    period: int = 10,
    fastn: int = 2,
    slown: int = 30,
    *,
    src: IntoExprColumn | None = None,
) -> pl.Expr:
    """Kaufman Adaptive Moving Average.

    An exponential moving average whose smoothing constant is re-derived every
    bar from the efficiency ratio — ``alpha = (slow + KER * (fast - slow))**2`` —
    so it tracks a clean trend closely and flattens out in chop.

    Args:
        period: number of changes in the efficiency-ratio window.
        fastn: period of the fast smoothing bound.
        slown: period of the slow smoothing bound.
        src: input column expression; defaults to ``pl.col("close")``.
            A column name string is also accepted.
    """
    if src is None:
        src = pl.col("close")

    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="kama_expr",
        is_elementwise=False,
        kwargs=dict(period=period, fastn=fastn, slown=slown),
    )
