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

# Keep implementation modules under ``lib`` so their module objects do not land
# in this facade namespace. Public imports remain ``from bartons.indicators
# import EMA``.
from .lib.adl import *
from .lib.alma import *
from .lib.atr import *
from .lib.bbands import *
from .lib.bop import *
from .lib.cci import *
from .lib.cmf import *
from .lib.dema import *
from .lib.dmi import *
from .lib.donchian import *
from .lib.ema import *
from .lib.hma import *
from .lib.kama import *
from .lib.ker import *
from .lib.keltner import *
from .lib.linreg import *
from .lib.macd import *
from .lib.mad import *
from .lib.mfi import *
from .lib.obv import *
from .lib.price import *
from .lib.ppo import *
from .lib.quadreg import *
from .lib.rma import *
from .lib.roc import *
from .lib.rsi import *
from .lib.sar import *
from .lib.sma import *
from .lib.stoch import *
from .lib.streak import *
from .lib.tema import *
from .lib.trange import *
from .lib.wma import *
from .lib.zlema import *

__all__ = [  # pyright: ignore[reportUnsupportedDunderAll]
    name
    for name, obj in vars().items()
    if getattr(obj, "__module__", "").startswith(f"{__name__}.lib.")
]
