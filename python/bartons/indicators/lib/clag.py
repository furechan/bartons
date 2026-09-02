import polars as pl
from polars.plugins import register_plugin_function

from ...support import PLUGIN_PATH, expression_factory
from ...typing import IntoExprColumn

__all__ = ("CLAG",)


@expression_factory(positional_src=True)
def CLAG(period: int = 1, *, src: IntoExprColumn = "close") -> pl.Expr:
    """Hold the last confirmed discrete state until a candidate repeats.

    A new state is accepted after its first observation plus ``period`` repeats.
    A zero period passes every value through unchanged.
    This is intended for discrete positions such as ``-1``, ``0``, ``0.5``, and
    ``1``, not noisy continuous measurements. Null and NaN inputs emit
    themselves without changing confirmation state.

    Args:
        period: required repeats after the first observation; zero is identity.
        src: discrete state column expression or name; defaults to ``"close"``.
    """
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="clag_expr",
        is_elementwise=False,
        kwargs=dict(period=period),
    )
