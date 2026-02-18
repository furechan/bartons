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
