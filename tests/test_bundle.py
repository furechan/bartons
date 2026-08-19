import polars as pl
import pytest

from bartons import ExprBundle


def test_members_are_named():
    bundle = ExprBundle("close", px="close", doubled=pl.col("close") * 2)

    assert [expr.meta.output_name() for expr in bundle] == ["close", "px", "doubled"]


def test_bundle_is_flattened_and_scopeable():
    frame = pl.DataFrame({"ticker": ["A", "A", "B", "B"], "x": [1, 2, 3, 4]})
    bundle = ExprBundle(total=pl.col("x").sum()).over("ticker")

    out = frame.with_columns(bundle)
    assert out["total"].to_list() == [3, 3, 7, 7]


def test_concatenation_stays_a_bundle():
    left = ExprBundle(x="x")
    right = ExprBundle(y="y")

    assert isinstance(left + right, ExprBundle)
    assert isinstance(tuple(left) + right, ExprBundle)


def test_concatenation_refuses_strings():
    with pytest.raises(TypeError, match="unsupported operand"):
        ExprBundle(x="x") + "close"  # ty: ignore[unsupported-operator]


def test_as_struct_is_explicit():
    frame = pl.DataFrame({"x": [1, 2]})
    result = frame.select(ExprBundle(x="x", doubled=pl.col("x") * 2).as_struct("pair"))

    assert result.columns == ["pair"]
    assert result["pair"].struct.fields == ["x", "doubled"]
