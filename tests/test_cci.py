import polars as pl
import pytest

from helpers import assert_series_equal

from bartons.indicators import CCI
from refimpl import ref_cci


HIGHS = [10.0, 12.0, 13.0, 15.0, 14.0, 17.0, 18.0]
LOWS = [8.0, 9.0, 10.0, 11.0, 11.0, 13.0, 15.0]
CLOSES = [9.0, 11.0, 12.0, 14.0, 12.0, 16.0, 17.0]


def test_cci_matches_native_composition_reference():
    frame = pl.DataFrame({"high": HIGHS, "low": LOWS, "close": CLOSES})
    got = frame.select(CCI(3).alias("cci"))["cci"]
    expected = pl.Series("cci", ref_cci(HIGHS, LOWS, CLOSES, 3), dtype=pl.Float64)

    assert_series_equal(got, expected, check_exact=False, rel_tol=1e-12)


def test_cci_custom_inputs_and_null_reset():
    highs = [10.0, 12.0, None, 15.0, 16.0, 17.0]
    lows = [8.0, 9.0, None, 11.0, 12.0, 13.0]
    closes = [9.0, 11.0, None, 14.0, 15.0, 16.0]
    frame = pl.DataFrame({"h": highs, "l": lows, "c": closes})

    got = frame.select(CCI(2, high="h", low="l", close="c").alias("cci"))["cci"]
    expected = pl.Series("cci", ref_cci(highs, lows, closes, 2), dtype=pl.Float64)
    assert_series_equal(got, expected, check_exact=False, rel_tol=1e-12)


def test_cci_accepts_expressions():
    frame = pl.DataFrame({"high": HIGHS, "low": LOWS, "close": CLOSES})
    names = frame.select(CCI(3).alias("cci"))
    expressions = frame.select(
        CCI(3, high=pl.col("high"), low=pl.col("low"), close=pl.col("close")).alias(
            "cci"
        )
    )
    assert names.equals(expressions)


def test_cci_rejects_invalid_period():
    frame = pl.DataFrame({"high": HIGHS, "low": LOWS, "close": CLOSES})
    with pytest.raises(pl.exceptions.PolarsError):
        frame.select(CCI(0))
