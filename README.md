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

To work from a clone instead:

```sh
uv sync
just develop        # builds the Rust extension and installs it into .venv
```

## Usage

```python
import polars as pl
from bartons.indicators import EMA, RSI, ATR
from bartons.samples import sample_prices

prices = sample_prices("daily")

prices.select("date", "close", ema=EMA(20), rsi=RSI(14), atr=ATR(14)).tail(3)
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

Single-source indicators default to `pl.col("close")` and also accept an explicit
source, which makes them chain with `pipe`:

```python
EMA(20)                          # close by default
EMA(pl.col("open"), 20)          # explicit source
pl.col("close").pipe(EMA, 5).pipe(RSI, 14)
```

`TRANGE` and `ATR` read `high`, `low` and `close`, each overridable by keyword.

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

## Eager API

The compiled kernels are also callable directly on a `pl.Series`, bypassing the
expression layer:

```python
import bartons.plugin as plugin

plugin.ema(prices["close"], period=20)
```

Parameters are keyword-only here. This path needs `polars>=1.28`; the expression
API alone works further back.

## Development

```sh
just develop     # build + install into .venv
just test        # pytest
just build       # wheel + sdist into dist/
just bench       # benchmark against a baseline
```

In the repository: `CLAUDE.md` for the architecture, `docs/` for the
version-pinning and polars-FFI details, `BACKLOG.md` for open items.

## Built with

- [Polars](https://docs.pola.rs/) — the DataFrame library these indicators extend.
  Everything here returns a plain `pl.Expr`, so anything polars can do with an
  expression applies unchanged.
- [PyO3](https://pyo3.rs/) — Rust bindings for Python. The indicator kernels are
  Rust, called over the polars plugin interface rather than through Python, so
  there is no per-element crossing between the two languages.
- [Maturin](https://www.maturin.rs/) — builds and packages the Rust extension as a
  Python wheel. The wheels are `abi3`, which is why a single one covers every
  Python from 3.11 up.
