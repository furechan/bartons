import polars as pl

from ...support import expression_factory
from ...typing import IntoExprColumn, into_expr

__all__ = ("OBV",)


@expression_factory
def OBV(
    *,
    close: IntoExprColumn = "close",
    volume: IntoExprColumn = "volume",
) -> pl.Expr:
    """On-Balance Volume.

    Volume is multiplied by the sign of the close change and cumulatively
    summed. The first row and incomplete changes are null; accumulation resumes
    afterward without resetting.

    Args:
        close: close column expression or name.
        volume: volume column expression or name.
    """
    close = into_expr(close).cast(pl.Float64)
    volume = into_expr(volume).cast(pl.Float64)
    return volume.mul(close.diff().sign()).cum_sum()
