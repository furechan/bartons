import polars as pl
from polars.plugins import register_plugin_function

from ...support import PLUGIN_PATH, expression_factory
from ...typing import IntoExprColumn

__all__ = ("STREAK",)


@expression_factory
def STREAK(src: IntoExprColumn) -> pl.Expr:
    """Count consecutive true values.

    ``true`` increments the count; ``false`` and null reset it to zero. The
    source must be Boolean, making direction an explicit composition such as
    ``STREAK(pl.col("close").diff() > 0)``.

    Args:
        src: Boolean column expression or name.
    """
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="streak_expr",
        is_elementwise=False,
    )
