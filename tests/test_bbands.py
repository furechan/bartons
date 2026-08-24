import math

import polars as pl
import pytest

from helpers import assert_series_equal

from bartons.indicators import BBANDS, BBP, BBW
from refimpl import ref_bbands


XS = [
    10.0,
    11.0,
    13.0,
    12.0,
    15.0,
    14.0,
    16.0,
    18.0,
    17.0,
    19.0,
]


@pytest.mark.parametrize(
    "xs",
    [
        XS,
        [10.0, 11.0, 12.0, None, 14.0, 15.0, 16.0, 17.0],
        [None, 10.0, 11.0, 12.0, 13.0, 14.0],
    ],
)
def test_bbands_matches_population_reference(xs):
    period, nbdev = 4, 2.0
    frame = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})
    got = frame.select(BBANDS(period, nbdev, src="x")).unnest("bbands")
    expected = ref_bbands(xs, period, nbdev)

    for name, values in zip(("upperband", "middleband", "lowerband"), expected):
        assert_series_equal(
            got[name],
            pl.Series(name, values, dtype=pl.Float64),
            check_exact=False,
            rel_tol=1e-12,
        )


def test_bbp_and_bbw_match_band_components():
    period, nbdev = 4, 2.0
    frame = pl.DataFrame({"x": pl.Series(XS, dtype=pl.Float64)})
    bands = frame.select(BBANDS(period, nbdev, src="x")).unnest("bbands")
    got = frame.select(
        BBP(period, nbdev, src="x"),
        BBW(period, nbdev, src="x"),
    )

    expected_bbp = (frame["x"] - bands["lowerband"]) / (
        bands["upperband"] - bands["lowerband"]
    )
    expected_bbw = (
        bands["upperband"] - bands["lowerband"]
    ) / bands["middleband"]
    assert_series_equal(got["bbp"], expected_bbp.rename("bbp"))
    assert_series_equal(got["bbw"], expected_bbw.rename("bbw"))


def test_bbands_returns_named_struct_and_defaults_to_close():
    frame = pl.DataFrame({"close": pl.Series(XS, dtype=pl.Float64)})
    expression = BBANDS(4)

    assert expression.meta.output_name() == "bbands"
    assert frame.select(expression).schema["bbands"] == pl.Struct(
        {
            "upperband": pl.Float64,
            "middleband": pl.Float64,
            "lowerband": pl.Float64,
        }
    )


@pytest.mark.parametrize("factory", [BBANDS, BBP, BBW])
def test_bollinger_expression_first_form(factory):
    frame = pl.DataFrame({"x": pl.Series(XS, dtype=pl.Float64)})
    positional = frame.select(factory(pl.col("x"), 4, 2.0))
    keyword = frame.select(factory(4, 2.0, src=pl.col("x")))
    assert positional.equals(keyword)


@pytest.mark.parametrize("factory", [BBANDS, BBP, BBW])
def test_bollinger_rejects_zero_period(factory):
    frame = pl.DataFrame({"close": pl.Series(XS, dtype=pl.Float64)})
    with pytest.raises((ValueError, pl.exceptions.PolarsError)):
        frame.select(factory(0))


def test_flat_window_has_nan_percent_b():
    got = pl.DataFrame({"close": [1.0, 1.0, 1.0]}).select(BBP(3))["bbp"][-1]
    assert math.isnan(got)
