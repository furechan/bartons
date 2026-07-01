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

## `tests/helpers.py` — `@requires_pyfunction` marker

pyo3-polars marshals a `Series` into a raw `#[pyfunction]` (the
`plugin.<name>(series, ...)` surface) via `PySeries._export`, a *private* polars
Python API. With the pinned **pyo3-polars 0.27**, that method is only present
from **polars 1.28** (1.27 lacks it); on older engines those calls raise
`AttributeError`.

The registered-expression surfaces (`<NAME>()` and `.bt.<name>()`) do **not**
use `_export` — the host engine marshals the Series internally over the stable
plugin FFI — so they work across the full supported range. Only the eager
direct-call tests need guarding.

[tests/helpers.py](../tests/helpers.py) exports a marker that skips a test when
`_export` is absent:

```python
requires_pyfunction = pytest.mark.skipif(
    not hasattr(pl.Series("x", [1.0])._s, "_export"),
    reason="eager plugin.<name> needs polars >= 1.28 (PySeries._export)",
)
```

Each eager test is decorated with `@requires_pyfunction`. On polars ≥ 1.28 the
condition is false so nothing is skipped; on an older `compat` engine those tests
skip while the expression-path tests still run. The condition is a *capability
probe*, not a version comparison, so it stays correct even if a pyo3-polars
upgrade moves the boundary — the "≥ 1.28" figure is specific to pyo3-polars 0.27.

> Earlier this was a `conftest.py` hook that auto-detected direct-call tests by
> grepping each test's source for `plugin.<name>(`. It was replaced with the
> explicit marker: simpler, and no fragile source inspection.

## When can these be removed?

Both shims become dead weight once the supported polars floor is raised above
the versions that need them:

- `helpers.py` — once the floor includes `rel_tol` / `abs_tol` in
  `polars.testing.assert_series_equal`; revert the imports back to
  `polars.testing`.
- the `@requires_pyfunction` marker (in `helpers.py`) — once the floor has
  `PySeries._export` (polars ≥ 1.28 with pyo3-polars 0.27); drop the marker and
  its `@requires_pyfunction` decorators, and the direct-call tests run everywhere.

Until then, raising the floor is the only correct way to drop them — never by
pinning the dev env to an old engine.
