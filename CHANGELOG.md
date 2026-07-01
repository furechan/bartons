# Changelog

## 0.1.0

- Replace the `tests/conftest.py` source-grepping skip hook with an explicit
  `@requires_pyfunction` marker (defined in `tests/helpers.py`) on the eager
  direct-call tests. The marker skips when `PySeries._export` is absent — the
  eager `plugin.<name>` surface needs it (polars ≥ 1.28 with pyo3-polars 0.27),
  while the expression / `.bt` path is unaffected and runs across the full
  supported range. `conftest.py` removed; verified on the polars 1.22 compat
  session (eager tests skip, everything else passes).
- Make the `.bt` namespace methods delegate to the expression factories
  (`xp.EMA(period, src=self._expr)`, …) instead of re-implementing the
  `register_plugin_function` call. The FFI wiring now lives in one place per
  indicator (the factory); `namespace.py` no longer imports `register_plugin_function`
  or `PLUGIN_PATH`.
- Add `///` doc comments to every eager pyfunction (EMA, SMA, RMA, WMA, RSI,
  TRANGE, ATR), so PyO3 surfaces them as `__doc__` and `help(bartons.plugin.<name>)`
  shows the signature plus an Args/Returns description.
- Move the Rust indicator kernels into a `bartons/src/indicators/` source module
  (`lib.rs` now `mod indicators;`); cross-kernel refs use `super::`. No API
  change — the eager functions stay exposed flat at `bartons.plugin.<name>`.
- Make the single-source factories (EMA, SMA, RMA, WMA, RSI) accept their source
  column as the leading positional argument via a `wrap_src_expression`
  decorator (adapted from bearta's `wrap_expression`), so they compose with `Expr.pipe`:
  `pl.col("close").pipe(EMA, 5).pipe(RSI, 14)`. `EMA(5)` and `EMA(5, src=...)`
  keep working unchanged.
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
