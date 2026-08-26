import polars as pl
import pytest

from helpers import assert_series_equal

from bartons.indicators import CMO
from refimpl import ref_cmo


VALUES = [10.0, 11.0, 10.5, 12.0, 11.0, 13.0, 12.5, 14.0, 13.0, 15.0]


@pytest.mark.parametrize(
    "values",
    [VALUES, VALUES[:5] + [None] + VALUES[6:]],
)
def test_cmo_matches_original_rolling_reference(values):
    frame = pl.DataFrame({"close": pl.Series(values, dtype=pl.Float64)})
    got = frame.select(CMO(3))["cmo"]
    want = pl.Series("cmo", ref_cmo(values, 3), dtype=pl.Float64)
    assert_series_equal(got, want, check_exact=False, rel_tol=1e-12)


def test_cmo_extremes_and_flat_window():
    assert pl.DataFrame({"close": [1.0, 2.0, 3.0, 4.0]}).select(CMO(3))["cmo"][3] == 100.0
    assert pl.DataFrame({"close": [4.0, 3.0, 2.0, 1.0]}).select(CMO(3))["cmo"][3] == -100.0
    assert pl.DataFrame({"close": [1.0, 1.0, 1.0, 1.0]}).select(CMO(3))["cmo"][3] == 0.0


def test_cmo_source_forms_and_name():
    frame = pl.DataFrame({"price": VALUES})
    by_name = frame.select(CMO(3, src="price"))
    by_expr = frame.select(CMO(3, src=pl.col("price")))
    by_pipe = frame.select(pl.col("price").pipe(CMO, 3))
    assert by_name.equals(by_expr)
    assert by_name.equals(by_pipe)
    assert by_name.columns == ["cmo"]
    assert by_name.schema == {"cmo": pl.Float64}


@pytest.mark.parametrize("period", [0, -1])
def test_cmo_rejects_nonpositive_period(period):
    with pytest.raises(ValueError, match="period"):
        CMO(period)
