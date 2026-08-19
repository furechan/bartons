# bartons

Polars plugin providing financial/technical analysis expressions, implemented in Rust via PyO3 + Maturin. Currently exposes EMA (Exponential Moving Average), SMA (Simple Moving Average), RMA (Wilder's / running moving average), WMA (Weighted Moving Average), RSI (Wilder's Relative Strength Index), TRANGE (True Range), and ATR (Average True Range).

## Architecture

One crate, one Python package:

- `bartons/` — PyO3 `cdylib` crate, compiles to `python/bartons/kernels.abi3.so`
- `python/bartons/` — Python package wrapping the compiled plugin

The crate directory is named after the Cargo package (`bartons`), which is what
a Rust reader expects to find. Its `[lib] name = "kernels"` is what makes the
compiled module `bartons.kernels`.

**The two layers are not mirrors.** Rust holds *kernels* — materialized vector
computations, series in and series out, written where polars cannot express the
logic or would be materially slower. Python holds *indicators* — expression
factories that compose on top. Today the sets happen to coincide (seven of each),
but that is incidental: a composite like BBANDS is `SMA ± k·std` and belongs in
Python with no Rust counterpart. The directories are named for those roles
(`bartons/src/kernels/` vs `python/bartons/indicators/`) precisely so the
divergence reads as intended rather than as drift.

Rust source layout: each indicator's kernel lives in `bartons/src/kernels/<name>.rs`
and is declared in `bartons/src/kernels/mod.rs`; the shared `Filter` trait, the
`run_unary`/`run_ternary` drivers and the `check_len!` length guard are in
`bartons/src/utils.rs` (crate root); and `bartons/src/lib.rs` is the `#[pymodule]` glue
that registers each eager pyfunction flat as `bartons.kernels.<name>`.

`Filter` carries an associated `Input`: `Option<f64>` for the single-series
kernels, and a three-tuple for TRANGE/ATR — spelled `utils::Triple` on the
arity-generic driver side and re-aliased `kernels::Hlc` on the kernel side.

The flat layout is deliberate — a `kernels.indicators` submodule was built and
rejected (`import bartons.kernels.indicators` needs a manual `sys.modules` hack that
isn't worth it). See
[docs/considered-alternatives.md](docs/considered-alternatives.md) for that and
other deferred designs.

The Python package and distribution are both `bartons`; the Rust module is imported as `bartons.kernels`. The name `bartons` was chosen to avoid colliding with the separate `bearta` TA library. Polars expressions are registered via `polars.plugins.register_plugin_function`.

## Build & test

```sh
just develop       # maturin develop --release — optimized, installed into .venv
just develop-debug # maturin develop — fast unoptimized build (~20x slower at runtime)
just build         # maturin build — wheel + sdist into dist/, installs nothing
just dump          # list what went into the sdist
just publish       # guarded upload of dist/ to PyPI
just test          # native Rust tests, then pytest
just bench         # develop, then benchmark vs a baseline
                   # (default vs-native; also vs-talib, vs-mintalib)
just stubs         # regenerate python/bartons/kernels.pyi from the built module
just raise-ceiling # test the newest polars-py; raise the pyproject ceiling if it passes
just clean         # remove Rust target/ and compiled .so files

# Native Rust bench/example targets must link libpython. The default
# extension-module feature deliberately does not. `.envrc` configures PyO3 and
# the runtime linker to use the project's uv-managed Python.
cargo bench --manifest-path bartons/Cargo.toml --no-default-features
```

`develop` and `build` mirror maturin's own verbs: `develop` installs into the
`.venv` (what you want for tests, benchmarks and stubs — all three depend on it),
`build` produces artifacts in `dist/` and installs nothing.

`extension-module` is a default Cargo feature because wheel builds are the
normal path. Cargo features are additive, so native Rust executables use
`--no-default-features`; there is intentionally no empty opposing feature.
This changes PyO3's linkage mode, not the generated Rust code: native targets
link libpython, while the Python extension resolves those symbols from its host
interpreter.

Requires the `.venv` to be active. The build tool is `uv`; use `uv sync` to set up the environment.

## Rust notebooks

`evcxr/` holds Rust prototyping notebooks on the [evcxr](https://github.com/evcxr/evcxr)
Jupyter kernel, installed by `scripts/install-evcxr.sh`. Each notebook declares
its crates in a versionless `:dep` cell, which resolves to whatever is newest
rather than tracking `bartons/Cargo.toml` — deliberate, since these compare
patterns rather than validate a version, and pinning them is what silently
rotted last time. Pin a single line when an experiment actually needs one.

Use the **same `:dep` block** in every notebook that needs one. The build cache
is keyed on the complete dependency set rather than per crate, so a set
differing by one crate pays its own ~80s build; identical sets share one.

`:cache` and `:opt 3` live in `~/.config/evcxr/init.evcxr`, managed in the
dotfiles repo — machine-level build settings, not project state. Without them
notebooks still work, just at ~80s per session instead of ~2s.

**Do not add an `evcxr.toml`.** It shadows `init.evcxr` entirely, settings and
`:dep` lines alike, and its schema has no cache key — so it disables `:cache`
and moves the build to kernel startup, past VS Code's launch timeout.
[evcxr/README.md](evcxr/README.md) records the measurements and the workarounds
that don't recover it.

Notebooks are for exploration only. Anything worth keeping goes to `docs/` with
its provenance — date, platform, resolved crate versions — because stored
notebook outputs carry none of that and read as current long after they aren't.
`evcxr/builder-vs-collect.ipynb` is the cautionary case: its recorded numbers
were both stale and confounded, and the corrected experiment now lives in
[scripts/builder-vs-collect.rs](scripts/builder-vs-collect.rs).

## Type checking

`ty` (Astral's type checker, https://github.com/astral-sh/ty) is the project's
designated type checker; run it as `uv run ty check`. The expression factories in
`python/bartons/indicators/` are the checkable surface, including the wrapped
single-source ones — `wrap_src_indicator` returns a `SrcIndicator` protocol
declaring both call forms as overloads, so `EMA(20)` and `EMA(pl.col("x"), 20)`
both type as `pl.Expr`.

`uv run ty check` is **clean** and should stay that way. Two things keep it so:
`python/bartons/kernels.pyi` (generated — see below) covers the compiled
extension, which a checker cannot otherwise see into; and `evcxr/` is excluded in
`[tool.ty.src]`, those being Rust notebooks ty would parse as Python. The
runtime-registered `.bt` namespace was retired partly because it could not be
typed at all; see [docs/namespace-legacy.md](docs/namespace-legacy.md).

The stub is generated by `just stubs`
([scripts/generate-stubs.py](scripts/generate-stubs.py)), which introspects the
built module rather than trusting a hand-written copy. pyo3 exposes parameter
names, defaults and docstrings but **no types**, so those come from a small
`PARAM_TYPES` map in the script; an unmapped parameter name is a hard error
rather than a silent `Any`. Commit the regenerated stub. `python/bartons/py.typed`
is the PEP 561 marker that makes the stub visible to *consumers* — without it a
downstream checker ignores it.

## Adding a new indicator

See [docs/adding-an-indicator.md](docs/adding-an-indicator.md) for the full
checklist (entry points, naming, conventions, tests). In short: add a Rust
kernel + `#[polars_expr]` + `#[pyfunction]` in `bartons/src/kernels/<name>.rs`,
declare it with `pub mod <name>;` in `bartons/src/kernels/mod.rs`, register the
pyfunction in `bartons/src/lib.rs`, add the `<NAME>()` factory in
`python/bartons/indicators/<name>.py` (re-exported from
`python/bartons/indicators/__init__.py`), then mirror `tests/test_ema.py`.
EMA and SMA are the reference implementations.

## Key files

- [bartons/src/kernels/ema.rs](bartons/src/kernels/ema.rs) — reference implementation: the `ema` kernel, `EmaKwargs`, and the `ema_expr` / `ema_py` bindings
- [python/bartons/indicators/ema.py](python/bartons/indicators/ema.py) — Python-side plugin registration; factories live in the `indicators` sub-package (`from bartons.indicators import EMA`)
- [python/bartons/prelude.py](python/bartons/prelude.py) — shared factory machinery: `PLUGIN_PATH` and the `wrap_src_indicator` decorator (mirrors `bearta.prelude`)
- [pyproject.toml](pyproject.toml) — Maturin config (module name, python-source, manifest-path)
- [bartons/Cargo.toml](bartons/Cargo.toml) — Rust dependencies (pyo3, pyo3-polars, polars)

## Docs

Open work is tracked in [BACKLOG.md](BACKLOG.md).

- [docs/adding-an-indicator.md](docs/adding-an-indicator.md) — the end-to-end checklist
- [docs/design-review.md](docs/design-review.md) — review of the `Filter` + driver core; all three items resolved or deliberately declined
- [docs/considered-alternatives.md](docs/considered-alternatives.md) — designs deliberately not taken
- [docs/unified-run-driver.md](docs/unified-run-driver.md) — deferred proposal to collapse the two drivers into one; revisit when a fourth input arity appears
- [docs/namespace-legacy.md](docs/namespace-legacy.md) — the retired `.bt` accessor: its code and why it went
- [docs/benchmark-vs-talib.md](docs/benchmark-vs-talib.md) — recorded EMA benchmark vs polars_talib and native `ewm_mean` (2026-04-25)
- [docs/builder-vs-collect-benchmark.md](docs/builder-vs-collect-benchmark.md) — recorded kernel micro-benchmark (2026-08-17): the `Filter` abstraction is free, `append_option` costs ~1.6× — read before touching the append in `run_unary`/`run_ternary`
- [docs/izip-vs-index-benchmark.md](docs/izip-vs-index-benchmark.md) — recorded driver micro-benchmark (2026-08-18): hoisting the per-element downcast beats `ChunkedArray::iter()`; both drivers use `FastIter`, which ties the native Arrow iterator in the unary single-chunk case

**Two artifacts are both called "polars"**, on unrelated version schemes, so a
bare "polars 0.54" is ambiguous. These docs say **polars-rs** for the Rust crate
(`0.5x`, `bartons/Cargo.toml`, compiled into the `.so`) and **polars-py** for the
Python package (`1.4x`, `[project].dependencies`, resolved into the venv) —
borrowed from upstream's own `rs-*` / `py-*` release tags. Defined in the Naming
section of [docs/cargo-version-pins.md](docs/cargo-version-pins.md).

Version/compatibility mechanics live in that doc plus
[docs/polars-ffi-version-table.md](docs/polars-ffi-version-table.md),
[docs/polars-ffi-version-guard.md](docs/polars-ffi-version-guard.md),
[docs/polars-runtime-libraries.md](docs/polars-runtime-libraries.md) and
[docs/test-compat-helpers.md](docs/test-compat-helpers.md). The `compat`/`rt32`/`rt64`
matrix is driven by `noxfile.py` (`uv run nox -s rt32`), with session envs under
`.venv/.nox`.
