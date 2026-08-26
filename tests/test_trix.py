import polars as pl
import pytest

from helpers import assert_series_equal

from bartons.indicators import TRIX
from refimpl import ref_trix


VALUES = [
    10.0, 11.0, 10.5, 12.0, 13.5, 12.5, 14.0, 15.0, 14.2, 16.0,
    17.0, 16.5, 18.0, 19.5, 18.5, 20.0,
]


@pytest.mark.parametrize("values", [VALUES, VALUES[:7] + [None] + VALUES[8:]])
def test_trix_matches_reference(values):
    frame = pl.DataFrame({"close": pl.Series(values, dtype=pl.Float64)})
    got = frame.select(TRIX(3))["trix"]
    want = pl.Series("trix", ref_trix(values, 3), dtype=pl.Float64)
    assert_series_equal(got, want, check_exact=False, rel_tol=1e-12)


def test_trix_defaults_and_source_forms():
    frame = pl.DataFrame({"close": VALUES, "price": VALUES})
    default = frame.select(TRIX(3))
    by_name = frame.select(TRIX(3, src="price"))
    by_expr = frame.select(TRIX(3, src=pl.col("price")))
    by_pipe = frame.select(pl.col("price").pipe(TRIX, 3))
    assert default.equals(by_name)
    assert by_name.equals(by_expr)
    assert by_name.equals(by_pipe)


def test_trix_returns_named_float_expression():
    expression = TRIX(3)
    assert expression.meta.output_name() == "trix"
    assert pl.DataFrame({"close": VALUES}).select(expression).schema == {
        "trix": pl.Float64
    }


@pytest.mark.parametrize("period", [0, -1])
def test_trix_rejects_nonpositive_period(period):
    with pytest.raises(ValueError, match="period"):
        TRIX(period)
