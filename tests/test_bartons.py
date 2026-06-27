import polars as pl

import bartons  # noqa: F401  (importing registers the `bt` expression namespace)
from bartons import plugin


def test_plugin_importable_and_versioned():
    assert isinstance(plugin.__version__, str)
    assert plugin.__version__


def test_bt_namespace_registered():
    # Importing bartons registers the "bt" expression namespace.
    expr = pl.col("x").bt.ema(period=2)
    assert isinstance(expr, pl.Expr)
