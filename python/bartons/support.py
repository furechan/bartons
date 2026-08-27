"""Shared support for Bartons expression factories and plugin registration."""

import functools
import inspect
from pathlib import Path
from typing import Callable, Literal, ParamSpec, Protocol, TypeVar, cast, overload

import polars as pl

from .bundle import ExprBundle

__all__ = [
    "ExprBundle",
    "PLUGIN_PATH",
    "PositionalSrcFactory",
    "expression_factory",
]

PLUGIN_PATH = Path(__file__).parent

P = ParamSpec("P")
R = TypeVar("R")
R_co = TypeVar("R_co", covariant=True)


class PositionalSrcFactory(Protocol[P, R_co]):
    """Factory supporting canonical and expression-first call forms."""

    @overload
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R_co: ...
    @overload
    def __call__(self, src: pl.Expr, /, *args: P.args, **kwargs: P.kwargs) -> R_co: ...


@overload
def expression_factory(factory: Callable[P, R], /) -> Callable[P, R]: ...


@overload
def expression_factory(
    *,
    alias: str | None = None,
    positional_src: Literal[False] = False,
) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


@overload
def expression_factory(
    *,
    alias: str | None = None,
    positional_src: Literal[True],
) -> Callable[[Callable[P, R]], PositionalSrcFactory[P, R]]: ...


def expression_factory(
    factory: Callable[P, R] | None = None,
    /,
    *,
    alias: str | None = None,
    positional_src: bool = False,
) -> (
    Callable[P, R]
    | Callable[[Callable[P, R]], Callable[P, R]]
    | Callable[[Callable[P, R]], PositionalSrcFactory[P, R]]
):
    """Name an expression factory's output and optionally route a leading source.

    The bare form derives the output alias from the lowercase function name::

        @expression_factory
        def MIDPRICE(...): ...

    The configured form can override that alias or add an expression-first call
    convention. With ``positional_src=True``, a leading :class:`polars.Expr` is
    removed from the positional arguments and passed as the ``src`` keyword so
    the factory composes with :meth:`polars.Expr.pipe`.
    """

    def decorate(
        target: Callable[P, R],
    ) -> Callable[P, R] | PositionalSrcFactory[P, R]:
        if positional_src and "src" not in inspect.signature(target).parameters:
            raise TypeError(
                f"{getattr(target, '__name__', target)!r} must accept `src` when "
                "positional_src=True"
            )

        output_name = (
            alias
            if alias is not None
            else getattr(target, "__name__", type(target).__name__).lower()
        )

        @functools.wraps(target)
        def wrapper(*args, **kwargs):
            if positional_src and args and isinstance(args[0], pl.Expr):
                if "src" in kwargs:
                    raise ValueError(
                        "cannot pass `src` as a keyword when the first positional "
                        "argument is already a polars expression"
                    )
                kwargs["src"] = args[0]
                args = args[1:]

            result = target(*args, **kwargs)
            if isinstance(result, ExprBundle):
                return result
            return cast(R, cast(pl.Expr, result).alias(output_name))

        if positional_src:
            return cast(PositionalSrcFactory[P, R], wrapper)
        return wrapper

    if factory is not None:
        return decorate(factory)
    return decorate
