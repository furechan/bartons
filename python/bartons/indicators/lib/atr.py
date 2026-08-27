import polars as pl

from polars.plugins import register_plugin_function

from ...support import PLUGIN_PATH, expression_factory
from ...typing import IntoExprColumn, into_expr

__all__ = ("ATR", "NATR")


@expression_factory
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


@expression_factory
def NATR(
    period: int = 14,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Normalized Average True Range in percentage points.

    ``100 * ATR(period) / close``.

    Args:
        period: ATR smoothing period.
        high: high column expression or name.
        low: low column expression or name.
        close: close column expression or name.
    """
    return (
        ATR(period, high=high, low=low, close=close)
        .truediv(into_expr(close))
        .mul(100.0)
    )
