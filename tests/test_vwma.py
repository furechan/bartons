import math

import polars as pl
import pytest

from helpers import assert_series_equal

from bartons.indicators import VWMA


def test_vwma_matches_rolling_weighted_average():
    frame = pl.DataFrame(
        {
            "close": [10.0, 12.0, 11.0, 15.0, 14.0],
            "volume": [100, 200, 300, 100, 400],
        }
    )
    got = frame.select(VWMA(3))["vwma"]
    expected = (frame["close"] * frame["volume"]).rolling_sum(3) / frame[
        "volume"
    ].rolling_sum(3)
    assert_series_equal(
        got,
        expected.rename("vwma"),
        check_exact=False,
        rel_tol=1e-12,
    )


def test_vwma_accepts_custom_expressions_and_integer_inputs():
    frame = pl.DataFrame({"price": [10, 12, 14], "size": [1, 2, 3]})
    by_name = frame.select(VWMA(2, src="price", volume="size"))
    by_expr = frame.select(
        VWMA(2, src=pl.col("price"), volume=pl.col("size"))
    )
    assert by_name.equals(by_expr)
    assert by_name.schema["vwma"] == pl.Float64


def test_vwma_supports_expression_first_form():
    frame = pl.DataFrame({"price": [10.0, 12.0, 14.0], "size": [1, 2, 3]})
    via_pipe = frame.select(pl.col("price").pipe(VWMA, 2, volume="size"))
    via_keyword = frame.select(VWMA(2, src=pl.col("price"), volume="size"))
    assert via_pipe.equals(via_keyword)


def test_vwma_requires_complete_non_null_window():
    frame = pl.DataFrame(
        {"close": [10.0, None, 20.0, 30.0], "volume": [1.0, 2.0, 3.0, 4.0]}
    )
    assert frame.select(VWMA(2))["vwma"].to_list() == [None, None, None, 180.0 / 7.0]


def test_vwma_null_price_excludes_its_volume_weight():
    frame = pl.DataFrame(
        {"close": [10.0, None, 20.0], "volume": [1.0, 1_000_000.0, 3.0]}
    )
    got = frame.select(VWMA(2))["vwma"]
    assert got.to_list() == [None, None, None]


def test_vwma_zero_total_volume_follows_float_arithmetic():
    frame = pl.DataFrame({"close": [10.0, 20.0], "volume": [0.0, 0.0]})
    assert math.isnan(frame.select(VWMA(2))["vwma"][-1])


@pytest.mark.parametrize("period", [0, -1])
def test_vwma_rejects_invalid_period(period):
    with pytest.raises(ValueError, match="period must be greater than zero"):
        VWMA(period)
