import polars as pl
import pytest

from helpers import assert_series_equal

from bartons import kernels
from bartons.indicators import (
    QUADREG,
    QUADREG_CURVE,
    QUADREG_RMSE,
    QUADREG_RVALUE,
    QUADREG_SLOPE,
)
from refimpl import ref_quadreg


VALUES = [1.0, 2.0, 4.0, 8.0, 5.0, None, 3.0, 5.0, 4.0, 9.0, 12.0]
FACTORIES = {
    "forecast": (QUADREG, "quadreg"),
    "curve": (QUADREG_CURVE, "quadreg_curve"),
    "slope": (QUADREG_SLOPE, "quadreg_slope"),
    "rvalue": (QUADREG_RVALUE, "quadreg_rvalue"),
    "rmse": (QUADREG_RMSE, "quadreg_rmse"),
}


def test_exact_quadratic_has_expected_coefficients_and_fit():
    values = [float(i * i + 2 * i + 3) for i in range(8)]
    df = pl.DataFrame({"x": values})
    got = df.select(
        QUADREG(4, src="x"),
        QUADREG_CURVE(4, src="x"),
        QUADREG_SLOPE(4, src="x"),
        QUADREG_RVALUE(4, src="x"),
        QUADREG_RMSE(4, src="x"),
    ).row(-1, named=True)

    assert got == {
        "quadreg": 66.0,
        "quadreg_curve": 1.0,
        "quadreg_slope": 16.0,
        "quadreg_rvalue": 1.0,
        "quadreg_rmse": 0.0,
    }


@pytest.mark.parametrize("output", FACTORIES)
def test_quadreg_expression_and_eager_match_reference(output):
    df = pl.DataFrame({"x": pl.Series(VALUES, dtype=pl.Float64)})
    factory, name = FACTORIES[output]
    expression = df.select(factory(3, src="x"))[name]
    eager = kernels.quadreg(df["x"], period=3, output=output)
    expected = pl.Series(output, ref_quadreg(VALUES, 3, output), dtype=pl.Float64)

    assert_series_equal(
        expression, expected, check_names=False, check_exact=False, rel_tol=1e-11
    )
    assert_series_equal(expression, eager, check_names=False)


@pytest.mark.parametrize("output,factory", [("forecast", QUADREG), ("slope", QUADREG_SLOPE)])
def test_quadreg_offset(output, factory):
    values = [float(i * i + 2 * i + 3) for i in range(8)]
    df = pl.DataFrame({"close": values})
    expected = pl.Series(output, ref_quadreg(values, 4, output, 2))
    expression = df.select(factory(4, offset=2))[factory.__name__.lower()]
    eager = kernels.quadreg(df["close"], 4, 2, output=output)

    assert_series_equal(expression, expected, check_names=False, check_exact=False, rel_tol=1e-12)
    assert_series_equal(expression, eager, check_names=False)


@pytest.mark.parametrize("output", ["curve", "rvalue", "rmse"])
def test_nonzero_offset_rejected_for_nonprojected_outputs(output):
    series = pl.Series("x", [1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="offset is only valid"):
        kernels.quadreg(series, period=3, output=output, offset=1)


def test_invalid_output_rejected():
    series = pl.Series("x", [1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="invalid QUADREG output"):
        kernels.quadreg(
            series,
            period=3,
            output="rsquare",  # type: ignore  # deliberately invalid runtime input
        )


@pytest.mark.parametrize("period", [0, 1, 2, -1])
def test_invalid_period_rejected(period):
    series = pl.Series("x", [1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="period must be >= 3"):
        kernels.quadreg(series, period=period)


def test_invalid_rebase_interval_rejected():
    series = pl.Series("x", [1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="rebase_interval must be >= 0"):
        kernels.quadreg(series, period=3, rebase_interval=-1)


@pytest.mark.parametrize("rebase_interval", [None, 0, 1, 3, 4, 1000])
def test_rebase_intervals_match_fresh_window_reference(rebase_interval):
    values = [100.0 + ((i * 17) % 23) * 0.125 for i in range(80)]
    series = pl.Series("x", values)
    got = kernels.quadreg(
        series,
        period=7,
        rebase_interval=rebase_interval,
        output="curve",
    )
    expected = pl.Series("curve", ref_quadreg(values, 7, "curve"))
    assert_series_equal(
        got, expected, check_names=False, check_exact=False, rel_tol=1e-9, abs_tol=1e-10
    )


def test_integer_input_is_cast_and_source_forms_work():
    df = pl.DataFrame({"x": [1, 2, 4, 8]})
    named = df.select(QUADREG_CURVE(3, src="x"))["quadreg_curve"]
    piped = df.select(pl.col("x").pipe(QUADREG_CURVE, 3))["quadreg_curve"]
    eager = kernels.quadreg(df["x"], period=3, output="curve")

    assert named.dtype == pl.Float64
    assert_series_equal(named, piped)
    assert_series_equal(named, eager, check_names=False)
