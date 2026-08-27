import polars as pl

from polars.plugins import register_plugin_function

from ...support import PLUGIN_PATH, expression_factory
from ...typing import IntoExprColumn

__all__ = ("SUPERTREND",)


@expression_factory
def SUPERTREND(
    period: int = 10,
    multiplier: float = 3.0,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Supertrend line and bullish/bearish direction from one fused kernel.

    Returns one native Polars struct expression with a Float64 ``supertrend``
    field and an Int64 ``direction`` field. Direction is ``1`` while bullish
    and ``-1`` while bearish. Output is null during ATR warmup, then the first
    valid state is bearish, matching TradingView's initialization convention.
    """
    return register_plugin_function(
        args=[high, low, close],
        plugin_path=PLUGIN_PATH,
        function_name="supertrend_expr",
        is_elementwise=False,
        kwargs=dict(period=period, multiplier=multiplier),
    )
