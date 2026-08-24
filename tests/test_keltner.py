import polars as pl

from helpers import assert_series_equal

from bartons.indicators import ATR, EMA, KELTNER, TYPPRICE


PRICES = pl.DataFrame(
    {
        "high": [11.0, 12.5, 13.0, 14.5, 15.0, 16.5, 16.0, 18.0],
        "low": [9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 13.5, 15.0],
        "close": [10.0, 12.0, 12.5, 14.0, 14.5, 15.0, 15.5, 17.0],
    }
)


def test_keltner_composes_typical_price_ema_and_atr():
    period, nbatr = 3, 2.0
    got = PRICES.select(KELTNER(period, nbatr)).unnest("keltner")

    middle = EMA(period, src=TYPPRICE())
    width = nbatr * ATR(period)
    expected = PRICES.select(
        (middle + width).alias("upperband"),
        middle.alias("middleband"),
        (middle - width).alias("lowerband"),
    )

    for name in ("upperband", "middleband", "lowerband"):
        assert_series_equal(got[name], expected[name])


def test_keltner_returns_named_struct():
    expression = KELTNER(3)

    assert expression.meta.output_name() == "keltner"
    assert PRICES.select(expression).schema["keltner"] == pl.Struct(
        {
            "upperband": pl.Float64,
            "middleband": pl.Float64,
            "lowerband": pl.Float64,
        }
    )


def test_keltner_accepts_custom_inputs():
    frame = PRICES.rename({"high": "h", "low": "l", "close": "c"})
    custom = frame.select(KELTNER(3, 1.5, high="h", low="l", close="c"))
    default = PRICES.select(KELTNER(3, 1.5))

    assert custom.equals(default)


def test_keltner_rejects_zero_period():
    try:
        PRICES.select(KELTNER(0))
    except (ValueError, pl.exceptions.PolarsError):
        return
    raise AssertionError("KELTNER accepted a zero period")
