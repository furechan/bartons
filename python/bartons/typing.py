import sys
import polars as pl

from typing import Union

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias
from polars.datatypes import DataType, DataTypeClass

IntoExprColumn: TypeAlias = Union[pl.Expr, str, pl.Series]
PolarsDataType: TypeAlias = Union[DataType, DataTypeClass]


def into_expr(value: IntoExprColumn) -> pl.Expr:
    """Convert a column name, Series, or expression into a Polars expression."""
    if isinstance(value, str):
        return pl.col(value)
    if isinstance(value, pl.Series):
        return pl.lit(value)
    return value
