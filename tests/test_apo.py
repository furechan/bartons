import polars as pl
import pytest

from helpers import assert_series_equal

from bartons.indicators import APO, MA


VALUES = [float(value) for value in range(1, 41)]


@pytest.mark.parametrize("matype", ["sma", "ema", "wma", "dema", "tema", "kama"])
def test_apo_matches_generic_ma_difference(matype):
    frame = pl.DataFrame({"close": VALUES})
    got = frame.select(APO(3, 5, matype=matype))["apo"]
    expected = frame.select(
        (MA(3, matype=matype) - MA(5, matype=matype)).alias("apo")
    )["apo"]
    assert_series_equal(got, expected)


def test_apo_defaults_to_ema():
    frame = pl.DataFrame({"close": VALUES})
    assert frame.select(APO(3, 5)).equals(
        frame.select(APO(3, 5, matype="ema"))
    )


def test_apo_accepts_custom_source_and_expression_first_form():
    frame = pl.DataFrame({"x": VALUES})
    keyword = frame.select(APO(3, 5, src="x"))
    expression_first = frame.select(APO(pl.col("x"), 3, 5))
    assert keyword.equals(expression_first)


def test_apo_rejects_positional_matype():
    with pytest.raises(TypeError):
        APO(3, 5, "sma")  # type: ignore  # intentionally invalid call shape
