import polars as pl

from polars.plugins import register_plugin_function

from ...prelude import PLUGIN_PATH, wrap_indicator
from ...typing import IntoExprColumn

__all__ = ("DMI",)


@wrap_indicator
def DMI(
    period: int = 14,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
    close: IntoExprColumn = "close",
) -> pl.Expr:
    """Directional Movement Index lines from one fused struct kernel.

    Returns one native Polars struct expression with ``adx``, ``pdi``, and
    ``mdi`` fields. Keep the struct intact through grouped computation, then
    unnest the resulting frame when top-level columns are wanted.
    """
    return register_plugin_function(
        args=[high, low, close],
        plugin_path=PLUGIN_PATH,
        function_name="dmi_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
