# Polars FFI Version Table

Reference data: the **plugin FFI version** (the `(MAJOR, MINOR)` handshake number a `pyo3-polars` plugin and the host polars negotiate at load time) mapped against the **Rust `polars` crate version** and the **Python `polars` package version**.

This doc records *what the numbers are* and *how to obtain them*. The guard logic that consumes these numbers is documented separately in [`polars-ffi-version-guard.md`](polars-ffi-version-guard.md).

Data verified June 2026 by reading source out of every published `polars-ffi` crate (crates.io) and the relevant Python `polars` / `polars-runtime-32` sdists (PyPI). Reproducible — see [Method](#method).

## FFI version history (Rust crate axis)

The FFI version is two `u16` constants, `MAJOR`/`MINOR`, in the `polars-ffi` crate `src/lib.rs`. `polars-ffi` is versioned in lockstep with the main Rust `polars` crate, so this column doubles as the polars-crate version.

| Rust `polars`(-ffi) crate | FFI version | Notes |
|---|---|---|
| ≤ `0.34.2` | *(none)* | No constants, no `get_version` — no handshake at all. |
| `0.35.0` – `0.36.2` | `(0, 0)` | Versioned handshake introduced. |
| `0.37.0` – `0.54.4` (latest) | `(0, 1)` | Bumped once; unchanged since. |

## Python `polars` → Rust crate → FFI version

### FFI `(0, 0)` era

| Python `polars` | Rust crate | FFI |
|---|---|---|
| `0.20.0` – `0.20.5` | `0.35.4` – `0.36.x` | `(0, 0)` |

### FFI `(0, 1)` era

| Python `polars` | Rust crate | FFI |
|---|---|---|
| `0.20.6` | `0.37.0` | `(0, 1)` ← first ever `(0,1)` |
| `1.0.0` | `0.41.2` | `(0, 1)` |
| `1.1.0` – `1.5.0` | `0.41.3` | `(0, 1)` |
| `1.6.0` | `0.42.0` | `(0, 1)` |
| `1.7.0` | `0.43.0` | `(0, 1)` |
| `1.7.1` – `1.12.0` | `0.43.1` | `(0, 1)` |
| `1.13.0` – `1.17.0` | `0.44.2` | `(0, 1)` |
| `1.17.1` – `1.21.0` | `0.45.1` | `(0, 1)` |
| `1.22.0` – `1.29.0` | `0.46.0` | `(0, 1)` |
| `1.30.0` – `1.31.0` | `0.48.1` | `(0, 1)` |
| `1.32.0` | `0.49.1` | `(0, 1)` |
| `1.32.1` – `1.33.1` | `0.50.0` | `(0, 1)` |
| `1.34.0` – `1.35.2` | `0.51.0` | `(0, 1)` |
| `1.36.0` – `1.38.1` | `0.52.0` | `(0, 1)` |
| `1.39.0` – `1.41.2` | `0.53.0` | `(0, 1)` |
| `1.42.0` – `1.42.1` | `0.54.4` | `(0, 1)` |

Notes:

- The `1.x` rows pick up from `1.0.0`; the `(0,1)` era actually starts at Python `0.20.6`. Intermediate `0.20.x` releases are omitted as out of scope.
- `1.25.1` published no sdist; bracketed by `1.25.0`/`1.25.2` (both Rust `0.46.0`).
- Some Rust crate versions were never shipped in a stable Python release (e.g. `0.47.x`, `0.54.1`–`0.54.3`); Python minors skip across them.
- Rust source moved out of the `polars` sdist into a separate `polars-runtime-32` / `polars-runtime-64` package at Python `1.34.0`; rows ≥ `1.34.0` were read from `polars-runtime-32`.

## pyo3-polars axis

The plugin side exports the FFI version via `pyo3-polars`. For reference, the export symbol and the polars crate each `pyo3-polars` version pins:

| pyo3-polars | exports `_polars_plugin_get_version` | polars crate `req` |
|---|---|---|
| ≤ `0.8.0` | no | `^0.34` (and earlier) |
| `0.9.0` | yes (first) | `^0.35` |
| `0.27.0` | yes | `^0.54.4` |

## Method

Reproducible without GitHub tokens or a build:

1. `GET https://crates.io/api/v1/crates/polars-ffi/versions` → all crate versions. For each, download `https://static.crates.io/crates/polars-ffi/polars-ffi-<v>.crate` and read `pub const MAJOR/MINOR: u16` from `src/lib.rs`.
2. `GET https://pypi.org/pypi/polars/json` and `.../polars-runtime-32/json` → Python release list + sdist URLs.
3. For each Python release, download the sdist and read `[workspace.package] version` from the root `Cargo.toml` (→ Rust crate version); cross-check `crates/polars-ffi/src/lib.rs` for the FFI constants. Use `polars-runtime-32` for ≥ `1.34.0`.
4. pyo3-polars side: download `https://static.crates.io/crates/pyo3-polars/pyo3-polars-<v>.crate`, grep `src/` for `_polars_plugin_get_version`; read the polars `req` from `https://crates.io/api/v1/crates/pyo3-polars/<v>/dependencies`.

## Related

- [`polars-ffi-version-guard.md`](polars-ffi-version-guard.md) — what the guard does with these numbers, where the code lives, and when it was introduced.
- [`polars-runtime-libraries.md`](polars-runtime-libraries.md) — the `polars-runtime-32`/`-64`/`-compat` engine split and how it relates (orthogonally) to the FFI version.
