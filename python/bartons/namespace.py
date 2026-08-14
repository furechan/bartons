import polars as pl

from . import indicators as ind


@pl.api.register_expr_namespace("bt")
class BartonsExprNamespace:
    def __init__(self, expr: pl.Expr):
        self._expr = expr

    def ema(self, period: int) -> pl.Expr:
        return ind.EMA(period, src=self._expr)

    def sma(self, period: int) -> pl.Expr:
        return ind.SMA(period, src=self._expr)

    def rma(self, period: int) -> pl.Expr:
        return ind.RMA(period, src=self._expr)

    def wma(self, period: int) -> pl.Expr:
        return ind.WMA(period, src=self._expr)

    def rsi(self, period: int) -> pl.Expr:
        return ind.RSI(period, src=self._expr)
