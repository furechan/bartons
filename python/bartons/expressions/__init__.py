"""Polars expression factories for the bartons indicators.

Each factory builds a ``pl.Expr`` that calls the compiled plugin, e.g.::

    from bartons.expressions import EMA, RSI, ATR

The compiled plugin (``plugin.abi3.so``) lives in the parent ``bartons`` package
directory, so ``PLUGIN_PATH`` points there and is shared by every factory.
"""

from pathlib import Path

PLUGIN_PATH = Path(__file__).parent.parent

from .ema import EMA
from .sma import SMA
from .rma import RMA
from .wma import WMA
from .rsi import RSI
from .trange import TRANGE
from .atr import ATR

__all__ = ["EMA", "SMA", "RMA", "WMA", "RSI", "TRANGE", "ATR"]
