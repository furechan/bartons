import polars as pl
import pytest

from helpers import assert_series_equal

from bartons import kernels
from bartons.indicators import ALMA
from refimpl import ref_alma


CASES = [
    ([1.0, 2.0, 3.0, 4.0, 5.0], 3, 0.85, 6.0),
    ([10.0, 11.0, None, 20.0, 21.0, 22.0], 3, 0.5, 4.0),
    ([5.0, 5.0, 5.0], 1, 0.85, 6.0),
    ([None, 1.0, 2.0, 3.0, 4.0], 2, 0.0, 2.0),
]


def expected(values, period, offset, sigma):
    return pl.Series(
        "alma", ref_alma(values, period, offset, sigma), dtype=pl.Float64
    )


@pytest.mark.parametrize("values,period,offset,sigma", CASES)
def test_alma_expression_and_eager_match_reference(values, period, offset, sigma):
    frame = pl.DataFrame({"x": pl.Series(values, dtype=pl.Float64)})
    expression = frame.select(
        ALMA(period, offset, sigma, src="x").alias("alma")
    )["alma"]
    eager = kernels.alma(
        frame["x"], period=period, offset=offset, sigma=sigma
    )
    want = expected(values, period, offset, sigma)
    assert_series_equal(expression, want, check_exact=False, rel_tol=1e-12)
    assert_series_equal(
        eager, want, check_names=False, check_exact=False, rel_tol=1e-12
    )


def test_alma_defaults_to_close_and_accepts_expression_first():
    frame = pl.DataFrame({"close": [1.0, 2.0, 3.0, 4.0]})
    default = frame.select(ALMA(3))
    piped = frame.select(pl.col("close").pipe(ALMA, 3))
    assert default.equals(piped)


def test_integer_input_is_cast():
    values = pl.Series("x", [1, 2, 3, 4], dtype=pl.Int64)
    result = kernels.alma(values, period=3)
    assert result.dtype == pl.Float64


@pytest.mark.parametrize(
    "kwargs,message",
    [
        ({"period": 0}, "period must be > 0"),
        ({"offset": float("inf")}, "offset must be finite"),
        ({"sigma": 0.0}, "sigma must be finite and > 0"),
    ],
)
def test_invalid_parameters_eager(kwargs, message):
    values = pl.Series("x", [1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match=message):
        kernels.alma(values, **kwargs)


def test_invalid_period_expression():
    frame = pl.DataFrame({"close": [1.0, 2.0, 3.0]})
    with pytest.raises(pl.exceptions.PolarsError):
        frame.select(ALMA(0))
