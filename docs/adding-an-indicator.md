# Adding an indicator

Every indicator touches ~7 files across Rust and Python. EMA is the reference
implementation — copy it. This is the checklist; substitute `<name>` (lower,
e.g. `sma`) and `<NAME>` (upper, e.g. `SMA`).

The **scaffolding** (entry points, registration, wrappers, tests) is identical
for every indicator. Only the **kernel math** (`<name>`) is new.

## Naming convention

Three Rust symbols per indicator, by role. **The kernel owns the plain name — it
is the computation; the two bindings are suffixed by the boundary they serve.**

| Role | Rust symbol | Reached from Python as |
|---|---|---|
| kernel — the vector calculation | `<name>` | — (private) |
| expression plugin fn (FFI entry point) | `<name>_expr` | `<NAME>()` |
| eager binding | `<name>_py` | `bartons.kernels.<name>` |

A module is a *container*, not a synonym for one kernel: `linreg.rs` may define
`linreg`, `slope` and `rvalue` side by side, each with its own bindings. So the
kernel function is named for what it computes, never for its position — there is
no bare `calc`.

`<name>_py` keeps its Python name via `#[pyo3(name = "<name>")]`, so the exported
surface is unchanged; the suffix exists only to leave the plain name free for the
kernel. Two of the three names are externally constrained and cannot be chosen
freely: `function_name="<name>_expr"` in the Python wrapper **must match the Rust
`<name>_expr` symbol exactly** (that is how polars resolves the plugin at load
time — there is no compile-time check), and the `#[pyo3(name = …)]` string is
what Python sees. Only the kernel name is free.

## Steps

### 1. Rust kernel — `bartons/src/kernels/<name>.rs`

Copy [bartons/src/kernels/ema.rs](../bartons/src/kernels/ema.rs). It contains all three symbols.

- **Kwargs struct** — `#[derive(Deserialize)] pub struct <NAME>Kwargs { period: i64, … }`.
- **Kernel** `fn <name>(series: &Series, …) -> PolarsResult<Series>` — series in,
  series out. The `Filter` + driver loop is one way to implement it, not part of
  the definition; a kernel may equally be a plain loop or a vectorized expression:
  - `let series = series.cast(&DataType::Float64)?;` then `let ca = series.f64()?;`
    (the cast accepts int/f32 input; `f64()?` then can't fail).
  - Validate args (`period <= 0` → `PolarsError::InvalidOperation`, which
    `PyPolarsErr` maps to Python's builtin `ValueError`).
  - Build output with `PrimitiveChunkedBuilder::<Float64Type>::new(name.into(), len)`,
    appending `append_value` / `append_null` once per input row.
- **Expression entry point**:
  ```rust
  #[polars_expr(output_type = Float64)]
  fn <name>_expr(inputs: &[Series], kwargs: <NAME>Kwargs) -> PolarsResult<Series> {
      <name>(&inputs[0], kwargs.period)
  }
  ```
  `output_type` must be declared (polars needs the dtype at plan time).
- **Eager pyfunction** (optional but EMA has one). Precede it with a `///` doc
  comment (Args/Returns) — PyO3 surfaces it as the function's `__doc__`, so
  `help(bartons.kernels.<name>)` works:
  ```rust
  /// <One-line description>.
  ///
  /// Args:
  ///     series: input values.
  ///     period: averaging period (default 20).
  ///
  /// Returns:
  ///     A Float64 series; null during the warmup period.
  #[pyfunction]
  #[pyo3(name = "<name>", signature = (series, *, period=20))]
  pub fn <name>_py(series: PySeries, period: i64) -> PyResult<PySeries> {
      let series: Series = series.into();
      let result = <name>(&series, period).map_err(PyPolarsErr::from)?;
      Ok(PySeries(result))
  }
  ```
  `PyPolarsErr` (from `pyo3_polars::error`) maps each `PolarsError` variant to
  a Python exception — do not hand-roll a `PyRuntimeError`, which discards it.

### 2. Register

- In `bartons/src/kernels/mod.rs`, add `pub mod <name>;` alongside the other
  kernel modules.
- In `bartons/src/lib.rs`, add
  `m.add_function(wrap_pyfunction!(kernels::<name>::<name>_py, m)?)?;` in the
  `#[pymodule]`.
- **Do not** register `<name>_expr` — the polars plugin machinery finds it by
  symbol; adding it to the module is wrong.

### 3. Python expression factory — `python/bartons/indicators/<name>.py`

Factories live in the `bartons.indicators` sub-package. Copy
[python/bartons/indicators/ema.py](../python/bartons/indicators/ema.py): the
shared `PLUGIN_PATH` (the `bartons` package dir holding the compiled `.so`) is
imported from [`bartons.prelude`](../python/bartons/prelude.py), and
`IntoExprColumn` from the parent. Follow the mintalib convention: **period
first, `src` keyword-only defaulting to `pl.col("close")`**.

For a single-source factory, wrap it with `@wrap_src_indicator` (also from the
prelude) so it accepts its source column as the leading positional argument and
composes with `Expr.pipe` (`pl.col("close").pipe(EMA, 5)`). Multi-input
factories (TRANGE/ATR) take their columns explicitly and are *not* wrapped.

An indicator whose extra inputs collapse *elementwise* into one series is
single-source, not multi-input: build the reduction as its own expression
factory and make that the default `src`. CCI does this with `TYPPRICE()`, which
lives with the other OHLC transforms in
[python/bartons/indicators/price.py](../python/bartons/indicators/price.py). See
[Elementwise reductions stay out of Rust](architecture.md#elementwise-reductions-stay-out-of-rust)
for why the reduction gets no kernel, and for the ATR case where it does not
apply.

```python
from polars.plugins import register_plugin_function

from ..prelude import PLUGIN_PATH, wrap_src_indicator
from ..typing import IntoExprColumn


@wrap_src_indicator
def <NAME>(period: int, *, src: IntoExprColumn | None = None) -> pl.Expr:
    if src is None:
        src = pl.col("close")
    return register_plugin_function(
        args=[src], plugin_path=PLUGIN_PATH,
        function_name="<name>_expr", is_elementwise=False,
        kwargs=dict(period=period),
    )
```

Then re-export it from
[python/bartons/indicators/__init__.py](../python/bartons/indicators/__init__.py)
(`from .<name> import <NAME>` plus the `__all__` entry) so it is importable as
`from bartons.indicators import <NAME>`.

### 4. Tests — `tests/test_<name>.py`

Copy [tests/test_ema.py](../tests/test_ema.py). Add a `ref_<name>` **independent
Python reference oracle** to [tests/refimpl.py](../tests/refimpl.py) (all oracles
live there, one importable module, so composite indicators reuse the
primitives — e.g. `ref_atr` is `ref_rma` of `ref_trange`), then
`from refimpl import ref_<name>` in the test. Cover, against that oracle:

- both surfaces (`<NAME>()` expression and `kernels.<name>()`) and that they
  agree;
- `src=None`→`close` default and the column-name-string form;
- warmup nulls and null handling (see below);
- integer input is cast (not panicked);
- invalid period raises.

Use `assert_series_equal(..., check_exact=False, rel_tol=1e-12)` imported from
[tests/helpers.py](../tests/helpers.py) — a portable shim, **not**
`polars.testing`, so the suite runs across the full supported polars range. See
[test-compat-helpers.md](test-compat-helpers.md) for why.

### 5. Build & verify

```sh
just develop     # release; debug builds are ~20x slower
just test
just stubs     # regenerate python/bartons/kernels.pyi, then commit it
```

`just stubs` introspects the built module, so a new eager pyfunction is picked
up automatically. If it errors with *no type mapped for parameter*, add the name
to `PARAM_TYPES` in [scripts/generate-stubs.py](../scripts/generate-stubs.py) —
pyo3 exposes no type information, so that map is where it comes from.

### 6. Benchmark (optional) — `scripts/benchmark-vs-<baseline>.py`

Benchmarks are organised per *baseline*, not per indicator: each script runs the
whole indicator set against one comparison target. Add the new factory to the
lists in whichever are relevant —
[benchmark-vs-native.py](../scripts/benchmark-vs-native.py) (polars built-ins:
`ewm_mean`, `rolling_mean`, …),
[benchmark-vs-talib.py](../scripts/benchmark-vs-talib.py) (preloads libta-lib for
`polars_talib`, skipped if absent), and
[benchmark-vs-mintalib.py](../scripts/benchmark-vs-mintalib.py). They decompose
cost into construction / execution / build+execute and also report how each
backend parallelises across expressions in one `select()`.

```sh
just bench vs-native    # builds release, then runs scripts/benchmark-vs-native.py
```

Benchmark only against a **release** build (`just bench` does this) — a debug
build is ~20x slower and misleading.

## Conventions & gotchas

- **Null handling**: the recursive indicators (EMA, RMA — and thus RSI, ATR)
  *skip* a null: emit null for that row but carry the running state across the gap,
  matching polars/pandas `ewm` and mintalib. The windowed indicators (SMA, WMA)
  reset the window on a null. RSI additionally keeps `prev` across the gap, so the
  next bar measures the real change across it (a deliberate divergence from
  mintalib, which re-seeds — see CHANGELOG). Match the family your indicator
  belongs to. Note "skip" here means *emit a null row*, not `break`: every input
  row must still produce exactly one output row, or the output length won't match
  the input and polars errors.
- **Warmup**: emit `null` until enough values are accumulated (`count >= period`).
- **NaN** is used only as the kernel's "unseeded" marker, never as a stand-in for
  a null input (nulls come through the `Option` from `ca.iter()`).
- **Single polars-py range**: the `polars >=x,<y` range lives only in
  `[project].dependencies` — see [cargo-version-pins.md](cargo-version-pins.md).
- **Release builds**: `just develop` is release; only `just develop-debug` is the slow
  debug build. Benchmark with `just bench`.
- Many indicators have a native polars equivalent (`ewm_mean`, `rolling_mean`).
  Adding a plugin version is a deliberate choice (consistency / a specific
  variant), not a perf necessity — a release-built plugin is competitive.
