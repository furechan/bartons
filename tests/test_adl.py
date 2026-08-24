import math

import polars as pl

from helpers import assert_series_equal

from bartons.indicators import ADL, ADOSC, EMA


PRICES = pl.DataFrame(
    {
        "high": [10.0, 12.0, 11.0, 14.0, 13.0, 15.0],
        "low": [8.0, 9.0, 7.0, 10.0, 9.0, 11.0],
        "close": [9.5, 10.0, 8.0, 13.0, 11.0, 14.0],
        "volume": [100, 200, 150, 300, 250, 400],
    }
)


def test_adl_matches_cumulative_money_flow_volume():
    got = PRICES.select(ADL())["adl"]
    multiplier = (
        (PRICES["close"] * 2.0 - PRICES["high"] - PRICES["low"])
        / (PRICES["high"] - PRICES["low"])
    )
    expected = (multiplier * PRICES["volume"]).cum_sum().rename("adl")
    assert_series_equal(got, expected)


def test_adosc_matches_explicit_ema_composition():
    adl = ADL()
    got = PRICES.select(ADOSC(2, 4))["adosc"]
    expected = PRICES.select(
        EMA(2, src=adl).sub(EMA(4, src=adl)).alias("adosc")
    )["adosc"]
    assert_series_equal(got, expected)


def test_ad_family_accepts_custom_integer_inputs():
    frame = PRICES.rename(
        {"high": "h", "low": "l", "close": "c", "volume": "v"}
    )
    custom_adl = frame.select(ADL(high="h", low="l", close="c", volume="v"))
    custom_adosc = frame.select(
        ADOSC(2, 4, high="h", low="l", close="c", volume="v")
    )

    assert custom_adl.equals(PRICES.select(ADL()))
    assert custom_adosc.equals(PRICES.select(ADOSC(2, 4)))


def test_adl_zero_range_is_nan():
    frame = pl.DataFrame(
        {"high": [1.0], "low": [1.0], "close": [1.0], "volume": [10]}
    )
    assert math.isnan(frame.select(ADL())["adl"][0])
