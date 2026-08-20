"""Shared machinery for the bartons indicator factories.

Holds the pieces every factory in :mod:`bartons.indicators` needs: the
``PLUGIN_PATH`` pointing at the compiled plugin (``kernels.abi3.so``, which sits
in this package directory), and the :func:`wrap_src_indicator` decorator.

Mirrors ``bearta.prelude``, which plays the same role there.
"""

import functools
import inspect
from pathlib import Path
from typing import Callable, ParamSpec, Protocol, TypeVar, cast, overload

import polars as pl

from .bundle import ExprBundle

__all__ = [
    "ExprBundle",
    "PLUGIN_PATH",
    "SrcIndicator",
    "wrap_indicator",
    "wrap_src_indicator",
]

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


def _named(factory: Callable[P, R]) -> Callable[P, R]:
    """Alias a factory's result with its own lowercased name.

    Polars names a plugin or arithmetic expression after its leftmost input
    column, so without this every factory returns a column called ``close`` or
    ``high``: ``with_columns(EMA(20))`` would overwrite the very column it read,
    and ``with_columns(EMA(20), SMA(20))`` would fail as a duplicate name. The
    Rust kernels already name their output — ``kernels.ema`` returns a series
    called ``ema`` — but the expression engine discards that, so the name has to
    be reapplied here.

    The name is the bare factory name, matching the kernels and bearta: two
    parameterizations of one indicator (``EMA(20)`` and ``EMA(50)``) still
    collide and still want an explicit ``.alias``. An outer alias always wins,
    so callers lose nothing.

    An :class:`~bartons.bundle.ExprBundle` is left alone — its members carry
    their own names (``macd``, ``macdsignal``, ``macdhist``) and the bundle has
    no single name to give them. Adapted from bearta's ``_named``.
    """
    name = getattr(factory, "__name__", type(factory).__name__).lower()

    @functools.wraps(factory)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        result = factory(*args, **kwargs)
        if isinstance(result, ExprBundle):
            return result
        # Every factory returns one of the two; the cast states that invariant,
        # which the unbounded `R` cannot.
        return cast(R, cast(pl.Expr, result).alias(name))

    return wrapper


def wrap_indicator(factory: Callable[P, R]) -> Callable[P, R]:
    """Multi-input indicator decorator: name the output after the factory.

    For factories that take their columns as individual keyword arguments
    (TRANGE, ATR, and the price transforms) rather than a single ``src``. A
    factory with a ``src`` parameter belongs to :func:`wrap_src_indicator`,
    which names the output *and* adds the expression-first calling convention.
    Mirrors bearta's ``wrap_indicator``.

    Raises:
        TypeError: at decoration time if `factory` declares a `src` parameter,
            which means the wrong decorator was reached for.
    """
    if "src" in inspect.signature(factory).parameters:
        raise TypeError(
            f"{getattr(factory, '__name__', factory)!r} has a `src` parameter — "
            f"use @wrap_src_indicator"
        )
    return _named(factory)


def wrap_src_indicator(factory: Callable[P, R]) -> SrcIndicator[P, R]:
    """Single-source indicator decorator: name the output, and route ``src``.

    The native signature is ``FACTORY(period, *, src=...)``. When the first
    positional argument is a ``pl.Expr`` it is passed as ``src`` instead, so the
    factory composes with :meth:`polars.Expr.pipe`::

        pl.col("close").pipe(EMA, 5)   ==   EMA(5, src=pl.col("close"))

    Any other leading argument (e.g. an ``int`` period) passes through unchanged,
    so ``EMA(5)`` and ``EMA(5, src=...)`` keep working. The result is also named
    after the factory, via :func:`_named`. Only for factories that declare a
    ``src`` parameter — the multi-input ones take their inputs as individual
    arguments and belong to :func:`wrap_indicator`. Adapted from bearta's
    ``wrap_src_indicator``.

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

    return cast(SrcIndicator[P, R], _named(wrapper))
