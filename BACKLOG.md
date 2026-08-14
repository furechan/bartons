# Backlog

Items decided or considered but not scheduled. Add new items at the end.

## Rust

- Consider renaming `bartons/src/indicators/` to `bartons/src/kernels/`. Weigh against the deliberate symmetry from commit `8a6ba3c`, which renamed the Python side `expressions` → `indicators` partly so the same seven names appear on both sides of the FFI boundary — this would undo that. Counterpoint: the files hold the `#[polars_expr]` and `#[pyfunction]` wrappers too, so neither name is exact.

## Python

- Add `python/bartons/plugin.pyi` for the 7 pyfunctions plus `__version__`/`__all__`. Measured: takes `ty check` from 10 diagnostics to 1 — every remaining diagnostic is this gap. The last one would be `plugin.ema.__text_signature__` in `extras/test-ema.ipynb`, which a stubbed function does not carry.

## Tooling


