# Polars Plugin ABI Compatibility

> [!WARNING]
> **LEGACY / INCOMPLETE — DO NOT USE AS REFERENCE (as of 2026-06-30).**
> This note predates the first-hand source analysis of the FFI version guard. Parts of it are inaccurate — notably its "strict `PYPOLARS_VERSION` match" description of the runtime check and its approximate Python↔Rust version table. The verified, fact-only material lives in [`polars-ffi-version-table.md`](../docs/polars-ffi-version-table.md) and [`polars-ffi-version-guard.md`](../docs/polars-ffi-version-guard.md). Retained for historical context only.

The core problem with Polars Rust plugins (via pyo3-polars): **the compiled `.so` is tightly coupled to the exact Polars version it was built against.**

## Why the coupling exists

Polars plugins are not ordinary PyO3 extensions. When `register_plugin_function` is called, Polars loads the `.so` at runtime and passes its internal Rust structs (`Series`, `ChunkedArray`, etc.) directly across the FFI boundary. Both sides must have been compiled against the same Rust `polars` crate — same struct layouts, same field offsets.

This is fundamentally different from `abi3` Python extensions, where only Python C API types cross the boundary. Here it's Polars' own types, and they change frequently.

## The runtime check

pyo3-polars enforces a strict `PYPOLARS_VERSION` match at plugin load time. A version mismatch is a **hard error**, not silent corruption. The Python polars package embeds the Rust crate version it was compiled against; the plugin embeds the same; they must agree.

This check was introduced in a later version of pyo3-polars. Plugins compiled against older versions (e.g. pyo3-polars 0.10) have no check baked in and load unconditionally — see the polars-talib note below.

## Version mapping

The Rust `polars` crate version and the Python `polars` package version use different numbering:

| Python polars | Rust polars crate |
|---|---|
| 1.3.x | ~0.43.x |
| 1.10.x | ~0.46.x |
| 1.30.x | ~0.53.x |

There is no fixed formula — check `pyo3-polars` release notes for the exact pairing.

## No stable ABI planned

As of mid-2025, the Polars team has not planned or started work on a stable plugin ABI:

- No RFC, issue, or roadmap entry exists for it
- Polars 1.0 explicitly scoped API stability to end-user Python APIs only
- pyo3-polars was absorbed into the main polars repo (July 2025) — consolidation, not stabilisation
- Polars cuts a new minor roughly every 2 weeks, making ABI commitments difficult

The strict version-match check *is* the intended contract.

## How distributed plugins handle it

**Appears to work but is fragile** (e.g. `polars-talib`): compiled against polars 0.36.2 / pyo3-polars 0.10, with `polars >= 0.19` declared as a Python dependency. Installs and runs against polars 1.30.0 because:
1. pyo3-polars 0.10 predates the `PYPOLARS_VERSION` check — no version enforcement is compiled in
2. The `Series` memory layout (backed by Arrow C Data Interface) hasn't changed enough between 0.36 and 0.53 to corrupt basic float operations

This works by coincidence, not design. A future polars release could silently corrupt results or segfault.

**Correct approach** (e.g. `polars-distance`, `polars-hash`): release a new plugin version for each polars minor. CI matrix builds wheels for each supported polars version × platform. PyPI has many wheels per plugin release.

## Practical workflow for personal/internal plugins (uv)

For plugins not published to PyPI, use editable local path installs:

```sh
# In each consumer project
uv add --editable /path/to/my-plugin
```

uv calls maturin as the build backend and compiles the `.so` into that project's venv. The Rust `polars` crate version in the plugin's `Cargo.toml` must match the Python polars version in the consumer project.

**On polars upgrade:**
1. Update `polars` and `polars-arrow` in the plugin's `Cargo.toml`
2. Update `pyo3-polars` to the matching version
3. In each consumer project: `uv sync --reinstall-package <plugin-name>`

This triggers a rebuild — maturin recompiles the Rust code against the new crate versions.

## The cost

Every polars minor version upgrade requires a rebuild of every plugin in every consumer project. For a distributed library this means CI matrix wheel publishing. For internal tools it means one `Cargo.toml` edit + one `uv sync --reinstall-package` per project.

## Key version table (as of 2026-04)

| Package | Version at last check |
|---|---|
| Python polars | 1.30.0 |
| Rust `polars` crate | 0.53.0 |
| `pyo3-polars` | 0.26.0 |
| `pyo3` | 0.28.3 |
