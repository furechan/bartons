import polars as pl
import pytest
from bartons.indicators import STREAK
from helpers import assert_series_equal
from refimpl import ref_streak

from bartons import kernels

CASES = [
    [True, True, False, True, True, True, None, True],
    [False, False, False],
    [True, True, True],
    [None, True, None, False, True],
    [],
]


def expected_series(values):
    return pl.Series("streak", ref_streak(values), dtype=pl.Int64)


@pytest.mark.parametrize("values", CASES)
def test_streak_expression(values):
    df = pl.DataFrame({"signal": pl.Series(values, dtype=pl.Boolean)})
    got = df.select(STREAK(pl.col("signal")))["streak"]
    assert_series_equal(got, expected_series(values))


@pytest.mark.parametrize("values", CASES)
def test_streak_pyfunction(values):
    signal = pl.Series("signal", values, dtype=pl.Boolean)
    got = kernels.streak(signal)
    assert_series_equal(got, expected_series(values), check_names=False)


def test_streak_accepts_column_name_and_pipe():
    df = pl.DataFrame({"signal": [True, True, False, True]})
    got = df.select(
        STREAK("signal").alias("named"),
        pl.col("signal").pipe(STREAK).alias("piped"),
    )
    assert_series_equal(got["named"], got["piped"], check_names=False)


def test_streak_composes_direction_explicitly():
    close = [10.0, 11.0, 12.0, 11.0, 12.0, 13.0]
    got = pl.DataFrame({"close": close}).select(
        STREAK(pl.col("close").diff() > 0)
    )["streak"]
    assert got.to_list() == [0, 1, 2, 0, 1, 2]


def test_streak_resets_per_group():
    df = pl.DataFrame(
        {
            "ticker": ["a", "b", "a", "b", "a", "b"],
            "signal": [True, True, True, False, False, True],
        }
    )
    got = df.select(STREAK(pl.col("signal")).over("ticker"))["streak"]
    assert got.to_list() == [1, 1, 2, 0, 0, 1]


def test_streak_handles_fragmented_boolean_input():
    signal = pl.concat(
        [
            pl.Series("signal", [True, True]),
            pl.Series("signal", [False, True]),
            pl.Series("signal", [True, None], dtype=pl.Boolean),
        ],
        rechunk=False,
    )
    assert signal.n_chunks() == 3
    assert_series_equal(
        kernels.streak(signal),
        expected_series(signal.to_list()),
        check_names=False,
    )


def test_streak_rejects_non_boolean_input():
    numeric = pl.Series("signal", [0, 1, 1], dtype=pl.Int64)
    with pytest.raises(ValueError, match="input must be Boolean"):
        kernels.streak(numeric)
    with pytest.raises(pl.exceptions.PolarsError):
        pl.DataFrame({"signal": numeric}).select(STREAK(pl.col("signal")))
