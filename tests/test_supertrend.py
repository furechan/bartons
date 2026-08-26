import math

import polars as pl
import pytest

from helpers import assert_series_equal

from bartons import kernels
from bartons.indicators import SUPERTREND
from refimpl import ref_supertrend


HIGHS = [10.0, 11.0, 12.0, 13.0, 12.0, 11.0, 10.0, 9.0, 10.0, 12.0]
LOWS = [8.0, 9.0, 10.0, 11.0, 10.0, 9.0, 8.0, 7.0, 8.0, 10.0]
CLOSES = [9.0, 10.0, 11.0, 12.0, 10.5, 9.5, 8.5, 8.0, 9.5, 11.5]


def frame(highs=HIGHS, lows=LOWS, closes=CLOSES):
    return pl.DataFrame(
        {
            "high": pl.Series(highs, dtype=pl.Float64),
            "low": pl.Series(lows, dtype=pl.Float64),
            "close": pl.Series(closes, dtype=pl.Float64),
        }
    )


def expected(highs=HIGHS, lows=LOWS, closes=CLOSES, period=3, multiplier=1.5):
    line, direction = ref_supertrend(highs, lows, closes, period, multiplier)
    return pl.DataFrame(
        {
            "supertrend": pl.Series(line, dtype=pl.Float64),
            "direction": pl.Series(direction, dtype=pl.Int64),
        }
    )


def test_supertrend_struct_matches_reference():
    got = frame().select(SUPERTREND(3, 1.5)).unnest("supertrend")
    want = expected()
    assert_series_equal(got["supertrend"], want["supertrend"], check_exact=False, rel_tol=1e-12)
    assert_series_equal(got["direction"], want["direction"])
    assert set(got["direction"].drop_nulls()) == {-1, 1}


def test_returns_named_typed_struct():
    expression = SUPERTREND(3, 1.5)
    assert expression.meta.output_name() == "supertrend"
    assert frame().select(expression).schema["supertrend"] == pl.Struct(
        {"supertrend": pl.Float64, "direction": pl.Int64}
    )


def test_first_valid_state_is_bearish():
    got = frame().select(SUPERTREND(3, 1.5)).unnest("supertrend")
    first = got.drop_nulls().row(0, named=True)
    assert first["direction"] == -1


def test_eager_kernel_matches_reference():
    prices = frame()
    result = kernels.supertrend(
        prices["high"], prices["low"], prices["close"], period=3, multiplier=1.5
    )
    assert result.name == "supertrend"
    got = result.struct.unnest()
    want = expected()
    assert_series_equal(got["supertrend"], want["supertrend"], check_exact=False, rel_tol=1e-12)
    assert_series_equal(got["direction"], want["direction"])


def test_accepts_column_names_and_expressions():
    prices = frame().rename({"high": "h", "low": "l", "close": "c"})
    by_name = prices.select(SUPERTREND(3, 1.5, high="h", low="l", close="c"))
    by_expr = prices.select(
        SUPERTREND(3, 1.5, high=pl.col("h"), low=pl.col("l"), close=pl.col("c"))
    )
    assert by_name.equals(by_expr)


def test_null_bar_emits_null_and_carries_trend_state():
    highs = [10.0, 11.0, 12.0, None, 13.0, 14.0, 10.0]
    lows = [8.0, 9.0, 10.0, None, 11.0, 12.0, 8.0]
    closes = [9.0, 10.0, 11.0, None, 12.0, 13.0, 9.0]
    got = frame(highs, lows, closes).select(SUPERTREND(2, 1.0)).unnest("supertrend")
    want = expected(highs, lows, closes, 2, 1.0)
    assert_series_equal(got["supertrend"], want["supertrend"], check_exact=False, rel_tol=1e-12)
    assert_series_equal(got["direction"], want["direction"])
    assert got.row(3) == (None, None)
    assert got.row(4) != (None, None)


def test_grouped_struct_matches_separate_groups():
    prices = pl.concat(
        [frame().with_columns(ticker=pl.lit("a")), frame().with_columns(ticker=pl.lit("b"))]
    )
    got = prices.select("ticker", SUPERTREND(3, 1.5).over("ticker")).unnest("supertrend")
    want = pl.concat(
        [
            frame().select(SUPERTREND(3, 1.5)).unnest("supertrend").with_columns(ticker=pl.lit("a")),
            frame().select(SUPERTREND(3, 1.5)).unnest("supertrend").with_columns(ticker=pl.lit("b")),
        ]
    ).select("ticker", "supertrend", "direction")
    assert got.equals(want)


@pytest.mark.parametrize("period", [0, -1])
def test_invalid_period(period):
    prices = frame()
    with pytest.raises(ValueError, match="period must be > 0"):
        kernels.supertrend(prices["high"], prices["low"], prices["close"], period=period)


@pytest.mark.parametrize("multiplier", [0.0, -1.0, math.inf, math.nan])
def test_invalid_multiplier(multiplier):
    prices = frame()
    with pytest.raises(ValueError, match="multiplier must be finite and > 0"):
        kernels.supertrend(
            prices["high"], prices["low"], prices["close"], multiplier=multiplier
        )


def test_mismatched_lengths_raise():
    prices = frame()
    with pytest.raises(ValueError, match="input lengths differ"):
        kernels.supertrend(
            prices["high"], prices["low"].slice(0, 3), prices["close"]
        )
