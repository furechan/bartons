# Backlog

Items decided or considered but not scheduled. Add new items at the end.

## Rust

- Consider renaming `bartons/src/indicators/` to `bartons/src/kernels/`. Weigh against the deliberate symmetry from commit `8a6ba3c`, which renamed the Python side `expressions` → `indicators` partly so the same seven names appear on both sides of the FFI boundary — this would undo that. Counterpoint: the files hold the `#[polars_expr]` and `#[pyfunction]` wrappers too, so neither name is exact.

## Tooling


