# Backlog

Items decided or considered but not scheduled. Add new items at the end.

## Rust

- Review the `abi3-py38` choice in [bartons/Cargo.toml](bartons/Cargo.toml). It builds a `cp38-abi3` wheel while `pyproject.toml` declares `requires-python = ">=3.11"`, so the ABI floor sits three minors below the version the package will actually install on. Raising it to `abi3-py311` would align the two and widen the stable-ABI surface pyo3 may use; keeping `py38` preserves headroom if the floor is ever relaxed. Data point: `pyo3-stub-gen` requires 3.10+, so the current level already ruled out one tool (see the CHANGELOG entry on stub generation).

## Tooling


