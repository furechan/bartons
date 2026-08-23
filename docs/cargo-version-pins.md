# Cargo.toml Version Pins

How to choose and set the Rust crate versions in [`bartons/Cargo.toml`](../bartons/Cargo.toml) for the plugin. This is the **compile-time** side: these pins fully determine the `.so` that gets built, independent of the polars-py installed in the venv (see [`polars-ffi-version-guard.md`](polars-ffi-version-guard.md) for the separate runtime concern).

Facts below are read from `bartons/Cargo.toml`, `bartons/Cargo.lock`, and the crates.io dependencies API.

## Naming: `polars-rs` vs `polars-py`

Two different artifacts are both called "polars", on unrelated version schemes —
saying just "polars 0.54" or "polars 1.42" is ambiguous about which. These docs
and the binding skills use:

| term | what | version scheme | declared in | example |
|---|---|---|---|---|
| **`polars-rs`** | the Rust crate, statically linked into the `.so` | `0.5x` | `bartons/Cargo.toml` | `0.55.2` |
| **`polars-py`** | the Python package, resolved into the venv | `1.4x` | `[project].dependencies` | `1.43.2` |

Borrowed from upstream: the `pola-rs/polars` monorepo dual-tags every release
`rs-0.54.4` and `py-1.42.1`, and mapping between those tags is exactly how the
correspondence in [`polars-ffi-version-table.md`](polars-ffi-version-table.md) is
derived.

Two further distinctions worth keeping straight, since they cut across the above:
**compile-time** (`Cargo.toml`, fixes what is in the `.so`) versus **install-time**
(`pyproject.toml`, gates what the venv may hold); and the **request** (a version
range) versus the **resolved** (`Cargo.lock`, or the package actually installed).

### Words for the version settings

One noun per file, so the term says where the setting lives:

| term | file | means |
|---|---|---|
| **pins** | `bartons/Cargo.toml` | the four crate versions compiled into the `.so` |
| **range** | `pyproject.toml` | `polars>=1.28,<1.44` — the polars-py versions allowed to install |
| **matrix** | `noxfile.py` | `COMPAT_VERSIONS` — the discrete versions actually executed |

The range has a **floor** (`>=1.28`) and a **ceiling** (`<1.44`), and they are not
the same kind of limit:

- The **floor is hard**. Below it the eager `bartons.kernels.<name>` functions
  genuinely break — `PySeries._export` does not exist. A functional requirement.
- The **ceiling is tested, not hard**. Nothing is known to fail above it; it marks
  how far the matrix has run. **The matrix sets the ceiling** — to raise one, run
  the other. `uv run inv raise-ceiling` does both in one step.

Avoid **cap** (it names only an upper limit, so it misdescribes the two-sided
range) and **constraint** (pip and uv use it for *constraints files*, `-c`, a
different mechanism). Note `window` is spoken for too, in the SMA/WMA rolling
sense.

## What is pinned and why

Four interlocking crates:

| Crate | Role |
|---|---|
| `pyo3-polars` | The plugin framework: generates the FFI entry points and exports the version handshake. **The dial** — see below. |
| `polars` (**polars-rs**) | The Rust polars crate, statically linked into the `.so`. Provides `Series`/`ChunkedArray` and the kernels. |
| `polars-arrow` | Polars' Arrow layer; must move in lockstep with `polars`. |
| `pyo3` | The Python ⇆ Rust binding layer (`#[pyfunction]`, the `extension-module`/`abi3` features). |

## The single dial: pick `pyo3-polars` first

`pyo3-polars` caret-pins **both** the polars-rs family **and** the pyo3 range. So you do not choose `polars` or `pyo3` independently — you choose `pyo3-polars`, then read off what it requires and set the rest to satisfy it.

Read the requirements straight from crates.io (structured, no build needed):

```
GET https://crates.io/api/v1/crates/pyo3-polars/<ver>/dependencies
```

For `pyo3-polars 0.28.0` this returns:

| dependency | req |
|---|---|
| `polars` | `^0.55.1` |
| `polars-arrow` | `^0.55.1` |
| `pyo3` | `^0.29` |

## The interlock rules

1. **`polars` and `polars-arrow` must match the version `pyo3-polars` targets, and each other.** Pin both to the exact version `pyo3-polars` carets to (here `0.55.1`). They share struct layouts; a mismatch between them, or against the version compiled into `pyo3-polars`, is an ABI break.
2. **`pyo3` must satisfy `pyo3-polars`'s `pyo3` req — pin to that caret, not to "latest".** When upgrading, the newest published pyo3 is often *ahead* of what `pyo3-polars` accepts (pyo3 `0.29` existed while `pyo3-polars 0.27` wanted `^0.28`). Pin to the req.
3. **`extension-module` ⇒ exactly one `pyo3` in the build tree.** A direct `pyo3` pin that disagrees with `pyo3-polars`'s pulls in *two* pyo3 versions; pyo3's build script detects this and the build **fails hard** (it does not silently pick one). This is why rule 2 matters.

## Current pins (verified snapshot)

`bartons/Cargo.toml`:

```toml
[features]
default = ["extension-module"]
extension-module = ["pyo3/extension-module"]

pyo3 = { version = "0.29", features = ["abi3-py311"] }
pyo3-polars = { version = "0.28", features = ["derive", "dtype-struct", "dtype-decimal", "dtype-array"] }
polars = { version = "0.55.1", features = ["dtype-struct"] }
polars-arrow = { version = "0.55.1", default-features = false }
```

Resolved in `bartons/Cargo.lock`:

| crate | resolved |
|---|---|
| `pyo3-polars` | `0.28.0` |
| `polars` | `0.55.2` |
| `polars-arrow` | `0.55.2` |
| `pyo3` | `0.29.2` |

These exactly satisfy `pyo3-polars 0.28.0`'s requirements above. Note the pin is
the caret *target* (`0.55.1`) while cargo resolves to the newest compatible
(`0.55.2`) — the request versus the resolved, as above.

## `abi3` — what it does and does not decouple

The `abi3-py311` feature builds against Python's stable ABI, so a single compiled `.so` works across Python `3.11+` without recompiling per Python minor. That decouples the plugin from the **Python interpreter** version — but **not** from polars-rs. The polars ABI is unaffected by `abi3`; it remains fixed by the polars-rs pin.

**Why `py311` and not a lower floor.** It was `abi3-py38` until 2026-08-14. The
lower floor bought nothing: `requires-python` is `>=3.11`, so installers never
resolve the package onto 3.8–3.10, and the nox matrix only ever runs 3.11 — a
`cp38-abi3` tag was advertising three minors that were neither reachable nor
tested. Raising it also costs nothing measurable, because **`abi3` cannot touch
the compute path**: `#[polars_expr]` compiles to a `#[no_mangle] extern "C"`
symbol that polars calls directly over the Arrow C interface, never through
pyo3, and the eager `kernels.<name>` path crosses pyo3 once per call to marshal a
Series rather than once per element. The floor governs module import and that
one marshalling step, nothing hot. What it does buy is headroom: pyo3 gates ~98
call sites on `Py_3_10` and ~33 on `Py_3_11`, so those APIs are available if a
future feature wants them.

## `bigidx` — for the runtime-64 engine

The default pins above produce a plugin for the default `polars-runtime-32` engine (`IdxSize = u32`). To target the `polars[rt64]` engine (`polars-runtime-64`, `IdxSize = u64`), add the `bigidx` feature to the `polars` dependency:

```toml
polars = { version = "0.55.1", features = ["dtype-struct", "bigidx"] }
```

`IdxSize` is a compile-time type, so one `.so` cannot serve both engines — a `bigidx` build is a separate artifact. For the default install this is unnecessary; see [`polars-runtime-libraries.md`](polars-runtime-libraries.md) for what the runtime variants are and when a `bigidx` build is actually needed.

## Procedure to set or bump the pins

**Start from a clean, synced working tree.** A bump edits `Cargo.toml`,
`Cargo.lock`, often several kernel files (a crate-minor jump breaks Rust API), and
sometimes `pyproject.toml`; the fallback at every step is to revert, and
`git checkout -- .` only backs out the upgrade if the upgrade is the only thing in
the tree.

1. Choose the `pyo3-polars` version (e.g. latest, or whichever you target).
2. `GET https://crates.io/api/v1/crates/pyo3-polars/<ver>/dependencies` → note the `polars`, `polars-arrow`, and `pyo3` reqs.
3. Set `polars` and `polars-arrow` to the **exact** version the `polars` caret targets; set `pyo3` within the `pyo3` caret.
4. `cargo build` (or `uv run inv make`). Confirm the resolved versions in `bartons/Cargo.lock` match step 2 — that is the source of truth for what got compiled in.
5. `uv run inv test` — **against the polars-py already installed**. Do not touch the
   `pyproject.toml` range yet: changing the pins moves the binary and changing the
   range moves the engine, so doing both at once means a failure cannot tell you
   which side caused it. Hold the engine fixed until the new binary is known good.

Only then consider whether the polars-py range should move (see *Scope* below).
The FFI handshake is a separate concern and is **not** part of a routine bump: it
has been `(0, 1)` since polars-rs `0.37.0`. Check it only if the plugin fails to
*load* rather than to compile, or if the jump crosses a boundary in
[`polars-ffi-version-table.md`](polars-ffi-version-table.md) — and if it really has
changed, stop and treat it as a compatibility event, not a version bump.

The [`check-bindings`](../.claude/commands/check-bindings.md) skill audits these pins for mutual consistency; [`upgrade-bindings`](../.claude/commands/upgrade-bindings.md) derives a newer set from upstream and rebuilds after approval, in the same staged order.

## Scope: this is the Cargo side only

This doc covers the compile-time crate pins. The **polars-py range** in [`pyproject.toml`](../pyproject.toml) is a *separate* setting — it governs which polars-py the built `.so` runs against at the FFI guard, not what compiles. The polars-rs ↔ polars-py correspondence is tabulated in [`polars-ffi-version-table.md`](polars-ffi-version-table.md). The current range is `polars>=1.28,<1.44`: the floor is a hard requirement for the eager `bartons.kernels.<name>` pyfunctions (they need `PySeries._export`, first exposed in polars-py 1.28 — see [`test-compat-helpers.md`](test-compat-helpers.md)), and the ceiling is the current test boundary, **not** a hard ABI limit — raise it with `uv run inv raise-ceiling`, which tests the newest polars-py and only moves the number if it passes. The expression path alone works down to polars-py 1.0, but the package floors at 1.28 so its whole public API is usable.

## Related

- [`polars-ffi-version-guard.md`](polars-ffi-version-guard.md) — the runtime FFI handshake the compiled `.so` participates in.
- [`polars-ffi-version-table.md`](polars-ffi-version-table.md) — FFI ↔ crate ↔ Python-package version data.
