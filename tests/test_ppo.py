import polars as pl

from helpers import assert_series_equal

from bartons.indicators import EMA, PPO


VALUES = [10.0, 11.0, 13.0, 12.0, 15.0, 14.0, 16.0, 18.0, 17.0, 19.0]


def test_ppo_matches_raw_ema_ratio():
    frame = pl.DataFrame({"close": VALUES})
    got = frame.select(PPO(3, 5))["ppo"]

    fast = EMA(3)
    slow = EMA(5)
    expected = frame.select(fast.sub(slow).truediv(slow).alias("ppo"))["ppo"]
    assert_series_equal(got, expected)


def test_ppo_accepts_custom_source_and_expression_first_form():
    frame = pl.DataFrame({"x": VALUES})
    keyword = frame.select(PPO(3, 5, src="x"))
    expression_first = frame.select(PPO(pl.col("x"), 3, 5))
    assert keyword.equals(expression_first)


def test_ppo_is_not_scaled_by_100():
    frame = pl.DataFrame({"close": VALUES})
    raw = frame.select(PPO(3, 5))["ppo"]
    scaled = frame.select(PPO(3, 5).mul(100.0))["ppo"]

    index = next(index for index, value in enumerate(raw) if value is not None)
    assert scaled[index] == raw[index] * 100.0
