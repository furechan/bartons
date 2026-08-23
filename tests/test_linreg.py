import polars as pl
import pytest

from helpers import assert_series_equal

from bartons import kernels
from bartons.indicators import LINREG, LINREG_RMSE, LINREG_RVALUE, LINREG_SLOPE
from refimpl import ref_linreg


VALUES = [1.0, 2.0, 4.0, 8.0, 5.0, None, 3.0, 5.0, 4.0, 9.0, 12.0]
FACTORIES = {
    "forecast": (LINREG, "linreg"),
    "slope": (LINREG_SLOPE, "linreg_slope"),
    "rvalue": (LINREG_RVALUE, "linreg_rvalue"),
    "rmse": (LINREG_RMSE, "linreg_rmse"),
}


@pytest.mark.parametrize("output", FACTORIES)
def test_linreg_expression_and_eager_match_reference(output):
    df = pl.DataFrame({"x": pl.Series(VALUES, dtype=pl.Float64)})
    factory, name = FACTORIES[output]
    expression = df.select(factory(3, src="x"))[name]
    eager = kernels.linreg(df["x"], period=3, output=output)
    expected = pl.Series(output, ref_linreg(VALUES, 3, output), dtype=pl.Float64)

    assert_series_equal(
        expression, expected, check_names=False, check_exact=False, rel_tol=1e-12
    )
    assert_series_equal(expression, eager, check_names=False)


def test_linreg_forecast_offset():
    values = [1.0, 2.0, 4.0, 8.0, 16.0]
    df = pl.DataFrame({"close": values})
    expected = pl.Series("linreg", ref_linreg(values, 3, "forecast", 2))
    expression = df.select(LINREG(3, offset=2))["linreg"]
    eager = kernels.linreg(df["close"], 3, 2)
    assert_series_equal(expression, expected, check_exact=False, rel_tol=1e-12)
    assert_series_equal(expression, eager, check_names=False)


def test_nonzero_offset_rejected_for_diagnostics():
    series = pl.Series("x", [1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="offset is only valid"):
        kernels.linreg(series, period=2, output="slope", offset=1)


def test_invalid_output_rejected():
    series = pl.Series("x", [1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="invalid LINREG output"):
        kernels.linreg(
            series,
            period=2,
            output="intercept",  # type: ignore  # deliberately invalid runtime input
        )


@pytest.mark.parametrize("period", [0, 1, -1])
def test_invalid_period_rejected(period):
    series = pl.Series("x", [1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="period must be >= 2"):
        kernels.linreg(series, period=period)


def test_invalid_rebase_interval_rejected():
    series = pl.Series("x", [1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="rebase_interval must be >= 0"):
        kernels.linreg(series, period=2, rebase_interval=-1)


@pytest.mark.parametrize("rebase_interval", [None, 0, 1, 3, 4, 1000])
def test_rebase_intervals_match_fresh_window_reference(rebase_interval):
    values = [100.0 + ((i * 17) % 23) * 0.125 for i in range(80)]
    series = pl.Series("x", values)
    got = kernels.linreg(
        series,
        period=7,
        rebase_interval=rebase_interval,
        output="slope",
    )
    expected = pl.Series("slope", ref_linreg(values, 7, "slope"))
    assert_series_equal(
        got, expected, check_names=False, check_exact=False, rel_tol=1e-10, abs_tol=1e-10
    )


def test_integer_input_is_cast_and_source_forms_work():
    df = pl.DataFrame({"x": [1, 2, 3, 4]})
    named = df.select(LINREG_SLOPE(3, src="x"))["linreg_slope"]
    piped = df.select(pl.col("x").pipe(LINREG_SLOPE, 3))["linreg_slope"]
    eager = kernels.linreg(df["x"], period=3, output="slope")
    assert named.dtype == pl.Float64
    assert_series_equal(named, piped)
    assert_series_equal(named, eager, check_names=False)
