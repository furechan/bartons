# bearta-plugin

Polars plugin providing financial/technical analysis expressions, implemented in Rust via PyO3 + Maturin. Currently exposes EMA (Exponential Moving Average).

## Architecture

One crate, one Python package:

- `bearta_plugin/` — PyO3 `cdylib` crate, compiles to `python/bearta_plugin/plugin.abi3.so`
- `python/bearta_plugin/` — Python package wrapping the compiled plugin

The Python package is `bearta_plugin` (distribution `bearta-plugin`); the Rust module is imported as `bearta_plugin.plugin`. The import namespace is `bearta_plugin` to avoid colliding with the separate `bearta` TA library. Polars expressions are registered via `polars.plugins.register_plugin_function`.

## Build & test

```sh
just build   # maturin develop — compiles Rust and installs into .venv
just test    # pytest
just clean   # remove Rust target/ and compiled .so files
```

Requires the `.venv` to be active. The build tool is `uv`; use `uv sync` to set up the environment.

## Adding a new expression

1. Add a Rust function in `bearta_plugin/src/` annotated with `#[polars_expr(output_type = ...)]`
2. Register it in `bearta_plugin/src/lib.rs` alongside the existing functions
3. Add a Python wrapper in `python/bearta_plugin/` following the pattern in `ema.py`
4. Optionally expose it via the `BeartaExprNamespace` in `expr.py` (`.bt.<name>()`)

## Key files

- [bearta_plugin/src/ema.rs](bearta_plugin/src/ema.rs) — reference implementation: EmaKwargs, `calc_ema`, expression + pyfunction wrappers
- [python/bearta_plugin/ema.py](python/bearta_plugin/ema.py) — Python-side plugin registration
- [python/bearta_plugin/expr.py](python/bearta_plugin/expr.py) — `@pl.api.register_expr_namespace("bt")` class
- [pyproject.toml](pyproject.toml) — Maturin config (module name, python-source, manifest-path)
- [bearta_plugin/Cargo.toml](bearta_plugin/Cargo.toml) — Rust dependencies (pyo3, pyo3-polars, polars)
