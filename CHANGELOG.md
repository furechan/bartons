# Changelog

## 0.1.0

- **Removed — the `.bt` expression namespace.** `pl.col("close").bt.ema(20)` no
  longer exists; use `EMA(20, src=pl.col("close"))` or
  `pl.col("close").pipe(EMA, 20)`, which are equivalent and, unlike `.bt`,
  statically checkable. `@pl.api.register_expr_namespace` attaches the accessor
  to `pl.Expr` at runtime, and since polars ships inline types with no `.pyi`
  files — and Python stubs have no declaration-merging — there is no way to
  declare `bt` on `pl.Expr` short of shadowing polars' own stubs. It was the only
  surface with no path to type checking, and it duplicated the factories it
  delegated to. `bartons/__init__.py` no longer imports anything for its side
  effect. The implementation and the full reasoning are preserved in
  [docs/namespace-legacy.md](docs/namespace-legacy.md).
- Make the wrapped single-source factories statically checkable. `wrap_src_indicator`
  is now typed `Callable[P, R] -> SrcIndicator[P, R]`, where `SrcIndicator` is a
  `Protocol` declaring both call forms as `__call__` overloads (canonical first,
  expression-first second). Previously the decorator carried no annotations, so
  a checker saw `EMA` and friends as opaque and checked nothing about them —
  `x: int = EMA(20)` passed. Ported from `bearta.prelude`.
- Move the shared factory machinery out of `bartons/indicators/__init__.py` into
  a new `bartons.prelude` module, and rename `wrap_src_expression` to
  `wrap_src_indicator` (matching `bearta.prelude`, which holds the same pieces
  under the same name). `PLUGIN_PATH` moves with it — it had to, because the two
  together were a circular import: each factory did `from . import PLUGIN_PATH,
  …` while `__init__.py` imported the factories at the bottom, so the package
  half-initialized itself and the re-export block could not be moved to the top
  without an `ImportError`. Factories now import `from ..prelude import …`,
  `indicators/__init__.py` is re-exports only, and the cycle is gone.
- **Bug fix — the three-series indicators (TRANGE, ATR) silently truncated on
  mismatched input lengths.** `run_ternary` sized its output builder from the
  first input while `izip!` stopped at the shortest, so unequal inputs produced a
  short result with no error. It now validates up front via a new variadic
  `check_len!(a, b, c)?` macro (a thin wrapper over `utils::check_lengths`),
  raising `ShapeMismatch` naming the series that disagrees and the two lengths.
  A length-1 input is treated as a mismatch, not a scalar to broadcast — plugin
  inputs arrive un-broadcast, so `pl.lit(100.0)` as an input is now a loud error
  instead of a silent one-row result.
- **API change — `bartons.expressions` is now `bartons.indicators`.** Import
  factories as `from bartons.indicators import EMA`. The `expressions` name was
  inherited from mintalib, where it distinguished the polars surface from the
  pandas `indicators` one; bartons is polars-only, so the contrast it drew does
  not exist here and every public object is an expression regardless. The
  sub-package now matches `bartons/src/indicators/` on the Rust side, giving the
  same seven names on both sides of the FFI boundary. "Expression factory"
  remains the term for what the module contains — only the module name changed.
  The `.bt` accessor is unaffected.
- Generalize the `Filter` trait over its input shape with an associated
  `type Input`, so the multi-input indicators join the same contract as the
  single-series ones. `TrangeFilter` and `AtrFilter` had an inherent `next` while
  `run_ternary` took a closure, leaving the two drivers with nothing in common
  and every ternary call site repeating a `|h, l, c| filter.next(h, l, c)`
  adapter. They now `impl Filter` with `type Input = Hlc` — a new
  `(Option<f64>, Option<f64>, Option<f64>)` alias, spelled `utils::Triple` on the
  driver side (which is arity-generic and assumes nothing about what the three
  series mean) and re-aliased as `indicators::Hlc` on the kernel side (which
  does). `run_ternary` is `run_ternary<F: Filter<Input = Triple>>`, and both call
  sites collapse to
  `run_ternary(h, l, c, name, filter)`. `AtrFilter::next` now passes the bar
  straight through to its inner `TrangeFilter` instead of unpacking and
  respreading it. Internal only — no behavior or API change.
- **Behavior change — nulls now skip instead of reset in the recursive
  indicators.** EMA, RMA (and therefore RSI and ATR, which smooth with the shared
  `RmaFilter`) previously treated a `None` input as a hard break: clear state,
  emit null, re-warm afterward. They now *skip* it — emit null for that row but
  carry the running average across the gap — matching polars/pandas `ewm` and
  mintalib. The windowed indicators (SMA, WMA) are unchanged; their window-reset
  already matches mintalib. RSI additionally keeps `prev` across the gap so the
  next bar measures the real change across it (BRIDGE); this **diverges from
  mintalib**, which re-seeds `prev` — chosen for consistency with the MA skip
  semantics (a null is ignored uniformly across all indicators) rather than
  copying mintalib's internal inconsistency. Filed upstream against mintalib to
  align its RSI. Verified kernel == oracle across all cases (166 tests pass), and
  EMA/RMA/ATR values == mintalib.
- Centralize the per-indicator Python reference oracles into one importable
  `tests/refimpl.py` (`ref_ema`/`ref_sma`/`ref_rma`/`ref_wma`/`ref_rsi`/
  `ref_trange`/`ref_atr`); the test files now `from refimpl import ref_<name>`
  instead of each defining its own inline. Kills the cross-file duplication
  (`ref_rma`/`ref_trange` had been copy-pasted into `test_atr.py`, and Wilder
  smoothing was inlined a third time inside `test_rsi.py`): `ref_atr` now composes
  `ref_rma ∘ ref_trange` and `ref_rsi` reuses `ref_rma`. Behaviour is unchanged
  (166 tests pass); the oracles stay dep-free hand-rolled Python so the lean
  `compat`/`rt` matrix keeps installing only the wheel + pytest + polars.
- Raise the supported `polars` floor from `>=1.0` to `>=1.28`, in both
  `pyproject.toml` and the nox `compat` matrix. The eager `bartons.plugin.<name>`
  pyfunctions marshal a Series into Rust via pyo3-polars 0.27's private
  `PySeries._export`, which polars only exposes from 1.28; on older engines they
  raise `AttributeError: 'PySeries' object has no attribute '_export'`. The
  expression path (`EMA()`, `.bt.ema()`) would work lower, but the package now
  floors at 1.28 so its whole public API is usable. `COMPAT_VERSIONS` drops the
  seven sub-1.28 entries and swaps `1.22.0` → `1.28.0` (both engine crate 0.46.0),
  keeping one representative per distinct engine crate across `[1.28, 1.43)`.
- Remove the `@requires_pyfunction` marker (and its decorators across the eager
  tests). With the `compat` floor now at 1.28, `PySeries._export` is always
  present, so the marker's `skipif` was permanently false. The
  `assert_series_equal` shim in `tests/helpers.py` stays — its `rel_tol`/`abs_tol`
  gate only clears at polars 1.32.3, so the 1.28–1.32.2 compat sessions still need
  it.
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
