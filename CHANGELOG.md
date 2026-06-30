# Changelog

## 0.1.0

- Add ATR (Average True Range). `AtrFilter` composes a `TrangeFilter` feeding an
  `RmaFilter` (Wilder's RMA of True Range); a multi-input indicator over high /
  low / close. Exposed as `ATR()` and `plugin.atr` (default period 14). Also
  widen the conftest pyfunction-skip pattern to cover `rsi` and `atr`.
- Add a `bartons.samples` subpackage with bundled OHLCV sample prices (daily /
  hourly / minute AAPL CSVs). `sample_prices(freq, max_bars=...)` returns a
  polars DataFrame; `sample_dataset(n_tickers, ...)` stacks them into a synthetic
  multi-ticker frame for `.over()` benchmarks. `scripts/update-samples.py`
  refreshes the CSVs via yfinance (optional `samples` dependency group). Ported
  from python-dev's `barcalc`.
- Add RSI (Wilder's Relative Strength Index). `RsiFilter` composes two
  `RmaFilter`s for the smoothed average gain/loss and emits
  `100 * avg_gain / (avg_gain + avg_loss)`; a flat run yields `0`, matching
  TA-Lib. Exposed as `RSI()`, `.bt.rsi()`, and `plugin.rsi` (default period 14).
- Refactor all indicator kernels onto a streaming-filter pattern. Each indicator
  is now a polars-free struct (`EmaFilter`, `SmaFilter`, `RmaFilter`, `WmaFilter`,
  `TrangeFilter`) with a `new` constructor and a `next` step method, holding its
  own run state.
- Add `bartons/src/utils.rs` with the shared `Filter` trait and the `run_unary`
  and `run_ternary` drivers, which own the cast / iterate / build-with-nulls
  scaffolding. The unary indicators (EMA, SMA, RMA, WMA) implement `Filter` and
  are driven by `run_unary`; TRANGE uses the closure-based `run_ternary`.
- Move period validation out of the kernels: `*Filter::new` returns
  `Result<Self, String>` and the `calc_*` boundary maps the error to
  `PolarsError::ComputeError`, keeping the filters independent of polars.
