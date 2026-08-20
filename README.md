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
from bartons.indicators import ATR, CCI, EMA, MACD, MAD, RSI, TYPPRICE
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

Each indicator names its output after itself, so it adds a column rather than
overwriting the one it read, and siblings reading the same source do not
collide. The name is the bare factory name, so two parameterizations of one
indicator still want an explicit alias:

```python
prices.with_columns(EMA(20), SMA(20))                     # -> "ema", "sma"
prices.with_columns(EMA(20).alias("fast"), EMA(50).alias("slow"))
```

Single-source indicators default to `pl.col("close")` and also accept an explicit
source, which makes them chain with `pipe`:

```python
EMA(20)                          # close by default
EMA(pl.col("open"), 20)          # explicit source
pl.col("close").pipe(EMA, 5).pipe(RSI, 14)
```

`TRANGE`, `ATR` and the price transforms read `high`, `low` and `close` (plus
`open`, for `AVGPRICE`), each overridable by keyword. `CCI` is single-source
like the rest, but defaults its source to `TYPPRICE()` rather than
`pl.col("close")`:

```python
CCI(20)                                              # standard, over typical price
CCI(20, src=TYPPRICE(high="h", low="l", close="c"))   # other column names
pl.col("close").pipe(CCI, 20)                         # over some other series
```

## Indicators

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

Multi-output native indicators return an `ExprBundle`, which Polars accepts as
one argument and expands into ordinary columns:

```python
prices.with_columns(MACD())
prices.with_columns(*MACD(), SMA(20))  # splat when mixing with other expressions
```

## Eager API

The compiled kernels are also callable directly on a `pl.Series`, bypassing the
expression layer:

```python
from bartons import kernels

kernels.ema(prices["close"], period=20)
```

Parameters are keyword-only here. This path needs `polars>=1.28`; the expression
API alone works further back.

## Related Projects

- [Polars](https://docs.pola.rs/) — the DataFrame library. Since every indicator
  here is a plain `pl.Expr`, its expression docs cover most of what you can do
  with them: windows, groups, lazy frames, and the rest.
- [PyO3](https://pyo3.rs/) — Rust bindings for Python, and the polars plugin
  interface these kernels are written against. Worth reading if you want to write
  indicators of your own.
- [Maturin](https://www.maturin.rs/) — builds and publishes Rust extensions as
  Python wheels. The tool to reach for if you take that route.
