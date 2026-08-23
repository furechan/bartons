import polars as pl

from polars.plugins import register_plugin_function

from ..prelude import PLUGIN_PATH, wrap_src_indicator
from ..typing import IntoExprColumn
from .price import TYPPRICE


@wrap_src_indicator
def MFI(
    period: int = 14,
    *,
    src: IntoExprColumn | None = None,
    volume: IntoExprColumn = "volume",
) -> pl.Expr:
    """Money Flow Index.

    Conventionally run over typical price, which is what ``src`` defaults to.
    The kernel itself takes a price source and volume, so a custom source can be
    supplied directly or through ``Expr.pipe``::

        MFI(14, src="close", volume="volume")
        pl.col("close").pipe(MFI, 14, volume="volume")

    Args:
        period: rolling money-flow period.
        src: price source; defaults to :func:`TYPPRICE`.
        volume: volume column expression or name.
    """
    if src is None:
        src = TYPPRICE()

    return register_plugin_function(
        args=[src, volume],
        plugin_path=PLUGIN_PATH,
        function_name="mfi_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
