# Backlog

Items decided or considered but not scheduled. Add new items at the end.

## Rust

- De-duplicate the pyfunction tail ([design-review.md](docs/design-review.md) item 3): all 7 repeat the same four-line `match` into `PyRuntimeError`. Add `fn to_pyseries(r: PolarsResult<Series>) -> PyResult<PySeries>` to `utils.rs`.
- De-duplicate the kernel error (same item): 6 kernels return `Result<Self, String>` then `map_err(…ComputeError…)?` a line later. Prefer a local `KernelError` + `impl From<KernelError> for PolarsError` (compiles; `?` then converts, so the `map_err` vanishes) over the review's `polars_bail!` in `new()`, which would put a polars type in every kernel constructor and lose the polars-independence that error buys.
- Switch invalid-period errors to `PyValueError` from `PyRuntimeError` (same item). Behavior change — tighten `test_invalid_period_pyfunction`, which catches bare `Exception`, alongside it.
- Consider renaming `bartons/src/indicators/` to `bartons/src/kernels/`. Weigh against the deliberate symmetry from commit `8a6ba3c`, which renamed the Python side `expressions` → `indicators` partly so the same seven names appear on both sides of the FFI boundary — this would undo that. Counterpoint: the files hold the `#[polars_expr]` and `#[pyfunction]` wrappers too, so neither name is exact.

## Python

- Add `python/bartons/plugin.pyi` for the 7 pyfunctions plus `__version__`/`__all__`. Measured: takes `ty check` from 11 diagnostics to 1.
- Fix the stale `import minimal_plugin` in `extras/plugin-version.ipynb`.

## Tooling

- Fix the `justfile` `bench` recipe: it defaults to `indicator="ema"` and so runs `scripts/benchmark-ema.py`, which no longer exists — benchmarks are per-baseline now (`benchmark-vs-native.py`, `-vs-talib.py`, `-vs-mintalib.py`). Bare `just bench` fails; `just bench vs-native` works. Pick a default baseline or drop the default.
- Consider `invoke` (`tasks.py`) instead of `just`. `invoke` is already a dev dependency here but unused — there is no `tasks.py` — while both `python-dev` and `bearta` drive their workflows through one, so this would align the sibling projects on a single runner.
- Consider `tox` instead of `nox`. Weigh against what the current `noxfile.py` already buys: the uv backend, one `maturin build --release` wheel shared across all 10 sessions rather than 10 recompiles, and the `POLARS_FORCE_PKG` engine switching for `rt32`/`rt64`. Those are the parts that would need re-expressing.
