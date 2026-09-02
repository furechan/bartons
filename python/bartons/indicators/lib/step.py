import polars as pl
from polars.plugins import register_plugin_function

from ...support import PLUGIN_PATH, expression_factory
from ...typing import IntoExprColumn

__all__ = ("STEP",)


@expression_factory(positional_src=True)
def STEP(threshold: float = 1.0, *, src: IntoExprColumn = "close") -> pl.Expr:
    """Limit the absolute change in a series per row.

    The first valid value seeds the state and emits null. Each later output
    moves from the previous output toward the current input by no more than
    ``threshold``. Null and NaN inputs emit themselves without changing the
    state, so the next finite value resumes from the previous finite output.

    Args:
        threshold: maximum absolute change per row.
        src: input column expression or name; defaults to ``"close"``.
    """
    return register_plugin_function(
        args=[src],
        plugin_path=PLUGIN_PATH,
        function_name="step_expr",
        is_elementwise=False,
        kwargs=dict(threshold=threshold),
    )
