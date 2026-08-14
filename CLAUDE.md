# bartons

Polars plugin providing financial/technical analysis expressions, implemented in Rust via PyO3 + Maturin. Currently exposes EMA (Exponential Moving Average), SMA (Simple Moving Average), RMA (Wilder's / running moving average), WMA (Weighted Moving Average), RSI (Wilder's Relative Strength Index), TRANGE (True Range), and ATR (Average True Range).

## Architecture

One crate, one Python package:

- `bartons/` — PyO3 `cdylib` crate, compiles to `python/bartons/plugin.abi3.so`
- `python/bartons/` — Python package wrapping the compiled plugin

Rust source layout: each indicator's kernel lives in `bartons/src/indicators/<name>.rs`
and is declared in `bartons/src/indicators/mod.rs`; the shared `Filter` trait and
`run_unary`/`run_ternary` drivers are in `bartons/src/utils.rs` (crate root); and
`bartons/src/lib.rs` is the `#[pymodule]` glue that registers each eager pyfunction
flat as `bartons.plugin.<name>`.

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
just bench       # build optimized, then run the EMA benchmark
just clean       # remove Rust target/ and compiled .so files
```

Requires the `.venv` to be active. The build tool is `uv`; use `uv sync` to set up the environment.

## Type checking

`ty` (Astral's type checker, https://github.com/astral-sh/ty) is the project's
designated type checker. Note the expression factories in
`python/bartons/indicators/` are the statically-checkable surface; the `.bt`
accessor is registered at runtime via `@pl.api.register_expr_namespace` and is
invisible to any type checker unless a `.pyi` stub declares `bt: BartonsExprNamespace`
on `pl.Expr`.

## Adding a new indicator

See [docs/adding-an-indicator.md](docs/adding-an-indicator.md) for the full
checklist (entry points, naming, conventions, tests). In short: add a Rust
kernel + `#[polars_expr]` + `#[pyfunction]` in `bartons/src/indicators/<name>.rs`,
declare it with `pub mod <name>;` in `bartons/src/indicators/mod.rs`, register the
pyfunction in `bartons/src/lib.rs`, add the `<NAME>()` factory in
`python/bartons/indicators/<name>.py` (re-exported from
`python/bartons/indicators/__init__.py`) and a `.bt.<name>()` method in
`namespace.py`, then mirror `tests/test_ema.py`.
EMA and SMA are the reference implementations.

## Key files

- [bartons/src/indicators/ema.rs](bartons/src/indicators/ema.rs) — reference implementation: EmaKwargs, `calc_ema`, expression + pyfunction wrappers
- [python/bartons/indicators/ema.py](python/bartons/indicators/ema.py) — Python-side plugin registration; factories live in the `indicators` sub-package (`from bartons.indicators import EMA`)
- [python/bartons/prelude.py](python/bartons/prelude.py) — shared factory machinery: `PLUGIN_PATH` and the `wrap_src_indicator` decorator (mirrors `bearta.prelude`)
- [python/bartons/namespace.py](python/bartons/namespace.py) — `@pl.api.register_expr_namespace("bt")` class (the `.bt` accessor)
- [pyproject.toml](pyproject.toml) — Maturin config (module name, python-source, manifest-path)
- [bartons/Cargo.toml](bartons/Cargo.toml) — Rust dependencies (pyo3, pyo3-polars, polars)
