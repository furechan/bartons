import polars as pl

from polars.plugins import register_plugin_function

from ..prelude import PLUGIN_PATH, wrap_src_indicator
from ..typing import IntoExprColumn

__all__ = ("KER",)


@wrap_src_indicator
def KER(period: int = 10, *, src: IntoExprColumn | None = None) -> pl.Expr:
    """Kaufman Efficiency Ratio.

    The net move over the window divided by the total distance travelled within
    it — ``|value - oldest| / sum(|change|)`` — in ``0..=1``. A value near 1 is a
    clean directional move, near 0 is chop.

    Absolute rather than signed, matching mintalib and TA-Lib. ``KAMA`` reads
    this same kernel for its smoothing constant, so the formula has exactly one
    definition.

    Args:
        period: number of changes in the window.
        src: input column expression; defaults to ``pl.col("close")``.
            A column name string is also accepted.
    """
    if src is None:
        src = pl.col("close")

    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="ker_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
