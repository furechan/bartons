# Backlog

Items decided or considered but not scheduled. Add new items at the end.

## Rust

- De-duplicate the pyfunction tail ([design-review.md](docs/design-review.md) item 3): all 7 repeat the same four-line `match` into `PyRuntimeError`. Add `fn to_pyseries(r: PolarsResult<Series>) -> PyResult<PySeries>` to `utils.rs`.
- De-duplicate the kernel error (same item): 6 kernels return `Result<Self, String>` then `map_err(…ComputeError…)?` a line later. Prefer a local `KernelError` + `impl From<KernelError> for PolarsError` (compiles; `?` then converts, so the `map_err` vanishes) over the review's `polars_bail!` in `new()`, which would put a polars type in every kernel constructor and lose the polars-independence that error buys.
- Switch invalid-period errors to `PyValueError` from `PyRuntimeError` (same item). Behavior change — tighten `test_invalid_period_pyfunction`, which catches bare `Exception`, alongside it.

## Python

- Add `python/bartons/plugin.pyi` for the 7 pyfunctions plus `__version__`/`__all__`. Measured: takes `ty check` from 11 diagnostics to 1.
- Fix the stale `import minimal_plugin` in `extras/plugin-version.ipynb`.
