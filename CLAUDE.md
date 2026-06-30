# bartons

Polars plugin providing financial/technical analysis expressions, implemented in Rust via PyO3 + Maturin. Currently exposes EMA (Exponential Moving Average), SMA (Simple Moving Average), RMA (Wilder's / running moving average), WMA (Weighted Moving Average), RSI (Wilder's Relative Strength Index), TRANGE (True Range), and ATR (Average True Range).

## Architecture

One crate, one Python package:

- `bartons/` — PyO3 `cdylib` crate, compiles to `python/bartons/plugin.abi3.so`
- `python/bartons/` — Python package wrapping the compiled plugin

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

## Adding a new indicator

See [docs/adding-an-indicator.md](docs/adding-an-indicator.md) for the full
checklist (entry points, naming, conventions, tests). In short: add a Rust
kernel + `#[polars_expr]` + `#[pyfunction]` in `bartons/src/<name>.rs`, register
in `bartons/src/lib.rs`, add the `<NAME>()` factory in
`python/bartons/expressions/<name>.py` (re-exported from
`python/bartons/expressions/__init__.py`) and a `.bt.<name>()` method in
`namespace.py`, then mirror `tests/test_ema.py`.
EMA and SMA are the reference implementations.

## Key files

- [bartons/src/ema.rs](bartons/src/ema.rs) — reference implementation: EmaKwargs, `calc_ema`, expression + pyfunction wrappers
- [python/bartons/expressions/ema.py](python/bartons/expressions/ema.py) — Python-side plugin registration; factories live in the `expressions` sub-package (`from bartons.expressions import EMA`)
- [python/bartons/namespace.py](python/bartons/namespace.py) — `@pl.api.register_expr_namespace("bt")` class (the `.bt` accessor)
- [pyproject.toml](pyproject.toml) — Maturin config (module name, python-source, manifest-path)
- [bartons/Cargo.toml](bartons/Cargo.toml) — Rust dependencies (pyo3, pyo3-polars, polars)
