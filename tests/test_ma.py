import polars as pl
import pytest

from bartons.indicators import DEMA, EMA, KAMA, MA, SMA, TEMA, WMA


@pytest.mark.parametrize(
    ("matype", "factory"),
    [
        ("sma", SMA),
        ("ema", EMA),
        ("wma", WMA),
        ("dema", DEMA),
        ("tema", TEMA),
        ("kama", KAMA),
    ],
)
def test_ma_matches_concrete_factory(matype, factory):
    frame = pl.DataFrame({"close": [float(value) for value in range(1, 41)]})
    generic = frame.select(MA(5, matype=matype))
    concrete = frame.select(factory(5).alias("ma"))
    assert generic.equals(concrete)


def test_ma_defaults_to_sma():
    frame = pl.DataFrame({"close": [1.0, 2.0, 3.0, 4.0]})
    assert frame.select(MA(2)).equals(frame.select(SMA(2).alias("ma")))


def test_ma_supports_expression_first_form():
    frame = pl.DataFrame({"price": [1.0, 2.0, 3.0, 4.0]})
    via_pipe = frame.select(pl.col("price").pipe(MA, 2, matype="ema"))
    via_keyword = frame.select(MA(2, matype="ema", src="price"))
    assert via_pipe.equals(via_keyword)


def test_ma_rejects_unsupported_type():
    with pytest.raises(ValueError, match="unsupported matype"):
        MA(20, matype="rma")  # type: ignore  # intentionally invalid runtime input


def test_ma_rejects_positional_matype():
    with pytest.raises(TypeError):
        MA(20, "ema")  # type: ignore  # intentionally invalid call shape
