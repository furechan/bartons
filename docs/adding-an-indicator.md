# Adding an indicator

Every indicator touches ~7 files across Rust and Python. EMA is the reference
implementation — copy it. This is the checklist; substitute `<name>` (lower,
e.g. `sma`) and `<NAME>` (upper, e.g. `SMA`).

The **scaffolding** (entry points, registration, wrappers, tests) is identical
for every indicator. Only the **kernel math** (`calc_<name>`) is new.

## Naming convention

Three Rust symbols per indicator, by role:

| Role | Rust symbol | Reached from Python as |
|---|---|---|
| compute kernel | `calc_<name>` | — (private) |
| expression plugin fn (FFI entry point) | `<name>_expr` | `<NAME>()` / `.bt.<name>()` |
| eager binding | `<name>` (pyfunction) | `bartons.plugin.<name>` |

The `function_name="<name>_expr"` string in the Python wrappers **must match the
Rust `<name>_expr` symbol exactly** — that's how polars resolves the plugin at
load time. There is no compile-time check on it.

## Steps

### 1. Rust kernel — `bartons/src/indicators/<name>.rs`

Copy [bartons/src/indicators/ema.rs](../bartons/src/indicators/ema.rs). It contains all three symbols.

- **Kwargs struct** — `#[derive(Deserialize)] pub struct <NAME>Kwargs { period: i64, … }`.
- **Kernel** `fn calc_<name>(series: &Series, …) -> PolarsResult<Series>`:
  - `let series = series.cast(&DataType::Float64)?;` then `let ca = series.f64()?;`
    (the cast accepts int/f32 input; `f64()?` then can't fail).
  - Validate args (`period <= 0` → `PolarsError::ComputeError`).
  - Build output with `PrimitiveChunkedBuilder::<Float64Type>::new(name.into(), len)`,
    appending `append_value` / `append_null` once per input row.
- **Expression entry point**:
  ```rust
  #[polars_expr(output_type = Float64)]
  fn <name>_expr(inputs: &[Series], kwargs: <NAME>Kwargs) -> PolarsResult<Series> {
      calc_<name>(&inputs[0], kwargs.period)
  }
  ```
  `output_type` must be declared (polars needs the dtype at plan time).
- **Eager pyfunction** (optional but EMA has one). Precede it with a `///` doc
  comment (Args/Returns) — PyO3 surfaces it as the function's `__doc__`, so
  `help(bartons.plugin.<name>)` works:
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
  #[pyo3(signature = (series, *, period=20))]
  pub fn <name>(series: PySeries, period: i64) -> PyResult<PySeries> { … }
  ```

### 2. Register

- In `bartons/src/indicators/mod.rs`, add `pub mod <name>;` alongside the other
  kernel modules.
- In `bartons/src/lib.rs`, add
  `m.add_function(wrap_pyfunction!(indicators::<name>::<name>, m)?)?;` in the
  `#[pymodule]`.
- **Do not** register `<name>_expr` — the polars plugin machinery finds it by
  symbol; adding it to the module is wrong.

### 3. Python expression factory — `python/bartons/expressions/<name>.py`

Factories live in the `bartons.expressions` sub-package. Copy
[python/bartons/expressions/ema.py](../python/bartons/expressions/ema.py): the
shared `PLUGIN_PATH` (the `bartons` package dir holding the compiled `.so`) is
imported from the package, and `IntoExprColumn` from the parent. Follow the
mintalib convention: **period first, `src` keyword-only defaulting to
`pl.col("close")`**.

For a single-source factory, wrap it with `@wrap_src_expression` (also from the
package) so it accepts its source column as the leading positional argument and
composes with `Expr.pipe` (`pl.col("close").pipe(EMA, 5)`). Multi-input
factories (TRANGE/ATR) take their columns explicitly and are *not* wrapped.

```python
from polars.plugins import register_plugin_function

from . import PLUGIN_PATH, wrap_src_expression
from ..typing import IntoExprColumn


@wrap_src_expression
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
[python/bartons/expressions/__init__.py](../python/bartons/expressions/__init__.py)
(`from .<name> import <NAME>` plus the `__all__` entry) so it is importable as
`from bartons.expressions import <NAME>`.

### 4. `.bt` namespace — `python/bartons/namespace.py`

Add a method to `BartonsExprNamespace` (source is the receiver expr, so no `src`):

```python
def <name>(self, period: int) -> pl.Expr:
    return register_plugin_function(
        function_name="<name>_expr", plugin_path=PLUGIN_PATH,
        is_elementwise=False, args=[self._expr], kwargs=dict(period=period),
    )
```

### 5. Tests — `tests/test_<name>.py`

Copy [tests/test_ema.py](../tests/test_ema.py). Cover, against an **independent
Python reference oracle**:

- all three surfaces (`<NAME>()` expression, `.bt.<name>()`, `plugin.<name>()`)
  and that they agree;
- `src=None`→`close` default and the column-name-string form;
- warmup nulls and null handling (see below);
- integer input is cast (not panicked);
- invalid period raises.

Use `assert_series_equal(..., check_exact=False, rel_tol=1e-12)` imported from
[tests/helpers.py](../tests/helpers.py) — a portable shim, **not**
`polars.testing`, so the suite runs across the full supported polars range. See
[test-compat-helpers.md](test-compat-helpers.md) for why.

### 6. Build & verify

```sh
just build     # release; debug builds are ~20x slower
just test
```

### 7. Benchmark (optional) — `scripts/benchmark-<name>.py`

Copy [scripts/benchmark-ema.py](../scripts/benchmark-ema.py) (or
[benchmark-sma.py](../scripts/benchmark-sma.py)). Compare against the native
polars equivalent (e.g. `ewm_mean`, `rolling_mean`) and the talib baseline. The
template decomposes cost into construction / execution / build+execute and
preloads libta-lib for `polars_talib` (skipped if absent). Run with:

```sh
just bench <name>    # builds release, then runs scripts/benchmark-<name>.py
```

Benchmark only against a **release** build (`just bench` does this) — a debug
build is ~20x slower and misleading.

## Conventions & gotchas

- **Null handling**: EMA *resets the run* on a null (emit null, clear state,
  re-warm afterward) — match this unless the indicator genuinely differs. Every
  input row must produce exactly one output row (no `break`/skip), or the output
  length won't match the input and polars errors.
- **Warmup**: emit `null` until enough values are accumulated (`count >= period`).
- **NaN** is used only as the kernel's "unseeded" marker, never as a stand-in for
  a null input (nulls come through the `Option` from `ca.iter()`).
- **Single polars cap**: the `polars >=x,<y` window lives only in
  `[project].dependencies` — see [pyo3-polars-version-lockstep.md](../archive/pyo3-polars-version-lockstep.md).
- **Release builds**: `just build` is release; only `just build-debug` is the slow
  debug build. Benchmark with `just bench`.
- Many indicators have a native polars equivalent (`ewm_mean`, `rolling_mean`).
  Adding a plugin version is a deliberate choice (consistency / a specific
  variant), not a perf necessity — a release-built plugin is competitive.
