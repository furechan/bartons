import polars as pl
import pytest

from helpers import assert_series_equal

from bartons import kernels
from bartons.indicators import DMI
from refimpl import ref_dmi


HIGHS = [10.0, 12.0, 11.0, 14.0, 13.0, 15.0, 14.0, 16.0]
LOWS = [8.0, 9.0, 8.5, 11.0, 10.0, 12.0, 11.0, 13.0]
CLOSES = [9.0, 11.0, 9.0, 13.0, 11.0, 14.0, 12.0, 15.0]


def frame(highs=HIGHS, lows=LOWS, closes=CLOSES):
    return pl.DataFrame({"high": highs, "low": lows, "close": closes})


def expected(highs=HIGHS, lows=LOWS, closes=CLOSES, period=2):
    adx, pdi, mdi = ref_dmi(highs, lows, closes, period)
    return pl.DataFrame(
        {
            "adx": pl.Series(adx, dtype=pl.Float64),
            "pdi": pl.Series(pdi, dtype=pl.Float64),
            "mdi": pl.Series(mdi, dtype=pl.Float64),
        }
    )


def test_dmi_struct_matches_reference():
    got = frame().select(DMI(2)).unnest("dmi")
    want = expected()
    for name in want.columns:
        assert_series_equal(got[name], want[name], check_exact=False, rel_tol=1e-12)


def test_dmi_returns_named_struct_expression():
    result = DMI(2)
    assert isinstance(result, pl.Expr)
    assert result.meta.output_name() == "dmi"
    assert frame().select(result).schema["dmi"] == pl.Struct(
        {"adx": pl.Float64, "pdi": pl.Float64, "mdi": pl.Float64}
    )


def test_dmi_accepts_column_names_and_expressions():
    prices = frame().rename({"high": "h", "low": "l", "close": "c"})
    by_name = prices.select(DMI(2, high="h", low="l", close="c"))
    by_expr = prices.select(
        DMI(2, high=pl.col("h"), low=pl.col("l"), close=pl.col("c"))
    )
    assert by_name.equals(by_expr)


def test_eager_kernel_returns_named_struct():
    prices = frame()
    result = kernels.dmi(prices["high"], prices["low"], prices["close"], period=2)
    assert result.name == "dmi"
    assert result.dtype == pl.Struct(
        {"adx": pl.Float64, "pdi": pl.Float64, "mdi": pl.Float64}
    )
    got = result.struct.unnest()
    want = expected()
    for name in want.columns:
        assert_series_equal(got[name], want[name], check_exact=False, rel_tol=1e-12)


def test_frame_level_unnest_exposes_fields():
    got = frame().select(DMI(2)).unnest("dmi")
    assert got.equals(expected())


def test_grouped_struct_matches_separate_groups():
    prices = pl.concat(
        [frame().with_columns(ticker=pl.lit("a")), frame().with_columns(ticker=pl.lit("b"))]
    )
    got = prices.select("ticker", DMI(2).over("ticker")).unnest("dmi")
    want = pl.concat(
        [
            frame().select(DMI(2)).unnest("dmi").with_columns(ticker=pl.lit("a")),
            frame().select(DMI(2)).unnest("dmi").with_columns(ticker=pl.lit("b")),
        ]
    ).select("ticker", "adx", "pdi", "mdi")
    assert got.equals(want)


def test_null_bar_resets_directional_comparison():
    highs = [10.0, 12.0, None, 15.0, 16.0, 17.0]
    lows = [8.0, 9.0, None, 12.0, 13.0, 14.0]
    closes = [9.0, 11.0, None, 14.0, 15.0, 16.0]
    got = frame(highs, lows, closes).select(DMI(2)).unnest("dmi")
    want = expected(highs, lows, closes, 2)
    for name in want.columns:
        assert_series_equal(got[name], want[name], check_exact=False, rel_tol=1e-12)


def test_integer_inputs_are_cast():
    prices = frame([10, 12, 11, 14], [8, 9, 8, 11], [9, 11, 9, 13])
    result = kernels.dmi(prices["high"], prices["low"], prices["close"], period=2)
    assert result.dtype == pl.Struct(
        {"adx": pl.Float64, "pdi": pl.Float64, "mdi": pl.Float64}
    )


def test_mismatched_lengths_raise():
    prices = frame()
    with pytest.raises(ValueError, match="input lengths differ"):
        kernels.dmi(
            prices["high"], prices["low"].slice(0, 3), prices["close"], period=2
        )


@pytest.mark.parametrize("surface", ["expression", "eager"])
def test_invalid_period(surface):
    prices = frame()
    if surface == "expression":
        with pytest.raises(pl.exceptions.PolarsError):
            prices.select(DMI(0))
    else:
        with pytest.raises(ValueError, match="period must be > 0"):
            kernels.dmi(prices["high"], prices["low"], prices["close"], period=0)
