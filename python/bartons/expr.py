from pathlib import Path

import polars as pl

from polars.plugins import register_plugin_function

PLUGIN_PATH = Path(__file__).parent


@pl.api.register_expr_namespace("bt")
class BartonsExprNamespace:
    def __init__(self, expr: pl.Expr):
        self._expr = expr

    def ema(self, period: int) -> pl.Expr:
        return register_plugin_function(
            function_name="ema_expr",
            plugin_path=PLUGIN_PATH,
            is_elementwise=False,
            args=[self._expr],
            kwargs=dict(period=period),
        )

