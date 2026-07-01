import polars as pl

from . import expressions as xp


@pl.api.register_expr_namespace("bt")
class BartonsExprNamespace:
    def __init__(self, expr: pl.Expr):
        self._expr = expr

    def ema(self, period: int) -> pl.Expr:
        return xp.EMA(period, src=self._expr)

    def sma(self, period: int) -> pl.Expr:
        return xp.SMA(period, src=self._expr)

    def rma(self, period: int) -> pl.Expr:
        return xp.RMA(period, src=self._expr)

    def wma(self, period: int) -> pl.Expr:
        return xp.WMA(period, src=self._expr)

    def rsi(self, period: int) -> pl.Expr:
        return xp.RSI(period, src=self._expr)
