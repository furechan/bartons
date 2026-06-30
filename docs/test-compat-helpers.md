# Test compatibility helpers

The plugin is built once (against polars crate 0.54.4 → polars 1.42) and is
verified to run on **every stable polars in `[1.0, 1.43)`** via the nox `compat`
matrix in [noxfile.py](../noxfile.py). To make the *same* test suite run
unchanged across that whole range, two small test-only shims exist. They are not
hacks — they are what keeps old-engine coverage possible. Do not delete them
unless the supported floor is raised to a polars new enough to make them moot.

## The everyday dev env runs the newest engine

The dev lockfile resolves polars to **1.42.x** (the engine the plugin is built
against), so `just test` exercises the full suite with **zero skips**. The shims
below only change behaviour on the *older* engines that the `compat` session
installs — they are inert on 1.42.

> History note: the dev lock was once pinned to **1.4.1** (an old-engine floor),
> which silently skipped 37 direct-call tests on every local `just test` run.
> That pin was the actual mistake and has been removed. The helpers themselves
> stayed, because the `compat` matrix still needs them.

## `tests/helpers.py` — portable `assert_series_equal`

`polars.testing.assert_series_equal` only gained the `rel_tol` / `abs_tol`
keywords in a later release. The suite compares floating-point indicator output
with a tolerance, so calling the real function with those kwargs raises
`TypeError` on polars 1.0–1.4.

[tests/helpers.py](../tests/helpers.py) is a drop-in replacement that reproduces
the subset of behaviour the suite uses (`check_names` / `check_dtype` /
`check_exact` / `rel_tol` / `abs_tol`) using only stable Series API (`len`,
`name`, `dtype`, `to_list`). Tests import it as:

```python
from helpers import assert_series_equal
```

## `tests/conftest.py` — skip direct `#[pyfunction]` calls on old engines

pyo3-polars marshals a `Series` into a raw `#[pyfunction]` (the
`plugin.<name>(series, ...)` surface) via `PySeries._export`, a polars *Python*
API that only exists in newer releases. On polars 1.0–1.4 those calls raise
`AttributeError`.

The registered-expression surfaces (`<NAME>()` and `.bt.<name>()`) do **not**
use `_export` and work across the full range. So [tests/conftest.py](../tests/conftest.py)
skips *only* the direct-call tests, and *only* when `PySeries._export` is absent
— detected once at collection time:

```python
HAS_PYFUNCTION = hasattr(pl.Series("x", [1.0])._s, "_export")
```

On polars 1.42 `HAS_PYFUNCTION` is `True`, so nothing is skipped. On an older
`compat` engine the direct-call tests are skipped with the reason
`pyo3-polars #[pyfunction] marshalling needs polars with PySeries._export`,
while the expression-path tests still run.

## When can these be removed?

Both shims become dead weight once the supported polars floor is raised above
the versions that need them:

- `helpers.py` — once the floor includes `rel_tol` / `abs_tol` in
  `polars.testing.assert_series_equal`; revert the imports back to
  `polars.testing`.
- `conftest.py` — once the floor has `PySeries._export` (polars ≥ 1.5); delete
  the file and the direct-call tests run everywhere.

Until then, raising the floor is the only correct way to drop them — never by
pinning the dev env to an old engine.
