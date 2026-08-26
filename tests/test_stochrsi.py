import polars as pl
import pytest

from helpers import assert_series_equal

from bartons.indicators import STOCHRSI
from refimpl import ref_stochrsi


VALUES = [
    44.0, 44.5, 43.8, 45.2, 46.0, 45.4, 47.1, 46.2, 45.0, 43.9,
    44.8, 46.3, 47.5, 48.0, 46.7, 45.5, 44.1, 45.9, 47.2, 48.6,
]


def frame(values=VALUES):
    return pl.DataFrame({"close": pl.Series(values, dtype=pl.Float64)})


@pytest.mark.parametrize(
    "values",
    [VALUES, VALUES[:10] + [None] + VALUES[11:]],
)
def test_stochrsi_matches_reference(values):
    periods = (4, 2, 2)
    got = frame(values).select(STOCHRSI(*periods)).unnest("stochrsi")
    want = ref_stochrsi(values, *periods)
    for name, expected in zip(("fastk", "fastd"), want):
        assert_series_equal(
            got[name],
            pl.Series(name, expected, dtype=pl.Float64),
            check_exact=False,
            rel_tol=1e-12,
        )


def test_stochrsi_returns_named_struct():
    expression = STOCHRSI(4, 2, 2)
    assert expression.meta.output_name() == "stochrsi"
    assert frame().select(expression).schema["stochrsi"] == pl.Struct(
        {"fastk": pl.Float64, "fastd": pl.Float64}
    )


def test_stochrsi_accepts_source_forms():
    prices = frame().rename({"close": "price"})
    by_name = prices.select(STOCHRSI(4, 2, 2, src="price"))
    by_expr = prices.select(STOCHRSI(4, 2, 2, src=pl.col("price")))
    by_pipe = prices.select(pl.col("price").pipe(STOCHRSI, 4, 2, 2))
    assert by_name.equals(by_expr)
    assert by_name.equals(by_pipe)


@pytest.mark.parametrize("periods", [(0, 3, 3), (14, 0, 3), (14, 3, 0)])
def test_stochrsi_rejects_invalid_periods(periods):
    with pytest.raises(ValueError, match="greater than zero"):
        STOCHRSI(*periods)
