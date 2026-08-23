# bartons

Polars plugin providing financial/technical analysis expressions, implemented in Rust via PyO3 + Maturin. Currently exposes EMA, DEMA, TEMA, HMA, ZLEMA, ALMA, SMA, RMA, WMA, RSI, TRANGE, ATR, MAD, CCI, MFI, DMI, KER, KAMA, SAR, STREAK, the LINREG and QUADREG families, and the kernel-free MACD and price transforms (AVGPRICE, MEDPRICE, TYPPRICE, WCLPRICE).

## Architecture

Bartons has a Rust kernel layer and a Python expression layer; they serve
different roles and are not required to mirror one another. See
[docs/architecture.md](docs/architecture.md) for the source layout, boundaries,
and deliberate design choices.

## Build & test

```sh
uv run inv make          # install release extension, regenerate, test, type-check
uv run inv build         # build sdist -> wheel in dist/, then test the wheel
uv run inv dump          # list what went into the sdist
uv run inv publish       # upload the tested artifacts in dist/
uv run inv test          # native Rust tests, then pytest
uv run inv bench         # release build, then benchmark (default: vs-native)
                         # also: --baseline=vs-talib or --baseline=vs-mintalib
uv run inv stubs         # regenerate kernel and indicator package stubs
uv run inv raise-ceiling # test newest polars-py and raise the ceiling if it passes
uv run inv clean         # remove Rust targets and compiled .so files

# Native Rust bench/example targets must link libpython. The default
# extension-module feature deliberately does not. `.envrc` configures PyO3 and
# the runtime linker to use the project's uv-managed Python.
cargo bench --manifest-path bartons/Cargo.toml --no-default-features
```

`inv make` prepares the source tree: it installs an optimized extension into the
`.venv`, regenerates checked-in stubs and README content, then runs tests and
type checking. `inv build` is the complete artifact phase: it clears `dist/`,
creates the sdist, builds the wheel from that sdist, then installs and tests the
wheel in an isolated Nox environment. The persistent Cargo target under `.venv`
keeps subsequent source builds fast.

`extension-module` is a default Cargo feature because wheel builds are the
normal path. Cargo features are additive, so native Rust executables use
`--no-default-features`; there is intentionally no empty opposing feature.
This changes PyO3's linkage mode, not the generated Rust code: native targets
link libpython, while the Python extension resolves those symbols from its host
interpreter.

Requires the `.venv` to be active. The build tool is `uv`; use `uv sync` to set up the environment.

## Git workflow

Unless the user explicitly requests a different workflow, work directly on the
`main` branch and push commits directly to `main`. Do not create a feature branch
or pull request by default.

## Release workflow

**This local path owns releases.** `.github/workflows/build.yml` and
`publish.yml` are experimental, inactive, and have never published anything — see
[docs/github-workflow.md](docs/github-workflow.md), which also records that their
server-side configuration is incomplete. They are a second upload path for the
same artifacts, and PyPI never frees a filename, so publishing a version through
both is not recoverable. Do not release through CI without deciding to move
ownership there first.


Run releases from a clean branch that is fully synchronized with its upstream.
Do not publish from a branch that is ahead, behind, or has uncommitted work that
is not intended for the release.

1. Fetch and verify repository state with `git fetch`, `git status`, and
   `git rev-list --left-right --count @{upstream}...HEAD`. Both counts must be
   zero before proceeding.
2. Review `README.md` against the release as it now stands. Update it when the
   public API, supported versions, examples, installation instructions, or
   documented indicator set changed.
3. Review the complete diff and commit and push all intended release changes,
   including any README update. Do not create an empty checkpoint commit when
   nothing changed.
4. Run `uv run inv build`. It clears `dist/`, creates the sdist, builds the
   native Linux ARM64 wheel from that sdist, and tests the wheel outside the
   checkout. This is the only build-and-validation phase.
5. Inspect the prepared files and build output. Releases ship a native ARM64
   wheel and the sdist only — the cross-compiled AMD64 wheel was dropped on
   2026-08-21 because it could not be imported here, so nothing untested goes out.
   x86_64 users build from the sdist, which needs a Rust toolchain. Restore the
   AMD64 wheel when CI can smoke-test it natively; see
   [docs/github-workflow.md](docs/github-workflow.md).
6. Run `uv run inv publish`. It never compiles: it verifies the clean,
   synchronized branch and unused PyPI version, pauses for confirmation, uploads
   the wheel and sdist currently in `dist/`, and bumps the patch version.
7. After publishing succeeds, review the version bump, commit it, and push.

Never continue past a failed build, test, synchronization check, version guard,
artifact validation, upload, or PyPI verification. Retain and review the publish
output as part of the release record.

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
[benchmarks/builder-vs-collect.rs](benchmarks/builder-vs-collect.rs).

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
typed at all.

`uv run inv stubs` runs two focused generators. `scripts/generate-kernel-stubs.py`
introspects the built extension for `python/bartons/kernels.pyi`; pyo3 exposes
parameter names, defaults and docstrings but **no types**, so those come from a
small `PARAM_TYPES` map and an unmapped name is a hard error. The indicator
package uses dynamic runtime `__all__`, so `scripts/generate-indicator-stubs.py`
reads each implementation module's literal `__all__` and writes explicit typed
re-exports to `python/bartons/indicators/__init__.pyi`. Commit both generated
stubs. `python/bartons/py.typed` makes them visible to consumers.

## Adding a new indicator

See [docs/adding-an-indicator.md](docs/adding-an-indicator.md) for the full
checklist (entry points, naming, conventions, tests). In short: add a Rust
kernel + `#[polars_expr]` + `#[pyfunction]` in `bartons/src/kernels/<name>.rs`,
declare it with `pub mod <name>;` in `bartons/src/kernels/mod.rs`, register the
pyfunction in `bartons/src/lib.rs`, add the `<NAME>()` factory in
`python/bartons/indicators/<name>.py` with its module-owned `__all__`, add one
star import for that module in
`python/bartons/indicators/__init__.py`, then mirror `tests/test_ema.py`.
EMA and SMA are the reference implementations.

## Key files

- [bartons/src/kernels/ema.rs](bartons/src/kernels/ema.rs) — reference implementation: the `ema` kernel, `EmaKwargs`, and the `ema_expr` / `ema_py` bindings
- [python/bartons/indicators/ema.py](python/bartons/indicators/ema.py) — Python-side plugin registration; factories live in the `indicators` sub-package (`from bartons.indicators import EMA`)
- [python/bartons/prelude.py](python/bartons/prelude.py) — shared factory machinery: `PLUGIN_PATH` and the `wrap_src_indicator` decorator (mirrors `bearta.prelude`)
- [pyproject.toml](pyproject.toml) — Maturin config (module name, python-source, manifest-path)
- [bartons/Cargo.toml](bartons/Cargo.toml) — Rust dependencies (pyo3, pyo3-polars, polars)

## Docs

Open work is tracked in [BACKLOG.md](BACKLOG.md).

- [docs/architecture.md](docs/architecture.md) — project layers, boundaries, and source layout
- [docs/github-workflow.md](docs/github-workflow.md) — the two dispatch-only GitHub Actions
  workflows in `.github/workflows/`, **experimental and never run**, plus the cost analysis
  behind their shape and the PyPI facts (immutable `Requires-Dist`, filenames never
  reusable, yank-not-delete)
- [docs/adding-an-indicator.md](docs/adding-an-indicator.md) — the end-to-end checklist
- [docs/unified-run-driver.md](docs/unified-run-driver.md) — implemented typed `run_filter` design; new dtypes or source arities add only the concrete `FilterInput` signature they require
- [docs/builder-vs-collect-benchmark.md](docs/builder-vs-collect-benchmark.md) — recorded kernel micro-benchmark (2026-08-17): the `Filter` abstraction is free, `append_option` costs ~1.6× — read before touching the builder append in `run_filter`
- [docs/izip-vs-index-benchmark.md](docs/izip-vs-index-benchmark.md) — recorded driver micro-benchmark (2026-08-18): hoisting the per-element downcast beats `ChunkedArray::iter()`; the unified driver's numeric `FilterInput` paths use `FastIter`, which ties the native Arrow iterator in the unary single-chunk case

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
