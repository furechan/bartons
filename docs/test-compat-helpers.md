# Test compatibility helpers

The plugin is built once (against polars crate 0.54.4 → polars 1.42) and is
verified to run on **every stable polars in `[1.28, 1.43)`** via the nox `compat`
matrix in [noxfile.py](../noxfile.py). To make the *same* test suite run
unchanged across that whole range, one small test-only shim exists. It is not a
hack — it is what keeps old-engine coverage possible. Do not delete it unless the
supported floor is raised to a polars new enough to make it moot.

> The floor is **1.28** because the eager `bartons.plugin.<name>` pyfunctions
> marshal a Series into Rust via `PySeries._export`, which polars only exposes
> from 1.28; on older engines they raise `AttributeError: 'PySeries' object has
> no attribute '_export'`. The package declares `polars>=1.28` for the same
> reason (see [pyproject.toml](../pyproject.toml)). The expression path (`EMA()`)
> needs no `_export` and would work lower, but 1.28 is where the
> whole public API is usable.

## The everyday dev env runs the newest engine

The dev lockfile resolves polars to **1.42.x** (the engine the plugin is built
against), so `just test` exercises the full suite with **zero skips**. The shim
below only changes behaviour on the *older* engines that the `compat` session
installs — it is inert on 1.42.

## `tests/helpers.py` — portable `assert_series_equal`

`polars.testing.assert_series_equal` only gained the `rel_tol` / `abs_tol`
keywords in **polars 1.32.3**. The suite compares floating-point indicator output
with a tolerance, so calling the real function with those kwargs raises
`TypeError` on the older engines the matrix still covers (polars 1.28–1.32.2).

[tests/helpers.py](../tests/helpers.py) is a drop-in replacement that reproduces
the subset of behaviour the suite uses (`check_names` / `check_dtype` /
`check_exact` / `rel_tol` / `abs_tol`) using only stable Series API (`len`,
`name`, `dtype`, `to_list`). Tests import it as:

```python
from helpers import assert_series_equal
```

## When can this be removed?

The shim becomes dead weight once the supported polars floor is raised above the
version that needs it:

- `helpers.py` — once the floor includes `rel_tol` / `abs_tol` in
  `polars.testing.assert_series_equal` (polars ≥ 1.32.3); revert the imports back
  to `polars.testing`.

Until then, raising the floor is the only correct way to drop it — never by
pinning the dev env to an old engine.

## History: the `@requires_pyfunction` marker

The eager direct-call tests were once guarded by a `@requires_pyfunction` marker
(in `tests/helpers.py`) that skipped them when `PySeries._export` was absent —
i.e. on polars < 1.28. When the supported floor was raised to 1.28 in **both**
[pyproject.toml](../pyproject.toml) and the `compat` matrix, every tested engine
gained `_export`, so the marker's `skipif` was permanently false. It and its
decorators were removed. Earlier still, that marker had itself replaced a
`conftest.py` hook that grepped each test's source for `plugin.<name>(` to
auto-detect the direct-call tests.
