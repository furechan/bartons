import polars as pl

from polars.plugins import register_plugin_function

from ..prelude import PLUGIN_PATH, wrap_src_indicator
from ..typing import IntoExprColumn
from .typprice import TYPPRICE


@wrap_src_indicator
def CCI(period: int = 20, *, src: IntoExprColumn | None = None) -> pl.Expr:
    """Commodity Channel Index.

    ``(src - SMA(src)) / (0.015 * MAD(src))``. Conventionally run over typical
    price, which is what ``src`` defaults to, so ``CCI(20)`` on a frame with
    ``high``/``low``/``close`` columns is standard CCI.

    The kernel takes a single series, so nothing here is specific to typical
    price. For other column names, or to run CCI over some other series, pass
    ``src``::

        CCI(20, src=TYPPRICE(high="h", low="l", close="c"))
        pl.col("close").pipe(CCI, 20)

    Args:
        period: window length (conventionally 20).
        src: input column expression; defaults to :func:`TYPPRICE`, i.e.
            ``(high + low + close) / 3``. A column name string is also accepted.
    """
    if src is None:
        src = TYPPRICE()

    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="cci_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
