# bartons

Polars plugin providing financial/technical analysis expressions, implemented in Rust via PyO3 + Maturin. Currently exposes EMA (Exponential Moving Average), SMA (Simple Moving Average), RMA (Wilder's / running moving average), WMA (Weighted Moving Average), RSI (Wilder's Relative Strength Index), TRANGE (True Range), and ATR (Average True Range).

## Architecture

One crate, one Python package:

- `rust/` — PyO3 `cdylib` crate, compiles to `python/bartons/plugin.abi3.so`
- `python/bartons/` — Python package wrapping the compiled plugin

The two source roots are named for their language, not the project, so the split
is visible at the repo root. The crate's Cargo package is still `bartons`; its
`[lib] name = "plugin"` is what makes the compiled module `bartons.plugin`.

Rust source layout: each indicator's kernel lives in `rust/src/indicators/<name>.rs`
and is declared in `rust/src/indicators/mod.rs`; the shared `Filter` trait and
`run_unary`/`run_ternary` drivers are in `rust/src/utils.rs` (crate root); and
`rust/src/lib.rs` is the `#[pymodule]` glue that registers each eager pyfunction
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
kernel + `#[polars_expr]` + `#[pyfunction]` in `rust/src/indicators/<name>.rs`,
declare it with `pub mod <name>;` in `rust/src/indicators/mod.rs`, register the
pyfunction in `rust/src/lib.rs`, add the `<NAME>()` factory in
`python/bartons/indicators/<name>.py` (re-exported from
`python/bartons/indicators/__init__.py`), then mirror `tests/test_ema.py`.
EMA and SMA are the reference implementations.

## Key files

- [rust/src/indicators/ema.rs](rust/src/indicators/ema.rs) — reference implementation: EmaKwargs, `calc_ema`, expression + pyfunction wrappers
- [python/bartons/indicators/ema.py](python/bartons/indicators/ema.py) — Python-side plugin registration; factories live in the `indicators` sub-package (`from bartons.indicators import EMA`)
- [python/bartons/prelude.py](python/bartons/prelude.py) — shared factory machinery: `PLUGIN_PATH` and the `wrap_src_indicator` decorator (mirrors `bearta.prelude`)
- [pyproject.toml](pyproject.toml) — Maturin config (module name, python-source, manifest-path)
- [rust/Cargo.toml](rust/Cargo.toml) — Rust dependencies (pyo3, pyo3-polars, polars)
