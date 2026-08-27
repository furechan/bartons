import polars as pl
from polars.plugins import register_plugin_function

from ...support import PLUGIN_PATH, expression_factory
from ...typing import IntoExprColumn

__all__ = ("SAR",)


@expression_factory
def SAR(
    afs: float = 0.02,
    maxaf: float = 0.2,
    *,
    high: IntoExprColumn = "high",
    low: IntoExprColumn = "low",
) -> pl.Expr:
    """Parabolic Stop and Reverse.

    Args:
        afs: starting acceleration factor.
        maxaf: maximum acceleration factor; zero disables the cap.
        high: high column expression or name.
        low: low column expression or name.
    """
    return register_plugin_function(
        args=[high, low],
        plugin_path=PLUGIN_PATH,
        function_name="sar_expr",
        is_elementwise=False,
        kwargs={"afs": afs, "maxaf": maxaf},
    )
