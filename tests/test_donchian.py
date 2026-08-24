import polars as pl
import pytest

from helpers import assert_series_equal

from bartons.indicators import DONCHIAN


HIGHS = [10.0, 12.0, 11.0, 14.0, 13.0, 15.0]
LOWS = [8.0, 9.0, 7.0, 10.0, 9.0, 11.0]


def test_donchian_matches_rolling_extrema():
    period = 3
    frame = pl.DataFrame({"high": HIGHS, "low": LOWS})
    got = frame.select(DONCHIAN(period)).unnest("donchian")

    upper = frame["high"].rolling_max(period)
    lower = frame["low"].rolling_min(period)
    middle = (upper + lower) / 2.0
    for name, expected in (
        ("upperband", upper),
        ("middleband", middle),
        ("lowerband", lower),
    ):
        assert_series_equal(got[name], expected.rename(name))


def test_donchian_returns_named_struct():
    frame = pl.DataFrame({"high": HIGHS, "low": LOWS})
    expression = DONCHIAN(3)

    assert expression.meta.output_name() == "donchian"
    assert frame.select(expression).schema["donchian"] == pl.Struct(
        {
            "upperband": pl.Float64,
            "middleband": pl.Float64,
            "lowerband": pl.Float64,
        }
    )


def test_donchian_accepts_custom_inputs():
    frame = pl.DataFrame({"h": HIGHS, "l": LOWS})
    custom = frame.select(DONCHIAN(3, high="h", low="l"))
    default = frame.rename({"h": "high", "l": "low"}).select(DONCHIAN(3))
    assert custom.equals(default)


@pytest.mark.parametrize("period", [0, -1])
def test_donchian_rejects_invalid_period(period):
    with pytest.raises(ValueError, match="period must be greater than zero"):
        DONCHIAN(period)
