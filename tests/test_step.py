import math

import polars as pl
import pytest

from bartons import kernels
from bartons.indicators import STEP
from helpers import assert_series_equal
from refimpl import ref_step


CASES = [
    ([0.0, 3.2, 3.8, 4.3, 1.0, -2.5], 1.0),
    ([1.0, 1.4, 1.9, 2.0, 2.1, 1.2, 1.0, 0.9], 0.5),
    ([None, 1.0, 1.5, None, 2.2, 3.3], 0.5),
    ([0.0, math.nan, 2.0, 3.0], 1.0),
    ([], 1.0),
]


def expected_series(values, threshold):
    return pl.Series("step", ref_step(values, threshold), dtype=pl.Float64)


@pytest.mark.parametrize("values,threshold", CASES)
def test_step_expression(values, threshold):
    frame = pl.DataFrame({"close": pl.Series(values, dtype=pl.Float64)})
    got = frame.select(STEP(threshold))["step"]
    assert_series_equal(got, expected_series(values, threshold))


@pytest.mark.parametrize("values,threshold", CASES)
def test_step_pyfunction(values, threshold):
    series = pl.Series("values", values, dtype=pl.Float64)
    got = kernels.step(series, threshold=threshold)
    assert_series_equal(
        got, expected_series(values, threshold), check_names=False
    )


def test_step_surfaces_match():
    values, threshold = CASES[1]
    frame = pl.DataFrame({"close": values})
    expression = frame.select(STEP(threshold))["step"]
    eager = kernels.step(frame["close"], threshold=threshold)
    assert_series_equal(expression, eager)


def test_step_source_forms_and_name():
    frame = pl.DataFrame({"price": [0.0, 3.0, 4.0]})
    got = frame.select(
        STEP(1.0, src="price").alias("named"),
        pl.col("price").pipe(STEP, 1.0).alias("piped"),
    )
    assert_series_equal(got["named"], got["piped"], check_names=False)
    assert frame.select(STEP(1.0, src="price")).columns == ["step"]


def test_step_zero_threshold_holds_seed_value():
    frame = pl.DataFrame({"close": [1.0, 2.0, -3.0]})
    assert frame.select(STEP(0.0))["step"].to_list() == [None, 1.0, 1.0]


def test_step_null_and_nan_emit_themselves_and_carry_state():
    frame = pl.DataFrame({"close": [0.0, 3.0, None, 5.0, math.nan, 7.0]})
    got = frame.select(STEP(1.0))["step"].to_list()
    assert got[:4] == [None, 1.0, None, 2.0]
    assert math.isnan(got[4])
    assert got[5] == 3.0


def test_step_integer_input_is_cast():
    series = pl.Series("values", [0, 3, 4], dtype=pl.Int64)
    got = kernels.step(series)
    assert got.dtype == pl.Float64
    assert got.to_list() == [None, 1.0, 2.0]


def test_step_resets_per_group():
    frame = pl.DataFrame(
        {
            "ticker": ["a", "b", "a", "b", "a", "b"],
            "close": [0.0, 10.0, 3.0, 8.0, 4.0, 7.0],
        }
    )
    got = frame.select(STEP(1.0).over("ticker"))["step"]
    assert got.to_list() == [None, None, 1.0, 9.0, 2.0, 8.0]


def test_step_handles_fragmented_input():
    series = pl.concat(
        [pl.Series("values", [0.0, 3.0]), pl.Series("values", [4.0, 1.0])],
        rechunk=False,
    )
    assert series.n_chunks() == 2
    got = kernels.step(series)
    assert got.to_list() == [None, 1.0, 2.0, 1.0]


@pytest.mark.parametrize("threshold", [-1.0, math.inf, math.nan])
def test_step_rejects_invalid_threshold(threshold):
    series = pl.Series("values", [1.0, 2.0])
    with pytest.raises(ValueError, match="threshold must be finite and >= 0"):
        kernels.step(series, threshold=threshold)
    with pytest.raises(pl.exceptions.PolarsError):
        pl.DataFrame({"close": series}).select(STEP(threshold))
