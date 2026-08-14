# bartons

Polars plugin providing financial/technical analysis expressions, implemented in Rust via PyO3 + Maturin. Currently exposes EMA (Exponential Moving Average), SMA (Simple Moving Average), RMA (Wilder's / running moving average), WMA (Weighted Moving Average), RSI (Wilder's Relative Strength Index), TRANGE (True Range), and ATR (Average True Range).

## Architecture

One crate, one Python package:

- `bartons/` — PyO3 `cdylib` crate, compiles to `python/bartons/plugin.abi3.so`
- `python/bartons/` — Python package wrapping the compiled plugin

The crate directory is named after the Cargo package (`bartons`), which is what
a Rust reader expects to find. Its `[lib] name = "plugin"` is what makes the
compiled module `bartons.plugin`.

Rust source layout: each indicator's kernel lives in `bartons/src/indicators/<name>.rs`
and is declared in `bartons/src/indicators/mod.rs`; the shared `Filter` trait, the
`run_unary`/`run_ternary` drivers and the `check_len!` length guard are in
`bartons/src/utils.rs` (crate root); and `bartons/src/lib.rs` is the `#[pymodule]` glue
that registers each eager pyfunction flat as `bartons.plugin.<name>`.

`Filter` carries an associated `Input`: `Option<f64>` for the single-series
kernels, and a three-tuple for TRANGE/ATR — spelled `utils::Triple` on the
arity-generic driver side and re-aliased `indicators::Hlc` on the kernel side.

The flat layout is deliberate — a `plugin.indicators` submodule was built and
rejected (`import bartons.plugin.indicators` needs a manual `sys.modules` hack that
isn't worth it for a private module). See
[docs/considered-alternatives.md](docs/considered-alternatives.md) for that and
other deferred designs.

The Python package and distribution are both `bartons`; the Rust module is imported as `bartons.plugin`. The name `bartons` was chosen to avoid colliding with the separate `bearta` TA library. Polars expressions are registered via `polars.plugins.register_plugin_function`.

## Build & test

```sh
just build       # maturin develop --release — optimized build, installed into .venv
just build-debug # maturin develop — fast unoptimized build (~20x slower at runtime)
just test        # pytest
just bench vs-native # build optimized, then run scripts/benchmark-vs-native.py
                     # (baselines: vs-native, vs-talib, vs-mintalib — bare
                     #  `just bench` defaults to a script that no longer exists)
just clean       # remove Rust target/ and compiled .so files
```

Requires the `.venv` to be active. The build tool is `uv`; use `uv sync` to set up the environment.

## Type checking

`ty` (Astral's type checker, https://github.com/astral-sh/ty) is the project's
designated type checker; run it as `uv run ty check`. The expression factories in
`python/bartons/indicators/` are the checkable surface, including the wrapped
single-source ones — `wrap_src_indicator` returns a `SrcIndicator` protocol
declaring both call forms as overloads, so `EMA(20)` and `EMA(pl.col("x"), 20)`
both type as `pl.Expr`.

The remaining diagnostics are the compiled `bartons.plugin` extension, which has
no `.pyi` stub. `evcxr/` is excluded in `[tool.ty.src]` — those are Rust
notebooks that ty would otherwise parse as Python. The runtime-registered `.bt`
namespace was retired partly because it could not be typed at all; see
[docs/namespace-legacy.md](docs/namespace-legacy.md).

## Adding a new indicator

See [docs/adding-an-indicator.md](docs/adding-an-indicator.md) for the full
checklist (entry points, naming, conventions, tests). In short: add a Rust
kernel + `#[polars_expr]` + `#[pyfunction]` in `bartons/src/indicators/<name>.rs`,
declare it with `pub mod <name>;` in `bartons/src/indicators/mod.rs`, register the
pyfunction in `bartons/src/lib.rs`, add the `<NAME>()` factory in
`python/bartons/indicators/<name>.py` (re-exported from
`python/bartons/indicators/__init__.py`), then mirror `tests/test_ema.py`.
EMA and SMA are the reference implementations.

## Key files

- [bartons/src/indicators/ema.rs](bartons/src/indicators/ema.rs) — reference implementation: EmaKwargs, `calc_ema`, expression + pyfunction wrappers
- [python/bartons/indicators/ema.py](python/bartons/indicators/ema.py) — Python-side plugin registration; factories live in the `indicators` sub-package (`from bartons.indicators import EMA`)
- [python/bartons/prelude.py](python/bartons/prelude.py) — shared factory machinery: `PLUGIN_PATH` and the `wrap_src_indicator` decorator (mirrors `bearta.prelude`)
- [pyproject.toml](pyproject.toml) — Maturin config (module name, python-source, manifest-path)
- [bartons/Cargo.toml](bartons/Cargo.toml) — Rust dependencies (pyo3, pyo3-polars, polars)

## Docs

Open work is tracked in [BACKLOG.md](BACKLOG.md).

- [docs/adding-an-indicator.md](docs/adding-an-indicator.md) — the end-to-end checklist
- [docs/design-review.md](docs/design-review.md) — review of the `Filter` + driver core; items 1 and 2 resolved, item 3 in the backlog
- [docs/considered-alternatives.md](docs/considered-alternatives.md) — designs deliberately not taken
- [docs/unified-run-driver.md](docs/unified-run-driver.md) — deferred proposal to collapse the two drivers into one; revisit when a fourth input arity appears
- [docs/namespace-legacy.md](docs/namespace-legacy.md) — the retired `.bt` accessor: its code and why it went
- [docs/benchmark-vs-talib.md](docs/benchmark-vs-talib.md) — recorded EMA benchmark vs polars_talib and native `ewm_mean` (2026-04-25)

Version/compatibility mechanics live in
[docs/cargo-version-pins.md](docs/cargo-version-pins.md),
[docs/polars-ffi-version-table.md](docs/polars-ffi-version-table.md),
[docs/polars-ffi-version-guard.md](docs/polars-ffi-version-guard.md),
[docs/polars-runtime-libraries.md](docs/polars-runtime-libraries.md) and
[docs/test-compat-helpers.md](docs/test-compat-helpers.md). The `compat`/`rt32`/`rt64`
matrix is driven by `noxfile.py` (`uv run nox -s rt32`), with session envs under
`.venv/.nox`.
