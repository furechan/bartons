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

from .alma import *
from .atr import *
from .cci import *
from .dema import *
from .dmi import *
from .ema import *
from .hma import *
from .kama import *
from .ker import *
from .linreg import *
from .macd import *
from .mad import *
from .mfi import *
from .price import *
from .quadreg import *
from .rma import *
from .rsi import *
from .sar import *
from .sma import *
from .streak import *
from .tema import *
from .trange import *
from .wma import *
from .zlema import *

__all__ = [  # pyright: ignore[reportUnsupportedDunderAll]
    name for name in dir() if name.isupper()
]
