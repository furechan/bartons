import polars as pl

from polars.plugins import register_plugin_function

from ...prelude import PLUGIN_PATH, wrap_src_indicator
from ...typing import IntoExprColumn

__all__ = ("ALMA",)


@wrap_src_indicator
def ALMA(
    period: int = 9,
    offset: float = 0.85,
    sigma: float = 6.0,
    *,
    src: IntoExprColumn = "close",
) -> pl.Expr:
    """Arnaud Legoux Moving Average.

    The Gaussian weights are derived once from ``period``, ``offset`` and
    ``sigma``. ``offset`` positions the Gaussian center within the window;
    ``sigma`` controls its shape.
    """
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="alma_expr",
        is_elementwise=False,
        kwargs=dict(period=period, offset=offset, sigma=sigma),
    )
