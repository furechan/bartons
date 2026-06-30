import polars as pl
from pathlib import Path

from polars.plugins import register_plugin_function

from .typing import IntoExprColumn

PLUGIN_PATH = Path(__file__).parent


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
