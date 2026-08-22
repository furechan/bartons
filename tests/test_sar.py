import polars as pl
import pytest
from bartons.indicators import SAR
from helpers import assert_series_equal
from refimpl import ref_sar

from bartons import kernels

CASES = [
    (
        [10.0, 11.0, 12.0, 13.0, 12.0, 11.0, 10.0, 11.0],
        [8.0, 9.0, 10.0, 11.0, 10.0, 9.0, 8.0, 9.0],
        0.02,
        0.2,
    ),
    (
        [10.0, 11.0, None, 14.0, 13.0, 12.0, 11.0],
        [8.0, 9.0, None, 12.0, 11.0, 10.0, 9.0],
        0.03,
        0.15,
    ),
    ([10.0, 9.0, 8.0, 7.0, 8.0, 9.0], [8.0, 7.0, 6.0, 5.0, 6.0, 7.0], 0.02, 0.0),
]


def _df(highs, lows):
    return pl.DataFrame(
        {
            "high": pl.Series(highs, dtype=pl.Float64),
            "low": pl.Series(lows, dtype=pl.Float64),
        }
    )


def expected_series(highs, lows, afs=0.02, maxaf=0.2):
    return pl.Series("sar", ref_sar(highs, lows, afs, maxaf), dtype=pl.Float64)


@pytest.mark.parametrize("highs,lows,afs,maxaf", CASES)
def test_sar_expression(highs, lows, afs, maxaf):
    got = _df(highs, lows).select(SAR(afs, maxaf))["sar"]
    assert_series_equal(
        got,
        expected_series(highs, lows, afs, maxaf),
        check_exact=False,
        rel_tol=1e-12,
    )


@pytest.mark.parametrize("highs,lows,afs,maxaf", CASES)
def test_sar_pyfunction(highs, lows, afs, maxaf):
    df = _df(highs, lows)
    got = kernels.sar(df["high"], df["low"], afs=afs, maxaf=maxaf)
    assert_series_equal(
        got,
        expected_series(highs, lows, afs, maxaf),
        check_names=False,
        check_exact=False,
        rel_tol=1e-12,
    )


def test_sar_accepts_column_names_and_exprs():
    df = pl.DataFrame({"h": [10.0, 11.0, 12.0], "l": [8.0, 9.0, 10.0]})
    by_name = df.select(SAR(high="h", low="l"))["sar"]
    by_expr = df.select(SAR(high=pl.col("h"), low=pl.col("l")))["sar"]
    assert_series_equal(by_name, by_expr)


def test_sar_defaults_match_explicit_values():
    df = _df([10.0, 11.0, 12.0, 11.0], [8.0, 9.0, 10.0, 9.0])
    got = df.select(SAR().alias("default"), SAR(0.02, 0.2).alias("explicit"))
    assert_series_equal(got["default"], got["explicit"], check_names=False)
    assert_series_equal(
        kernels.sar(df["high"], df["low"]),
        kernels.sar(df["high"], df["low"], afs=0.02, maxaf=0.2),
    )


def test_sar_carries_state_across_invalid_rows():
    highs = [10.0, 11.0, None, 14.0, 13.0, 12.0]
    lows = [8.0, 9.0, None, 12.0, 11.0, 10.0]
    got = _df(highs, lows).select(SAR())["sar"]
    assert_series_equal(
        got,
        expected_series(highs, lows),
        check_exact=False,
        rel_tol=1e-12,
    )
    assert got[2] is None
    assert got[3] is not None


def test_high_below_low_is_an_invalid_bar():
    highs = [10.0, 11.0, 5.0, 14.0]
    lows = [8.0, 9.0, 6.0, 12.0]
    got = _df(highs, lows).select(SAR())["sar"]
    assert_series_equal(got, expected_series(highs, lows), check_exact=False, rel_tol=1e-12)
    assert got[2] is None


def test_mismatched_lengths_raise():
    high = pl.Series("high", [10.0, 11.0, 12.0])
    low = pl.Series("low", [8.0, 9.0])
    with pytest.raises(ValueError, match="input lengths differ"):
        kernels.sar(high, low)


def test_length_one_input_is_not_broadcast():
    df = _df(*CASES[0][:2])
    with pytest.raises(pl.exceptions.ComputeError, match="input lengths differ"):
        df.select(SAR(low=pl.lit(8.0)))


def test_integer_input_is_cast():
    high = pl.Series("high", [10, 11, 12, 13], dtype=pl.Int64)
    low = pl.Series("low", [8, 9, 10, 11], dtype=pl.Int64)
    got = kernels.sar(high, low)
    assert got.dtype == pl.Float64
    assert_series_equal(
        got,
        expected_series([10.0, 11.0, 12.0, 13.0], [8.0, 9.0, 10.0, 11.0]),
        check_names=False,
        check_exact=False,
        rel_tol=1e-12,
    )
