import polars as pl
import pytest

from helpers import assert_series_equal

from bartons import kernels
from bartons.indicators import AROON, AROONOSC


def ref_aroon(highs, lows, period):
    window = []
    down, up = [], []
    factor = 100.0 / period
    for high, low in zip(highs, lows):
        if high is None or low is None:
            window.clear()
            down.append(None)
            up.append(None)
            continue
        window.append((high, low))
        if len(window) > period + 1:
            window.pop(0)
        if len(window) < period + 1:
            down.append(None)
            up.append(None)
            continue

        highest = max(index for index, row in enumerate(window) if row[0] == max(x[0] for x in window))
        lowest = max(index for index, row in enumerate(window) if row[1] == min(x[1] for x in window))
        down.append(factor * lowest)
        up.append(factor * highest)
    return down, up


HIGHS = [10.0, 12.0, 11.0, 12.0, 9.0, 8.0, 13.0, 12.0]
LOWS = [8.0, 9.0, 7.0, 8.0, 6.0, 5.0, 7.0, 6.0]


def test_aroon_expression_and_eager_match_reference():
    period = 3
    frame = pl.DataFrame({"high": HIGHS, "low": LOWS})
    expression = frame.select(AROON(period)).unnest("aroon")
    eager = kernels.aroon(frame["high"], frame["low"], period=period).struct.unnest()
    down, up = ref_aroon(HIGHS, LOWS, period)

    assert_series_equal(expression["aroondown"], pl.Series("aroondown", down))
    assert_series_equal(expression["aroonup"], pl.Series("aroonup", up))
    assert expression.equals(eager)


def test_aroonosc_is_up_minus_down():
    frame = pl.DataFrame({"high": HIGHS, "low": LOWS})
    fields = frame.select(AROON(3)).unnest("aroon")
    expected = (fields["aroonup"] - fields["aroondown"]).rename("aroonosc")

    assert_series_equal(frame.select(AROONOSC(3))["aroonosc"], expected)


def test_aroon_accepts_custom_inputs_and_resets_on_null():
    frame = pl.DataFrame(
        {
            "h": [3.0, 2.0, 1.0, None, 2.0, 3.0, 4.0],
            "l": [1.0, 0.0, -1.0, 0.0, 1.0, 2.0, 3.0],
        }
    )
    got = frame.select(AROON(2, high="h", low="l")).unnest("aroon")
    down, up = ref_aroon(frame["h"], frame["l"], 2)
    assert_series_equal(got["aroondown"], pl.Series("aroondown", down))
    assert_series_equal(got["aroonup"], pl.Series("aroonup", up))


def test_aroon_returns_named_struct():
    frame = pl.DataFrame({"high": HIGHS, "low": LOWS})
    expression = AROON(3)
    assert expression.meta.output_name() == "aroon"
    assert frame.select(expression).schema["aroon"] == pl.Struct(
        {"aroondown": pl.Float64, "aroonup": pl.Float64}
    )


@pytest.mark.parametrize("period", [0, 1, -1])
def test_aroon_rejects_period_below_two(period):
    values = pl.Series([1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="period must be >= 2"):
        kernels.aroon(values, values, period=period)
