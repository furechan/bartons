import math

import polars as pl
import pytest

from bartons import kernels
from bartons.indicators import CLAG
from helpers import assert_series_equal
from refimpl import ref_clag


CASES = [
    ([1.0, 1.0, 2.0, 2.0, 3.0, 2.0, 2.0], 1),
    ([1.0, 1.0, 1.0, 2.0, 2.0, 2.0], 2),
    ([0.0, 1.0, 0.0, 1.0, 1.0, 1.0], 2),
    ([None, 1.0, 1.0, None, 2.0, 2.0], 1),
    ([0.0, math.nan, 0.0, 1.0, math.nan, 1.0], 1),
    ([], 1),
]


def expected_series(values, period):
    return pl.Series("clag", ref_clag(values, period), dtype=pl.Float64)


@pytest.mark.parametrize("values,period", CASES)
def test_clag_expression(values, period):
    frame = pl.DataFrame({"close": pl.Series(values, dtype=pl.Float64)})
    got = frame.select(CLAG(period))["clag"]
    assert_series_equal(got, expected_series(values, period))


@pytest.mark.parametrize("values,period", CASES)
def test_clag_pyfunction(values, period):
    series = pl.Series("position", values, dtype=pl.Float64)
    got = kernels.clag(series, period=period)
    assert_series_equal(got, expected_series(values, period), check_names=False)


def test_clag_surfaces_match():
    values, period = CASES[0]
    frame = pl.DataFrame({"close": values})
    expression = frame.select(CLAG(period))["clag"]
    eager = kernels.clag(frame["close"], period=period)
    assert_series_equal(expression, eager)


def test_clag_source_forms_and_name():
    frame = pl.DataFrame({"position": [0, 1, 1, 0, 0]})
    got = frame.select(
        CLAG(1, src="position").alias("named"),
        pl.col("position").pipe(CLAG, 1).alias("piped"),
    )
    assert_series_equal(got["named"], got["piped"], check_names=False)
    assert frame.select(CLAG(1, src="position")).columns == ["clag"]


def test_clag_accepts_boolean_positions_as_zero_and_one():
    signal = pl.Series("signal", [False, True, True, False, False])
    expression = pl.DataFrame({"signal": signal}).select(CLAG(1, src="signal"))["clag"]
    eager = kernels.clag(signal, period=1)
    expected = pl.Series("clag", [None, None, 1.0, 1.0, 0.0])
    assert_series_equal(expression, expected)
    assert_series_equal(eager, expected, check_names=False)


def test_clag_zero_period_is_identity():
    values = [1.0, None, -1.0, math.nan, 0.5]
    frame = pl.DataFrame({"position": values})
    got = frame.select(CLAG(0, src="position"))["clag"]
    expected = pl.Series("clag", values)
    assert_series_equal(got, expected)


def test_clag_null_and_nan_emit_themselves_and_carry_candidate():
    frame = pl.DataFrame({"position": [1.0, None, 1.0, math.nan, 2.0, None, 2.0]})
    got = frame.select(CLAG(1, src="position"))["clag"].to_list()
    assert got[:3] == [None, None, 1.0]
    assert math.isnan(got[3])
    assert got[4:] == [1.0, None, 2.0]


def test_clag_resets_per_group():
    frame = pl.DataFrame(
        {
            "ticker": ["a", "b", "a", "b", "a", "b"],
            "position": [1.0, -1.0, 1.0, 0.0, 2.0, 0.0],
        }
    )
    got = frame.select(CLAG(1, src="position").over("ticker"))["clag"]
    assert got.to_list() == [None, None, 1.0, None, 1.0, 0.0]


def test_clag_handles_fragmented_input():
    series = pl.concat(
        [pl.Series("position", [0.0, 1.0]), pl.Series("position", [1.0, 0.0])],
        rechunk=False,
    )
    assert series.n_chunks() == 2
    assert kernels.clag(series, period=1).to_list() == [None, None, 1.0, 1.0]


@pytest.mark.parametrize("period", [-1, -2])
def test_clag_rejects_invalid_period(period):
    series = pl.Series("position", [0.0, 1.0])
    with pytest.raises(ValueError, match="period must be >= 0"):
        kernels.clag(series, period=period)
    with pytest.raises(pl.exceptions.PolarsError):
        pl.DataFrame({"close": series}).select(CLAG(period))
