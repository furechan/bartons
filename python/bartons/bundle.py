"""Experimental expression bundles: named packs for Polars frame contexts."""

import warnings
from collections.abc import Iterable
from typing import TypeAlias

import polars as pl

__all__ = ("ExprBundle", "IntoExpr")

IntoExpr: TypeAlias = pl.Expr | str


class ExprBundle(tuple[pl.Expr, ...]):
    """Experimental group of named expressions destined for one frame context.

    Shipped multi-output indicators use native Struct expressions instead. This
    utility remains available for evaluating the tuple-based alternative::

        pair = ExprBundle(left=pl.col("a"), right=pl.col("b"))
        frame.select(pair)
    """

    def __new__(cls, *args: IntoExpr, **kwargs: IntoExpr) -> "ExprBundle":
        items = tuple(_to_expr(arg) for arg in args)
        items += tuple(_to_expr(arg).alias(name) for name, arg in kwargs.items())
        return super().__new__(cls, items)

    def over(self, by: IntoExpr | Iterable[IntoExpr]) -> "ExprBundle":
        """Apply the same window partition to every member."""
        return ExprBundle(*(expr.over(by) for expr in self))

    def as_struct(self, name: str | None = None) -> pl.Expr:
        """Explicitly pack the members into one struct expression."""
        struct = pl.struct(self)
        return struct.alias(name) if name is not None else struct

    @property
    def struct(self):
        """Compatibility bridge for struct-era call sites."""
        warnings.warn(
            "ExprBundle is experimental — pass the bundle directly, "
            "or use .as_struct() when you want a record column",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.as_struct().struct

    def __add__(self, other: Iterable[pl.Expr]) -> "ExprBundle":
        if isinstance(other, str) or not isinstance(other, Iterable):
            return NotImplemented
        return ExprBundle(*self, *other)

    def __radd__(self, other: Iterable[pl.Expr]) -> "ExprBundle":
        if isinstance(other, str) or not isinstance(other, Iterable):
            return NotImplemented
        return ExprBundle(*other, *self)


def _to_expr(value: IntoExpr) -> pl.Expr:
    return pl.col(value) if isinstance(value, str) else value
