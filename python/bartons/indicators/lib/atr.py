import polars as pl

from polars.plugins import register_plugin_function

from ...prelude import PLUGIN_PATH, wrap_indicator
from ...typing import IntoExprColumn, into_expr

__all__ = ("ATR", "NATR")


@wrap_indicator
def ATR(
    period: int,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Average True Range — Wilder's RMA of the True Range.

    A multi-input indicator: pass the high, low and close columns (names or
    expressions); they default to ``"high"``, ``"low"`` and ``"close"``.

    Args:
        period: smoothing period (conventionally 14).
        high: high column expression or name.
        low: low column expression or name.
        close: close column expression or name.
    """
    return register_plugin_function(
        args=[high, low, close],
        plugin_path=PLUGIN_PATH,
        function_name="atr_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )


@wrap_indicator
def NATR(
    period: int = 14,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Raw fractional Normalized Average True Range.

    ``ATR(period) / close``. The result is a fractional ratio; multiply by 100
    explicitly when percentage points are desired.

    Args:
        period: ATR smoothing period.
        high: high column expression or name.
        low: low column expression or name.
        close: close column expression or name.
    """
    return ATR(period, high=high, low=low, close=close).truediv(into_expr(close))
