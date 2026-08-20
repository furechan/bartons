"""The price transforms are native polars composition with no kernel behind
them. TYPPRICE is additionally CCI's default src, so it is checked against the
kernel's eager input as well."""

import polars as pl
import pytest

from helpers import assert_series_equal

from bartons.indicators import AVGPRICE, MEDPRICE, TYPPRICE, WCLPRICE


OPENS = [9.0, 10.0, None, 13.0, 14.0]
HIGHS = [10.0, 12.0, None, 15.0, 16.0]
LOWS = [8.0, 9.0, None, 11.0, 12.0]
CLOSES = [9.0, 11.0, None, 14.0, 15.0]

# (factory, columns it reads, reference formula over those columns)
TRANSFORMS = [
    (AVGPRICE, ("open", "high", "low", "close"), lambda o, h, l, c: (o + h + l + c) / 4),
    (MEDPRICE, ("high", "low"), lambda h, l: (h + l) / 2),
    (TYPPRICE, ("high", "low", "close"), lambda h, l, c: (h + l + c) / 3),
    (WCLPRICE, ("high", "low", "close"), lambda h, l, c: (h + l + 2 * c) / 4),
]

COLUMNS = {"open": OPENS, "high": HIGHS, "low": LOWS, "close": CLOSES}
# Short names for the custom-column-name test, in the canonical order.
SHORT = {"open": "o", "high": "h", "low": "l", "close": "c"}


def _df(names=None):
    names = names or {name: name for name in COLUMNS}
    return pl.DataFrame(
        {names[name]: pl.Series(values, dtype=pl.Float64) for name, values in COLUMNS.items()}
    )


def _expected(reference, columns):
    rows = zip(*(COLUMNS[name] for name in columns))
    return pl.Series(
        "price",
        [None if any(v is None for v in row) else reference(*row) for row in rows],
        dtype=pl.Float64,
    )


@pytest.mark.parametrize("factory,columns,reference", TRANSFORMS)
def test_defaults_to_ohlc_columns(factory, columns, reference):
    got = _df().select(factory().alias("price"))["price"]
    assert_series_equal(got, _expected(reference, columns), check_exact=False, rel_tol=1e-12)


@pytest.mark.parametrize("factory,columns,reference", TRANSFORMS)
def test_custom_column_names(factory, columns, reference):
    frame = _df(names=SHORT)
    expr = factory(**{name: SHORT[name] for name in columns})
    got = frame.select(expr.alias("price"))["price"]
    assert_series_equal(got, _expected(reference, columns), check_exact=False, rel_tol=1e-12)


@pytest.mark.parametrize("factory,columns,reference", TRANSFORMS)
def test_accepts_expressions(factory, columns, reference):
    frame = _df()
    names = frame.select(factory().alias("price"))
    expressions = frame.select(
        factory(**{name: pl.col(name) for name in columns}).alias("price")
    )
    assert names.equals(expressions)


@pytest.mark.parametrize("factory,columns,reference", TRANSFORMS)
def test_null_in_any_input_propagates(factory, columns, reference):
    """A missing bar yields null, which is what resets a downstream window."""
    got = _df().select(factory().alias("price"))["price"]
    assert got[2] is None


@pytest.mark.parametrize("factory,columns,reference", TRANSFORMS)
def test_integer_input_yields_float(factory, columns, reference):
    frame = pl.DataFrame({name: [10, 12] for name in COLUMNS})
    got = frame.select(factory().alias("price"))["price"]
    assert got.dtype == pl.Float64


def test_typprice_matches_eager_series_arithmetic():
    """The eager form the cci kernel's docstring points at gives the same values."""
    frame = _df()
    lazy = frame.select(TYPPRICE().alias("price"))["price"]
    eager = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    assert_series_equal(lazy, eager, check_names=False)


def test_medprice_is_not_a_rolling_midpoint():
    """MEDPRICE is TA-Lib's (high + low) / 2, not its period-taking MIDPRICE.

    The name divergence from bearta and mintalib is deliberate, so pin the shape
    the name promises: two inputs, no period.
    """
    with pytest.raises(TypeError):
        MEDPRICE(20)  # ty: ignore[too-many-positional-arguments]
