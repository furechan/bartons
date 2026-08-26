import polars as pl
import pytest

from helpers import assert_series_equal

from bartons.indicators import ULTOSC
from refimpl import ref_ultosc


HIGHS = [
    12.0, 13.0, 12.5, 14.0, 15.0, 14.5, 16.0, 17.0, 16.5, 18.0,
    19.0, 18.5, 20.0, 21.0, 20.5, 22.0, 23.0, 22.5, 24.0, 25.0,
]
LOWS = [value - 3.0 for value in HIGHS]
CLOSES = [value - offset for value, offset in zip(HIGHS, [1.0, 2.0] * 10)]


def frame(highs=HIGHS, lows=LOWS, closes=CLOSES):
    return pl.DataFrame(
        {
            "high": pl.Series(highs, dtype=pl.Float64),
            "low": pl.Series(lows, dtype=pl.Float64),
            "close": pl.Series(closes, dtype=pl.Float64),
        }
    )


@pytest.mark.parametrize(
    "prices",
    [
        (HIGHS, LOWS, CLOSES),
        (HIGHS[:9] + [None] + HIGHS[10:], LOWS[:9] + [None] + LOWS[10:], CLOSES[:9] + [None] + CLOSES[10:]),
    ],
)
def test_ultosc_matches_reference(prices):
    periods = (3, 5, 7)
    got = frame(*prices).select(ULTOSC(*periods))["ultosc"]
    want = pl.Series(
        "ultosc",
        ref_ultosc(prices[0], prices[1], prices[2], 3, 5, 7),
        dtype=pl.Float64,
    )
    assert_series_equal(got, want, check_exact=False, rel_tol=1e-12)


def test_ultosc_defaults_to_standard_columns_and_accepts_expressions():
    prices = frame().rename({"high": "h", "low": "l", "close": "c"})
    by_name = prices.select(ULTOSC(3, 5, 7, high="h", low="l", close="c"))
    by_expr = prices.select(
        ULTOSC(3, 5, 7, high=pl.col("h"), low=pl.col("l"), close=pl.col("c"))
    )
    assert by_name.equals(by_expr)


def test_ultosc_returns_named_float_expression():
    expression = ULTOSC(3, 5, 7)
    assert expression.meta.output_name() == "ultosc"
    assert frame().select(expression).schema == {"ultosc": pl.Float64}


@pytest.mark.parametrize("periods", [(0, 14, 28), (7, 0, 28), (7, 14, 0)])
def test_ultosc_rejects_nonpositive_periods(periods):
    with pytest.raises(ValueError, match="greater than zero"):
        ULTOSC(*periods)
