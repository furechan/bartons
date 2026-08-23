import polars as pl
import pytest

from helpers import assert_series_equal

from bartons import kernels
from bartons.indicators import DEMA, HMA, TEMA, ZLEMA
from refimpl import ref_dema, ref_hma, ref_tema, ref_zlema


CASES = [
    ([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0], 2),
    ([1.0, 2.0, 3.0, None, 5.0, 6.0, 7.0, 8.0, 9.0], 2),
    ([5.0] * 12, 3),
]


@pytest.mark.parametrize(
    "name,factory,kernel,reference",
    [("dema", DEMA, kernels.dema, ref_dema), ("tema", TEMA, kernels.tema, ref_tema)],
)
@pytest.mark.parametrize("values,period", CASES)
def test_exponential_families_match_composed_reference(
    name, factory, kernel, reference, values, period
):
    df = pl.DataFrame({"x": values})
    expression = df.select(factory(period, src="x"))[name]
    eager = kernel(df["x"], period=period)
    expected = pl.Series(name, reference(values, period))
    assert_series_equal(expression, expected, check_exact=False, rel_tol=1e-12)
    assert_series_equal(expression, eager)


@pytest.mark.parametrize("period", [2, 3, 5, 8])
def test_hma_matches_composed_reference(period):
    values = [float(value) for value in range(1, 25)]
    df = pl.DataFrame({"x": values})
    expression = df.select(HMA(period, src="x"))["hma"]
    eager = kernels.hma(df["x"], period=period)
    expected = pl.Series("hma", ref_hma(values, period))
    assert_series_equal(expression, expected, check_exact=False, rel_tol=1e-12)
    assert_series_equal(expression, eager)


@pytest.mark.parametrize("period", [1, 2, 3, 6])
def test_zlema_matches_delagged_ema_reference(period):
    values = [1.0, 2.0, 4.0, 3.0, None, 8.0, 9.0, 11.0, 10.0, 12.0, 14.0]
    df = pl.DataFrame({"x": values})
    expression = df.select(ZLEMA(period, src="x"))["zlema"]
    eager = kernels.zlema(df["x"], period=period)
    expected = pl.Series("zlema", ref_zlema(values, period))
    assert_series_equal(expression, expected, check_exact=False, rel_tol=1e-12)
    assert_series_equal(expression, eager)


@pytest.mark.parametrize(
    "kernel,period,message",
    [(kernels.dema, 0, "DEMA period must be > 0"),
     (kernels.tema, 0, "TEMA period must be > 0"),
     (kernels.hma, 1, "HMA period must be > 1"),
     (kernels.zlema, 0, "ZLEMA period must be > 0")],
)
def test_invalid_periods(kernel, period, message):
    with pytest.raises(ValueError, match=message):
        kernel(pl.Series([1.0]), period=period)
