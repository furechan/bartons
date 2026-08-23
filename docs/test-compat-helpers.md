# Test compatibility helpers

The plugin is built once (against polars-rs 0.55.2) and is
verified to run on **every stable polars-py in `[1.28, 1.44)`** via the nox
`compat` matrix in [noxfile.py](../noxfile.py). To make the *same* test suite
run unchanged across that whole range, one small test-only shim exists. It is not
a hack — it is what keeps old-engine coverage possible. Do not delete it unless
the supported floor is raised to a polars new enough to make it moot.

## Raising the ceiling

The ceiling is a **record of what the matrix has verified**, not a prediction — so
it goes stale as polars releases. Keep it current with:

```sh
uv run inv raise-ceiling
```

That looks up the newest polars-py, adds it to `COMPAT_VERSIONS`, runs the
`compat` session against it, and **only if that passes** moves the ceiling to the
next minor — then upgrades the dev env to match (`uv lock --upgrade-package
polars`, `uv sync`) and re-runs the suite. It changes nothing on failure, and
never commits.

Note the order: the compat session runs **before** the ceiling moves, deliberately.
`uv pip install polars==<new>` inside the session does not enforce the installed
wheel's `Requires-Dist`, so the matrix can probe a version the declared range does
not yet admit — which is what lets you verify before declaring rather than after.

Widening the ceiling to `<2.0` on the assumption that polars will not break the
plugin within `1.x` was considered and rejected: `PySeries._export` — private API
the eager path depends on — first appeared at polars-py `1.28`, a *minor*, which
is precisely why the floor is not `1.0`. Semver does not cover underscore-prefixed
API, so the surface that matters here has already moved inside `1.x` once.

## The everyday dev env runs the newest engine

The dev lockfile resolves polars-py to the **newest supported** release, so
`uv run inv test` exercises the full suite with **zero skips** against the same engine
the ceiling admits. `uv run inv raise-ceiling` keeps it that way: after the compat run
passes and the ceiling moves, it runs `uv lock --upgrade-package polars` and
`uv sync`, then re-runs the suite. Without that the newly-admitted version would
be tested once in a throwaway nox venv and never again. The shim below only
changes behaviour on the *older* engines the `compat` session installs.

Note this is **not** the engine the plugin is built against. The plugin links
polars-rs `0.55.2`, and no released polars-py ships that yet — every `1.43.x`
still resolves to `0.54.4`. So even the everyday dev run is a cross-crate test
over the stable FFI boundary, which is the guarantee the pins exist to provide.

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
`conftest.py` hook that grepped each test's source for `kernels.<name>(` to
auto-detect the direct-call tests.
