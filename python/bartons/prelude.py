"""Shared machinery for the bartons indicator factories.

Holds the pieces every factory in :mod:`bartons.indicators` needs: the
``PLUGIN_PATH`` pointing at the compiled plugin (``plugin.abi3.so``, which sits
in this package directory), and the :func:`wrap_src_indicator` decorator.

Mirrors ``bearta.prelude``, which plays the same role there.
"""

import functools
import inspect
from pathlib import Path
from typing import Callable, ParamSpec, Protocol, TypeVar, cast, overload

import polars as pl

__all__ = ["PLUGIN_PATH", "SrcIndicator", "wrap_src_indicator"]

PLUGIN_PATH = Path(__file__).parent

P = ParamSpec("P")
R = TypeVar("R")
R_co = TypeVar("R_co", covariant=True)


class SrcIndicator(Protocol[P, R_co]):
    """Call signature of a factory wrapped by :func:`wrap_src_indicator`.

    Wrapping is a runtime trick — the decorator returns an untyped ``*args,
    **kwargs`` wrapper — so without this the factories would be opaque to a type
    checker. Declaring the two forms as overloads keeps them checkable::

        EMA(20, src=pl.col("close"))          # canonical
        EMA(pl.col("close"), 20)              # expression-first
        pl.col("close").pipe(EMA, 20)         # and therefore pipe

    Ported from ``bearta.prelude``.
    """

    # Canonical form first — editors list overloads in declaration order, and the
    # params-first signature is the one to show and to prefer when both match.
    @overload
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R_co: ...
    @overload
    def __call__(self, src: pl.Expr, /, *args: P.args, **kwargs: P.kwargs) -> R_co: ...


def wrap_src_indicator(factory: Callable[P, R]) -> SrcIndicator[P, R]:
    """Single-source indicator decorator: route a leading ``pl.Expr`` to ``src``.

    The native signature is ``FACTORY(period, *, src=...)``. When the first
    positional argument is a ``pl.Expr`` it is passed as ``src`` instead, so the
    factory composes with :meth:`polars.Expr.pipe`::

        pl.col("close").pipe(EMA, 5)   ==   EMA(5, src=pl.col("close"))

    Any other leading argument (e.g. an ``int`` period) passes through unchanged,
    so ``EMA(5)`` and ``EMA(5, src=...)`` keep working. Only for factories that
    declare a ``src`` parameter — the multi-input ones (TRANGE, ATR) take their
    inputs as individual arguments and are left undecorated. Adapted from
    bearta's ``wrap_src_indicator``.

    Raises:
        TypeError: at decoration time if `factory` has no `src` parameter to
            route the leading expression into.
    """
    if "src" not in inspect.signature(factory).parameters:
        raise TypeError(
            f"@wrap_src_indicator requires {getattr(factory, '__name__', factory)!r} "
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

    return cast(SrcIndicator[P, R], wrapper)
