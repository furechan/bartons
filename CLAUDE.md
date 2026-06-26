# bartons

Polars plugin providing financial/technical analysis expressions, implemented in Rust via PyO3 + Maturin. Currently exposes EMA (Exponential Moving Average).

## Architecture

One crate, one Python package:

- `bartons/` — PyO3 `cdylib` crate, compiles to `python/bartons/plugin.abi3.so`
- `python/bartons/` — Python package wrapping the compiled plugin

The Python package and distribution are both `bartons`; the Rust module is imported as `bartons.plugin`. The name `bartons` was chosen to avoid colliding with the separate `bearta` TA library. Polars expressions are registered via `polars.plugins.register_plugin_function`.

## Build & test

```sh
just build   # maturin develop — compiles Rust and installs into .venv
just test    # pytest
just clean   # remove Rust target/ and compiled .so files
```

Requires the `.venv` to be active. The build tool is `uv`; use `uv sync` to set up the environment.

## Adding a new expression

1. Add a Rust function in `bartons/src/` annotated with `#[polars_expr(output_type = ...)]`
2. Register it in `bartons/src/lib.rs` alongside the existing functions
3. Add a Python wrapper in `python/bartons/` following the pattern in `ema.py`
4. Optionally expose it via the `BartonsExprNamespace` in `expr.py` (`.bt.<name>()`)

## Key files

- [bartons/src/ema.rs](bartons/src/ema.rs) — reference implementation: EmaKwargs, `calc_ema`, expression + pyfunction wrappers
- [python/bartons/ema.py](python/bartons/ema.py) — Python-side plugin registration
- [python/bartons/expr.py](python/bartons/expr.py) — `@pl.api.register_expr_namespace("bt")` class
- [pyproject.toml](pyproject.toml) — Maturin config (module name, python-source, manifest-path)
- [bartons/Cargo.toml](bartons/Cargo.toml) — Rust dependencies (pyo3, pyo3-polars, polars)
