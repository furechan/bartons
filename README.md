# bartons

Financial and technical-analysis expressions for [polars](https://docs.pola.rs/),
implemented in Rust as a native plugin (PyO3 + maturin).

Each indicator is a factory returning a `pl.Expr`, so it composes with the rest of
polars — inside `select`, `with_columns`, `over`, lazy frames, and so on.

## Install

Requires Python 3.11+ and `polars>=1.28,<1.44`. Wheels are `cp311-abi3`, so one
wheel per platform covers every Python from 3.11 up. Prebuilt wheels support
Linux x86_64 and ARM64, macOS Intel and Apple silicon, and Windows x64; other
platforms can build from the sdist with a Rust toolchain.

```sh
pip install bartons
```

## Usage

```python
import polars as pl
from bartons.indicators import ATR, CCI, DMI, EMA, MACD, RSI, SMA, TYPPRICE
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

## Conventions

Price frames use a `date` or `datetime` column followed by lowercase `open`,
`high`, `low`, `close`, and `volume` columns. Indicators refer to these lowercase
OHLCV names by default; pass explicit column names or expressions when your
schema differs.

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

`CCI` is a single-source indicator, but defaults its source to `TYPPRICE()`
rather than `pl.col("close")`:

```python
CCI(20)                          # typical price by default
CCI(20, src=TYPPRICE())          # same thing
```

## Indicators

<!-- indicators:start -->
| | |
|---|---|
| `ADL()` | Accumulation/Distribution Line |
| `ADOSC(fast=3, slow=10)` | Chaikin A/D Oscillator |
| `ADX(period=14)` | Average Directional Index |
| `ALMA(period=9, offset=0.85, sigma=6.0)` | Arnaud Legoux moving average |
| `APO(fast=12, slow=26, matype="ema")` | Absolute Price Oscillator |
| `AROON(period=14)` | Aroon Down and Up |
| `AROONOSC(period=14)` | Aroon Oscillator |
| `ATR(period)` | Average true range |
| `AVGPRICE()` | Average price, `(open + high + low + close) / 4` |
| `BBANDS(period=20, nbdev=2.0)` | Bollinger upper, middle and lower bands |
| `BBP(period=20, nbdev=2.0)` | Bollinger Percent B ratio |
| `BBW(period=20, nbdev=2.0)` | Bollinger BandWidth ratio |
| `BOP()` | Unsmoothed Balance of Power |
| `CCI(period=20)` | Commodity Channel Index |
| `CMF(period=20)` | Chaikin Money Flow |
| `CMO(period=14)` | Rolling-window Chande Momentum Oscillator |
| `DEMA(period)` | Double exponential moving average |
| `DMI(period=14)` | ADX, plus DI and minus DI expressions |
| `DONCHIAN(period=20)` | Donchian upper, middle and lower channels |
| `EMA(period)` | Exponential moving average |
| `HMA(period)` | Hull moving average |
| `KAMA(period=10, fastn=2, slown=30)` | Kaufman adaptive moving average |
| `KELTNER(period=20, nbatr=2.0)` | Keltner upper, middle and lower channels |
| `KER(period=10)` | Kaufman efficiency ratio |
| `LINREG(period=20, offset=0)` | Rolling linear-regression forecast |
| `LINREG_RMSE(period=20)` | Rolling linear-regression RMSE |
| `LINREG_RVALUE(period=20)` | Rolling linear-regression r-value |
| `LINREG_SLOPE(period=20)` | Rolling linear-regression slope |
| `MA(period=30, matype="sma")` | Generic moving-average dispatcher |
| `MACD(fast=12, slow=26, signal=9)` | MACD, signal and histogram expressions |
| `MAD(period=20)` | Rolling mean absolute deviation |
| `MDI(period=14)` | Negative Directional Indicator |
| `MEDPRICE()` | Median price, `(high + low) / 2` |
| `MFI(period=14)` | Money Flow Index |
| `MOM(period=1)` | Momentum |
| `NATR(period=14)` | Normalized Average True Range (%) |
| `OBV()` | On-Balance Volume |
| `PDI(period=14)` | Positive Directional Indicator |
| `PPO(fast=12, slow=26, matype="ema")` | Price Percentage Oscillator (%) |
| `QUADREG(period=20, offset=0)` | Rolling quadratic-regression forecast |
| `QUADREG_CURVE(period=20)` | Rolling quadratic coefficient |
| `QUADREG_RMSE(period=20)` | Rolling quadratic-regression RMSE |
| `QUADREG_RVALUE(period=20)` | Rolling quadratic partial r-value |
| `QUADREG_SLOPE(period=20, offset=0)` | Rolling quadratic-regression slope |
| `RMA(period)` | Wilder's running moving average |
| `ROC(period=1)` | Rate of Change (%) |
| `ROCP(period=1)` | Rate of Change as an unscaled fraction |
| `RSI(period)` | Wilder's relative strength index |
| `SAR(afs=0.02, maxaf=0.2)` | Parabolic Stop and Reverse |
| `SMA(period)` | Simple moving average |
| `STOCH(period=14, fastn=3, slown=3)` | Slow stochastic oscillator, `%K` and `%D` |
| `STOCHRSI(period=14, fastn=3, slown=3)` | Stochastic RSI, fast K and fast D |
| `STREAK(src)` | Consecutive true count |
| `SUPERTREND(period=10, multiplier=3.0)` | Supertrend line and bullish/bearish direction |
| `TEMA(period=20)` | Triple exponential moving average |
| `TRANGE()` | True range |
| `TRIX(period=30)` | Triple-smoothed EMA rate of change (%) |
| `TYPPRICE()` | Typical price, `(high + low + close) / 3` |
| `ULTOSC(fast=7, medium=14, slow=28)` | Ultimate Oscillator |
| `VWMA(period=20)` | Volume-weighted moving average |
| `WCLPRICE()` | Weighted close price, `(high + low + 2 * close) / 4` |
| `WILLR(period=14)` | Williams %R |
| `WMA(period)` | Weighted moving average |
| `ZLEMA(period)` | Zero-lag exponential moving average |
<!-- indicators:end -->


Multi-output indicators return a Polars struct expression. You can unpack its
fields directly in the query:

```python
prices.select("date", MACD().struct.unnest())
```

Or keep the struct column in the query result and unnest it afterward:

```python
result = prices.select("date", MACD())  # contains "macd" struct column
result.unnest()
```

Bare `.unnest()` expands every struct column; pass a column name such as
`.unnest("macd")` to expand only that struct. The resulting field names must not
collide with existing columns.

## Development

Set up the development environment and run the complete source-tree validation:

```sh
uv sync
uv run inv make
```

Run the Rust and Python tests without regenerating the extension and stubs:

```sh
uv run inv test
```

## License

Bartons is available under the MIT License.

## Related Projects

- [polars-talib](https://github.com/Yvictor/polars_ta_extension) — a Polars extension exposing TA-Lib indicators and candlestick-pattern functions as Polars expressions.
- [polars-ta](https://github.com/wukan1986/polars_ta) — an expression-oriented collection of technical-analysis, WorldQuant, and Tongdaxin operators for Polars.
- [Polars](https://docs.pola.rs/) — a fast DataFrame library with Rust and Python APIs, an expression engine, lazy query optimization, and Arrow-compatible memory.
- [PyO3](https://pyo3.rs/) — Rust bindings for creating native Python modules and calling between Rust and Python.
- [Maturin](https://www.maturin.rs/) — a build and publishing tool for Python packages implemented in Rust.
