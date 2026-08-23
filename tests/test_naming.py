"""Every factory names its output after itself.

Polars names a plugin or arithmetic expression after its leftmost input column,
so without the `_named` step in the prelude decorators each factory would return
a column called `close` or `high` — overwriting the column it read, and
colliding with any sibling reading the same source.
"""

import polars as pl
import pytest

from bartons import indicators
from bartons.bundle import ExprBundle
from bartons.prelude import wrap_indicator, wrap_src_indicator


# Leading positional args needed to build each factory, by name.
ARGS = {
    "EMA": (2,), "SMA": (2,), "RMA": (2,), "WMA": (2,), "RSI": (2,),
    "ATR": (2,), "MAD": (2,), "CCI": (2,), "KER": (2,), "KAMA": (2,),
    "MACD": (2, 3, 2),
    "LINREG": (2,), "LINREG_SLOPE": (2,), "LINREG_RVALUE": (2,),
    "LINREG_RMSE": (2,),
    "QUADREG": (3,), "QUADREG_CURVE": (3,), "QUADREG_SLOPE": (3,),
    "QUADREG_RVALUE": (3,), "QUADREG_RMSE": (3,),
}
SINGLE = [name for name in indicators.__all__ if name != "MACD"]

OHLC = {
    "open": [1.0, 2.0, 3.0, 4.0],
    "high": [3.0, 4.0, 5.0, 6.0],
    "low": [1.0, 1.0, 2.0, 3.0],
    "close": [2.0, 3.0, 4.0, 5.0],
}


def _df():
    return pl.DataFrame({k: pl.Series(v, dtype=pl.Float64) for k, v in OHLC.items()})


def _build(name):
    if name == "STREAK":
        return indicators.STREAK(pl.col("close") > 0)
    return getattr(indicators, name)(*ARGS.get(name, ()))


@pytest.mark.parametrize("name", SINGLE)
def test_output_is_named_after_the_factory(name):
    assert _df().select(_build(name)).columns == [name.lower()]


@pytest.mark.parametrize("name", SINGLE)
def test_source_column_survives(name):
    """`with_columns` adds a column rather than overwriting the input it read."""
    got = _df().with_columns(_build(name))
    assert set(OHLC) <= set(got.columns)


@pytest.mark.parametrize("name", SINGLE)
def test_outer_alias_wins(name):
    assert _df().select(_build(name).alias("chosen")).columns == ["chosen"]


def test_whole_catalogue_composes_in_one_context():
    """No two factories collide on a default name."""
    got = _df().with_columns([_build(name) for name in SINGLE])
    assert got.columns == list(OHLC) + [name.lower() for name in SINGLE]


def test_bundle_members_keep_their_own_names():
    """MACD returns an ExprBundle, which names its members and is left alone."""
    assert _df().select(*_build("MACD")).columns == ["macd", "macdsignal", "macdhist"]


def test_same_indicator_twice_still_needs_an_alias():
    """The name is the bare factory name, so parameterizations collide by design."""
    df = _df()
    with pytest.raises(pl.exceptions.PolarsError, match="duplicate"):
        df.with_columns(indicators.EMA(2), indicators.EMA(3))
    assert df.with_columns(
        indicators.EMA(2).alias("ema2"), indicators.EMA(3).alias("ema3")
    ).columns[-2:] == ["ema2", "ema3"]


def test_wrap_indicator_rejects_a_src_factory():
    """A non-leading `src` needs wrap_src_indicator to route expressions."""
    with pytest.raises(TypeError, match="wrap_src_indicator"):

        @wrap_indicator
        def HasSrc(period, *, src=None):
            return pl.lit(period)


def test_wrap_indicator_accepts_a_leading_src():
    """A source-first factory already has the expression-first grammar."""

    @wrap_indicator
    def HasLeadingSrc(src):
        return src

    df = _df()
    assert df.select(HasLeadingSrc(pl.col("close"))).columns == ["hasleadingsrc"]
    assert df.select(pl.col("close").pipe(HasLeadingSrc)).columns == ["hasleadingsrc"]


def test_named_leaves_bundles_alone():
    """A bundle has no single name to give its members."""

    @wrap_indicator
    def PAIR():
        return ExprBundle(a=pl.lit(1), b=pl.lit(2))

    assert isinstance(PAIR(), ExprBundle)
    assert pl.DataFrame({"x": [1]}).select(*PAIR()).columns == ["a", "b"]


def test_named_applies_through_the_src_wrapper():
    """wrap_src_indicator names its output too, on both calling conventions."""

    @wrap_src_indicator
    def THING(period, *, src=None):
        return (src if src is not None else pl.col("close")) * period

    df = _df()
    assert df.select(THING(2)).columns == ["thing"]
    # The expression-first form, which is what `.pipe` reaches (covered for the
    # real factories in test_pipe.py).
    assert df.select(THING(pl.col("high"), 2)).columns == ["thing"]


# Kernel-backed indicators, paired with the eager pyfunction and the series it
# takes. The two names have independent sources — a hardcoded literal in the
# Rust driver call, and the Python factory's `__name__` — so
# nothing but this test keeps them from drifting apart.
KERNEL_BACKED = [
    "EMA", "SMA", "RMA", "WMA", "RSI", "TRANGE", "ATR", "MAD", "CCI", "KER", "KAMA", "SAR", "STREAK",
    "LINREG", "LINREG_SLOPE", "LINREG_RVALUE", "LINREG_RMSE",
    "QUADREG", "QUADREG_CURVE", "QUADREG_SLOPE", "QUADREG_RVALUE", "QUADREG_RMSE",
]


@pytest.mark.parametrize("name", KERNEL_BACKED)
def test_kernel_and_expression_names_agree(name):
    """The eager surface names its output in Rust, the expression surface in
    Python. Neither can see the other, so pin them to the same string."""
    from bartons import kernels

    df = _df()
    series = {k: df[k] for k in ("high", "low", "close")}
    period = ARGS.get(name, ())

    if name in ("TRANGE", "ATR"):
        eager = getattr(kernels, name.lower())(
            series["high"], series["low"], series["close"],
            **({"period": period[0]} if period else {}),
        )
    elif name == "SAR":
        eager = kernels.sar(series["high"], series["low"])
    elif name == "STREAK":
        eager = kernels.streak(series["close"] > 0)
    elif name == "CCI":
        typical = (series["high"] + series["low"] + series["close"]) / 3.0
        eager = kernels.cci(typical, period=period[0])
    elif name.startswith("LINREG"):
        output = name.removeprefix("LINREG_").lower() if name != "LINREG" else "forecast"
        eager = kernels.linreg(series["close"], period=period[0], output=output)
    elif name.startswith("QUADREG"):
        output = name.removeprefix("QUADREG_").lower() if name != "QUADREG" else "forecast"
        eager = kernels.quadreg(series["close"], period=period[0], output=output)
    else:
        eager = getattr(kernels, name.lower())(series["close"], period=period[0])

    assert eager.name == df.select(_build(name)).columns[0] == name.lower()
