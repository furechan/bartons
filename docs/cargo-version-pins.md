# Cargo.toml Version Pins

How to choose and set the Rust crate versions in [`bartons/Cargo.toml`](../bartons/Cargo.toml) for the plugin. This is the **compile-time** side: these pins fully determine the `.so` that gets built, independent of the Python `polars` installed in the venv (see [`polars-ffi-version-guard.md`](polars-ffi-version-guard.md) for the separate runtime concern).

Facts below are read from `bartons/Cargo.toml`, `bartons/Cargo.lock`, and the crates.io dependencies API.

## What is pinned and why

Four interlocking crates:

| Crate | Role |
|---|---|
| `pyo3-polars` | The plugin framework: generates the FFI entry points and exports the version handshake. **The dial** — see below. |
| `polars` | The Rust polars crate, statically linked into the `.so`. Provides `Series`/`ChunkedArray` and the kernels. |
| `polars-arrow` | Polars' Arrow layer; must move in lockstep with `polars`. |
| `pyo3` | The Python ⇆ Rust binding layer (`#[pyfunction]`, the `extension-module`/`abi3` features). |

## The single dial: pick `pyo3-polars` first

`pyo3-polars` caret-pins **both** the polars crate family **and** the pyo3 range. So you do not choose `polars` or `pyo3` independently — you choose `pyo3-polars`, then read off what it requires and set the rest to satisfy it.

Read the requirements straight from crates.io (structured, no build needed):

```
GET https://crates.io/api/v1/crates/pyo3-polars/<ver>/dependencies
```

For `pyo3-polars 0.27.0` this returns:

| dependency | req |
|---|---|
| `polars` | `^0.54.4` |
| `polars-arrow` | `^0.54.4` |
| `pyo3` | `^0.28` |

## The interlock rules

1. **`polars` and `polars-arrow` must match the version `pyo3-polars` targets, and each other.** Pin both to the exact version `pyo3-polars` carets to (here `0.54.4`). They share struct layouts; a mismatch between them, or against the version compiled into `pyo3-polars`, is an ABI break.
2. **`pyo3` must satisfy `pyo3-polars`'s `pyo3` req — pin to that caret, not to "latest".** When upgrading, the newest published pyo3 is often *ahead* of what `pyo3-polars` accepts (pyo3 `0.29` existed while `pyo3-polars 0.27` wanted `^0.28`). Pin to the req.
3. **`extension-module` ⇒ exactly one `pyo3` in the build tree.** A direct `pyo3` pin that disagrees with `pyo3-polars`'s pulls in *two* pyo3 versions; pyo3's build script detects this and the build **fails hard** (it does not silently pick one). This is why rule 2 matters.

## Current pins (verified snapshot)

`bartons/Cargo.toml`:

```toml
pyo3 = { version = "0.28", features = ["extension-module", "abi3-py38"] }
pyo3-polars = { version = "0.27", features = ["derive", "dtype-struct", "dtype-decimal", "dtype-array"] }
polars = { version = "0.54.4", features = ["dtype-struct"] }
polars-arrow = { version = "0.54.4", default-features = false }
```

Resolved in `bartons/Cargo.lock`:

| crate | resolved |
|---|---|
| `pyo3-polars` | `0.27.0` |
| `polars` | `0.54.4` |
| `polars-arrow` | `0.54.4` |
| `pyo3` | `0.28.3` |

These exactly satisfy `pyo3-polars 0.27.0`'s requirements above.

## `abi3` — what it does and does not decouple

The `abi3-py38` feature builds against Python's stable ABI, so a single compiled `.so` works across Python `3.8+` without recompiling per Python minor. That decouples the plugin from the **Python interpreter** version — but **not** from the polars crate. The polars ABI is unaffected by `abi3`; it remains fixed by the `polars` crate pin.

## `bigidx` — for the runtime-64 engine

The default pins above produce a plugin for the default `polars-runtime-32` engine (`IdxSize = u32`). To target the `polars[rt64]` engine (`polars-runtime-64`, `IdxSize = u64`), add the `bigidx` feature to the `polars` dependency:

```toml
polars = { version = "0.54.4", features = ["dtype-struct", "bigidx"] }
```

`IdxSize` is a compile-time type, so one `.so` cannot serve both engines — a `bigidx` build is a separate artifact. For the default install this is unnecessary; see [`polars-runtime-libraries.md`](polars-runtime-libraries.md) for what the runtime variants are and when a `bigidx` build is actually needed.

## Procedure to set or bump the pins

1. Choose the `pyo3-polars` version (e.g. latest, or whichever you target).
2. `GET https://crates.io/api/v1/crates/pyo3-polars/<ver>/dependencies` → note the `polars`, `polars-arrow`, and `pyo3` reqs.
3. Set `polars` and `polars-arrow` to the **exact** version the `polars` caret targets; set `pyo3` within the `pyo3` caret.
4. `cargo build` (or `just build`). Confirm the resolved versions in `bartons/Cargo.lock` match step 2 — that is the source of truth for what got compiled in.

The [`check-bindings`](../.claude/commands/check-bindings.md) skill audits these pins for mutual consistency; [`upgrade-bindings`](../.claude/commands/upgrade-bindings.md) derives a newer set from upstream and rebuilds after approval.

## Scope: this is the Cargo side only

This doc covers the compile-time crate pins. The **Python `polars` cap** in [`pyproject.toml`](../pyproject.toml) is a *separate* constraint — it governs which Python `polars` the built `.so` runs against at the FFI guard, not what compiles. The crate ↔ Python-package correspondence is tabulated in [`polars-ffi-version-table.md`](polars-ffi-version-table.md); the rationale for the exact `pyproject` cap is currently under review.

## Related

- [`polars-ffi-version-guard.md`](polars-ffi-version-guard.md) — the runtime FFI handshake the compiled `.so` participates in.
- [`polars-ffi-version-table.md`](polars-ffi-version-table.md) — FFI ↔ crate ↔ Python-package version data.
