import polars as pl

from bearta.ema import EMA


from polars.testing import assert_frame_equal


def test_ema():
    df = pl.DataFrame(
        {"close": [100.0, 101.0, 102.0]}
    )
    result = df.with_columns(EMA(pl.col('close'), period=2))
    assert isinstance(result, pl.DataFrame)

