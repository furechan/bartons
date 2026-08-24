import polars as pl
from helpers import assert_series_equal

from bartons.indicators import OBV


def ref_obv(closes, volumes):
    result = []
    previous = None
    total = 0.0
    for close, volume in zip(closes, volumes):
        if close is None or volume is None or previous is None:
            result.append(None)
            previous = close
            continue
        if close > previous:
            total += volume
        elif close < previous:
            total -= volume
        previous = close
        result.append(total)
    return result


def test_obv_expression_matches_reference():
    closes = [10.0, 11.0, 11.0, 9.0, None, 10.0, 12.0, 11.0]
    volumes = [100, 200, 300, 400, 500, 50, 60, 70]
    frame = pl.DataFrame({"close": closes, "volume": volumes})

    expression = frame.select(OBV())["obv"]
    expected = pl.Series("obv", ref_obv(closes, volumes))

    assert expression.dtype == pl.Float64
    assert_series_equal(expression, expected)


def test_obv_accepts_custom_inputs_and_ignores_missing_contributions():
    frame = pl.DataFrame(
        {
            "c": [1.0, 2.0, 3.0, 2.0],
            "v": [10, 20, None, 40],
        }
    )

    got = frame.select(OBV(close="c", volume="v"))["obv"]
    expected = pl.Series("obv", [None, 20.0, None, -20.0])
    assert_series_equal(got, expected)


def test_obv_runs_independently_over_groups():
    frame = pl.DataFrame(
        {
            "ticker": ["a", "b", "a", "b"],
            "close": [1.0, 5.0, 2.0, 4.0],
            "volume": [10, 100, 20, 200],
        }
    )

    got = frame.select(OBV().over("ticker"))["obv"]
    assert_series_equal(got, pl.Series("obv", [None, None, 20.0, -200.0]))
