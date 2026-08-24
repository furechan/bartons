import polars as pl

from bartons.typing import into_expr


def test_into_expr_converts_column_name():
    frame = pl.DataFrame({"x": [1, 2, 3]})
    assert frame.select(into_expr("x")).equals(frame.select(pl.col("x")))


def test_into_expr_converts_series_to_literal():
    series = pl.Series("x", [1, 2, 3])
    assert pl.select(into_expr(series))["x"].equals(series)


def test_into_expr_preserves_expression():
    expression = pl.col("x") + 1
    assert into_expr(expression) is expression
