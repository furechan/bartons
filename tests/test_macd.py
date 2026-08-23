import polars as pl
import pytest

from helpers import assert_series_equal

from bartons.indicators import MACD
from refimpl import ref_macd


XS = [float(value) for value in range(1, 41)]


def expected_frame(xs, fast, slow, signal):
    macd, macdsignal, macdhist = ref_macd(xs, fast, slow, signal)
    return pl.DataFrame(
        {
            "macd": pl.Series(macd, dtype=pl.Float64),
            "macdsignal": pl.Series(macdsignal, dtype=pl.Float64),
            "macdhist": pl.Series(macdhist, dtype=pl.Float64),
        }
    )


@pytest.mark.parametrize(
    "xs",
    [
        XS,
        [1.0, 2.0, 3.0, None, 5.0, 6.0, 7.0, 8.0, 9.0],
        [None, None, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
    ],
)
def test_macd_matches_composed_reference(xs):
    periods = (3, 5, 2)
    frame = pl.DataFrame({"x": pl.Series(xs, dtype=pl.Float64)})

    got = frame.select(MACD(*periods, src="x")).unnest("macd")
    expected = expected_frame(xs, *periods)

    for name in expected.columns:
        assert_series_equal(got[name], expected[name], check_exact=False, rel_tol=1e-12)


def test_macd_returns_named_struct_and_defaults_to_close():
    result = MACD(3, 5, 2)
    assert isinstance(result, pl.Expr)
    assert result.meta.output_name() == "macd"
    frame = pl.DataFrame({"close": pl.Series(XS, dtype=pl.Float64)})
    assert frame.select(result).schema["macd"] == pl.Struct(
        {"macd": pl.Float64, "macdsignal": pl.Float64, "macdhist": pl.Float64}
    )


def test_macd_expression_first_form():
    frame = pl.DataFrame({"x": pl.Series(XS, dtype=pl.Float64)})

    positional = frame.select(MACD(pl.col("x"), 3, 5, 2)).unnest("macd")
    keyword = frame.select(MACD(3, 5, 2, src=pl.col("x"))).unnest("macd")

    assert positional.equals(keyword)


@pytest.mark.parametrize("periods", [(0, 5, 2), (3, 0, 2), (3, 5, 0)])
def test_macd_rejects_invalid_periods(periods):
    frame = pl.DataFrame({"close": pl.Series(XS, dtype=pl.Float64)})
    with pytest.raises(pl.exceptions.PolarsError):
        frame.select(MACD(*periods))
