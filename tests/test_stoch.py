import polars as pl
import pytest

from helpers import assert_series_equal

from bartons.indicators import STOCH
from refimpl import ref_stoch


PRICES = {
    "high": [12.0, 13.0, 15.0, 14.0, 16.0, 18.0, 17.0, 20.0, 19.0, 21.0],
    "low": [9.0, 10.0, 11.0, 10.0, 12.0, 13.0, 12.0, 15.0, 14.0, 16.0],
    "close": [11.0, 12.0, 14.0, 11.0, 15.0, 17.0, 13.0, 19.0, 18.0, 20.0],
}


@pytest.mark.parametrize(
    "prices",
    [
        PRICES,
        {
            "high": [12.0, 13.0, 15.0, None, 16.0, 18.0, 17.0, 20.0],
            "low": [9.0, 10.0, 11.0, None, 12.0, 13.0, 12.0, 15.0],
            "close": [11.0, 12.0, 14.0, None, 15.0, 17.0, 13.0, 19.0],
        },
    ],
)
def test_stoch_matches_reference(prices):
    periods = (4, 2, 2)
    frame = pl.DataFrame(
        {
            name: pl.Series(values, dtype=pl.Float64)
            for name, values in prices.items()
        }
    )
    got = frame.select(STOCH(*periods)).unnest("stoch")
    expected = ref_stoch(
        prices["high"], prices["low"], prices["close"], *periods
    )

    for name, values in zip(("slowk", "slowd"), expected):
        assert_series_equal(
            got[name],
            pl.Series(name, values, dtype=pl.Float64),
            check_exact=False,
            rel_tol=1e-12,
        )


def test_stoch_returns_named_struct():
    frame = pl.DataFrame(PRICES)
    expression = STOCH(4, 2, 2)
    assert expression.meta.output_name() == "stoch"
    assert frame.select(expression).schema["stoch"] == pl.Struct(
        {"slowk": pl.Float64, "slowd": pl.Float64}
    )


def test_stoch_accepts_custom_expressions():
    frame = pl.DataFrame(
        {f"x_{name}": values for name, values in PRICES.items()}
    )
    got = frame.select(
        STOCH(
            4,
            2,
            2,
            high=pl.col("x_high"),
            low=pl.col("x_low"),
            close=pl.col("x_close"),
        )
    )
    renamed = frame.rename(
        {"x_high": "high", "x_low": "low", "x_close": "close"}
    ).select(STOCH(4, 2, 2))
    assert got.equals(renamed)


@pytest.mark.parametrize(
    "periods",
    [(0, 3, 3), (14, 0, 3), (14, 3, 0)],
)
def test_stoch_rejects_invalid_periods(periods):
    with pytest.raises(ValueError):
        STOCH(*periods)
