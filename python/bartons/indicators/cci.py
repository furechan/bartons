import polars as pl

from polars.plugins import register_plugin_function

from ..prelude import PLUGIN_PATH
from ..typing import IntoExprColumn


def CCI(
    period: int = 20,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Commodity Channel Index.

    ``(typical - SMA(typical)) / (0.015 * MAD(typical))``, where ``typical`` is
    ``(high + low + close) / 3``. A multi-input indicator: pass the high, low
    and close columns (names or expressions); they default to ``"high"``,
    ``"low"`` and ``"close"``.

    The typical price is built as a native polars expression and the kernel
    takes it as its single input, so the SMA and MAD terms share one window
    while only one column crosses the plugin boundary.

    Args:
        period: window length (conventionally 20).
        high: high column expression or name.
        low: low column expression or name.
        close: close column expression or name.
    """
    typical = (_expr(high) + _expr(low) + _expr(close)) / 3.0

    return register_plugin_function(
        args=[typical],
        plugin_path=PLUGIN_PATH,
        function_name="cci_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )


def _expr(value: IntoExprColumn) -> pl.Expr:
    if isinstance(value, str):
        return pl.col(value)
    if isinstance(value, pl.Series):
        return pl.lit(value)
    return value
