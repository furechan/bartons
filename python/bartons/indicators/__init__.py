"""Polars expression factories for the bartons indicators.

Each factory builds a ``pl.Expr`` that calls the compiled plugin, e.g.::

    from bartons.indicators import EMA, RSI, ATR

The shared machinery they build on — ``PLUGIN_PATH`` and the
:func:`~bartons.prelude.wrap_src_indicator` decorator — lives in
:mod:`bartons.prelude`.

Single-source factories are wrapped with
:func:`~bartons.prelude.wrap_src_indicator` so they also take their source
column as the leading positional argument, which makes them compose with
:meth:`polars.Expr.pipe`::

    pl.col("close").pipe(EMA, 5).pipe(RSI, 14)
"""

from .ema import EMA
from .sma import SMA
from .rma import RMA
from .wma import WMA
from .rsi import RSI
from .trange import TRANGE
from .atr import ATR
from .macd import MACD
from .mad import MAD
from .price import AVGPRICE, MEDPRICE, TYPPRICE, WCLPRICE
from .cci import CCI
from .ker import KER
from .kama import KAMA
from .sar import SAR
from .streak import STREAK
from .linreg import LINREG, LINREG_RMSE, LINREG_RVALUE, LINREG_SLOPE
from .quadreg import QUADREG, QUADREG_CURVE, QUADREG_RMSE, QUADREG_RVALUE, QUADREG_SLOPE

__all__ = [
    "EMA",
    "SMA",
    "RMA",
    "WMA",
    "RSI",
    "TRANGE",
    "ATR",
    "MACD",
    "MAD",
    "AVGPRICE",
    "MEDPRICE",
    "TYPPRICE",
    "WCLPRICE",
    "CCI",
    "KER",
    "KAMA",
    "SAR",
    "STREAK",
    "LINREG",
    "LINREG_SLOPE",
    "LINREG_RVALUE",
    "LINREG_RMSE",
    "QUADREG",
    "QUADREG_CURVE",
    "QUADREG_SLOPE",
    "QUADREG_RVALUE",
    "QUADREG_RMSE",
]
