# bartons

Financial and technical-analysis expressions for [polars](https://docs.pola.rs/),
implemented in Rust as a native plugin (PyO3 + maturin).

Each indicator is a factory returning a `pl.Expr`, so it composes with the rest of
polars — inside `select`, `with_columns`, `over`, lazy frames, and so on.

## Install

Requires Python 3.11+ and `polars>=1.28,<1.44`. Wheels are `cp311-abi3`, so one
wheel per platform covers every Python from 3.11 up.

```sh
pip install bartons
```

## Usage

```python
import polars as pl
from bartons.indicators import ATR, CCI, EMA, MACD, RSI, SMA, TYPPRICE
from bartons.samples import sample_prices

prices = sample_prices("daily")

prices.select("date", "close", EMA(20), RSI(14), ATR(14)).tail(3)
```

```
┌────────────┬────────────┬────────────┬───────────┬──────────┐
│ date       ┆ close      ┆ ema        ┆ rsi       ┆ atr      │
╞════════════╪════════════╪════════════╪═══════════╪══════════╡
│ 2024-08-07 ┆ 209.820007 ┆ 217.642081 ┆ 40.192313 ┆ 6.920431 │
│ 2024-08-08 ┆ 213.309998 ┆ 217.229501 ┆ 45.237928 ┆ 6.809686 │
│ 2024-08-09 ┆ 216.240005 ┆ 217.135264 ┆ 49.118920 ┆ 6.666851 │
└────────────┴────────────┴────────────┴───────────┴──────────┘
```

Each indicator names its output after itself in lowercase like `ema`, `sma` ... Use explicit aliases to avoid name collisions:

```python
prices.with_columns(EMA(20), SMA(20))                     # -> "ema", "sma"
prices.with_columns(EMA(20).alias("fast"), EMA(50).alias("slow"))
```

Single-source indicators typically default to `pl.col("close")` as source, but they also accept an explicit source, either as the first positional argument or via the `src` keyword, which makes them chainable with `pipe`:

```python
EMA(20)                                     # default source
EMA(pl.col("close"), 20)                    # explicit source (positional)
EMA(20, src=pl.col("close"))                # explicit source (src keyword)
pl.col("close").pipe(EMA, 20)               # chaining with pipe
```

`TRANGE`, `ATR` and the price transforms like `TYPPRICE` accept multiple inputs like `high`, `low` and `close`, each overridable via keyword arguments:

```python
TYPPRICE()                              # high, low and close
TYPPRICE(high="h", low="l", close="c")  # other column names
```

`CCI` is single-source indicator, but defaults its source to `TYPPRICE()`
rather than `pl.col("close")`:

```python
CCI(20)                          # typical price by default
CCI(20, src=TYPPRICE())          # same thing
```

## Indicators

<!-- indicators:start -->
| | |
|---|---|
| `EMA(period)` | Exponential moving average |
| `SMA(period)` | Simple moving average |
| `RMA(period)` | Wilder's running moving average |
| `WMA(period)` | Weighted moving average |
| `RSI(period)` | Wilder's relative strength index |
| `TRANGE()` | True range |
| `ATR(period)` | Average true range |
| `MACD(fast=12, slow=26, signal=9)` | MACD, signal and histogram expressions |
| `MAD(period=20)` | Rolling mean absolute deviation |
| `AVGPRICE()` | Average price, `(open + high + low + close) / 4` |
| `MEDPRICE()` | Median price, `(high + low) / 2` |
| `TYPPRICE()` | Typical price, `(high + low + close) / 3` |
| `WCLPRICE()` | Weighted close price, `(high + low + 2 * close) / 4` |
| `CCI(period=20)` | Commodity Channel Index |
| `KER(period=10)` | Kaufman efficiency ratio |
| `KAMA(period=10, fastn=2, slown=30)` | Kaufman adaptive moving average |
| `SAR(afs=0.02, maxaf=0.2)` | Parabolic Stop and Reverse |
| `STREAK(src)` | Consecutive true count |
| `LINREG(period=20, offset=0)` | Rolling linear-regression line |
| `LINREG_SLOPE(period=20)` | Rolling linear-regression slope |
| `LINREG_RVALUE(period=20)` | Rolling linear-regression r-value |
| `LINREG_RMSE(period=20)` | Rolling linear-regression RMSE |
| `QUADREG(period=20, offset=0)` | Rolling quadratic-regression curve |
| `QUADREG_CURVE(period=20)` | Rolling quadratic coefficient |
| `QUADREG_SLOPE(period=20, offset=0)` | Rolling quadratic-regression slope |
| `QUADREG_RVALUE(period=20)` | Rolling quadratic partial r-value |
| `QUADREG_RMSE(period=20)` | Rolling quadratic-regression RMSE |
<!-- indicators:end -->


Multi-output native indicators return an `ExprBundle`, essentially a tuple of expressions:

```python
prices.with_columns(MACD())             # tuple works as single argument
prices.with_columns(*MACD(), SMA(20))   # splat when mixing with other expressions
```

## Eager API

The compiled kernels are also callable directly on polars series, bypassing the
expression layer:

```python
from bartons import kernels

kernels.ema(prices["close"], period=20)
```

Parameters are keyword-only here. This path needs `polars>=1.28`; the expression
API alone works further back.

## Related Projects

- [polars-talib](https://github.com/Yvictor/polars_ta_extension) — a Polars extension exposing TA-Lib indicators and candlestick-pattern functions as Polars expressions.
- [polars-ta](https://github.com/wukan1986/polars_ta) — an expression-oriented collection of technical-analysis, WorldQuant, and Tongdaxin operators for Polars.
- [Polars](https://docs.pola.rs/) — a fast DataFrame library with Rust and Python APIs, an expression engine, lazy query optimization, and Arrow-compatible memory.
- [PyO3](https://pyo3.rs/) — Rust bindings for creating native Python modules and calling between Rust and Python.
- [Maturin](https://www.maturin.rs/) — a build and publishing tool for Python packages implemented in Rust.
