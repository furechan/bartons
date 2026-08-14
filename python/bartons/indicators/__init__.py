"""Polars expression factories for the bartons indicators.

Each factory builds a ``pl.Expr`` that calls the compiled plugin, e.g.::

    from bartons.indicators import EMA, RSI, ATR

The compiled plugin (``plugin.abi3.so``) lives in the parent ``bartons`` package
directory, so ``PLUGIN_PATH`` points there and is shared by every factory.

Single-source factories are wrapped with :func:`wrap_src_expression` so they
also take their source column as the leading positional argument, which makes
them compose with :meth:`polars.Expr.pipe`::

    pl.col("close").pipe(EMA, 5).pipe(RSI, 14)
"""

import functools
import inspect
from pathlib import Path

import polars as pl

PLUGIN_PATH = Path(__file__).parent.parent


def wrap_src_expression(factory):
    """Expression-factory decorator: route a leading ``pl.Expr`` to ``src``.

    The native signature is ``FACTORY(period, *, src=...)``. When the first
    positional argument is a ``pl.Expr`` it is passed as ``src`` instead, so the
    factory composes with :meth:`polars.Expr.pipe`::

        pl.col("close").pipe(EMA, 5)   ==   EMA(5, src=pl.col("close"))

    Any other leading argument (e.g. an ``int`` period) passes through unchanged,
    so ``EMA(5)`` and ``EMA(5, src=...)`` keep working. Adapted from bearta's
    ``wrap_expression``.

    Raises:
        TypeError: at decoration time if `factory` has no `src` parameter to
            route the leading expression into.
    """
    if "src" not in inspect.signature(factory).parameters:
        raise TypeError(
            f"@wrap_src_expression requires {getattr(factory, '__name__', factory)!r} "
            f"to accept a `src` keyword argument"
        )

    @functools.wraps(factory)
    def wrapper(*args, **kwargs):
        if args and isinstance(args[0], pl.Expr):
            if "src" in kwargs:
                raise ValueError(
                    "cannot pass `src` as a keyword when the first positional "
                    "argument is already a polars expression"
                )
            kwargs["src"] = args[0]
            args = args[1:]
        return factory(*args, **kwargs)

    return wrapper


from .ema import EMA
from .sma import SMA
from .rma import RMA
from .wma import WMA
from .rsi import RSI
from .trange import TRANGE
from .atr import ATR

__all__ = ["EMA", "SMA", "RMA", "WMA", "RSI", "TRANGE", "ATR"]
