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
from .cci import CCI

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
    "CCI",
]
