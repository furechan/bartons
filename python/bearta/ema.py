import polars as pl
from pathlib import Path

from polars.plugins import register_plugin_function

from .typing import IntoExprColumn

PLUGIN_PATH = Path(__file__).parent


def EMA(expr: IntoExprColumn, *, period: int) -> pl.Expr:
    return register_plugin_function(
        args=[expr],
        plugin_path=PLUGIN_PATH,
        function_name="ema_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
