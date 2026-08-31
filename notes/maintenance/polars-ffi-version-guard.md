# Polars Plugin FFI Version Guard

What the runtime guard between a `pyo3-polars` plugin and the host polars actually does, where its code lives, and when it was introduced. The version *numbers* it operates on are tabulated in [`polars-ffi-version-table.md`](../../docs/polars-ffi-version-table.md).

Everything below is read from source: `pyo3-polars` / `polars-ffi` crates (crates.io) and the `pola-rs/polars` monorepo (the host check is compiled into polars-py's native binary, not shipped as Python).

## What the guard is

A native polars plugin is a compiled `.so` that the host polars Rust engine `dlopen`s and calls over a C FFI. The guard is a single integer handshake: the plugin exports its **FFI version** `(MAJOR, MINOR)`; the host reads it and dispatches on it, refusing versions it does not recognise. It is a check on the **FFI/ABI generation**, not on the polars package or crate version string.

## Plugin side — where the version comes from

Three crates contribute to the exported `.so`:

1. **`polars-ffi`** defines the version constants — `crates/polars-ffi/src/lib.rs`:
   ```rust
   pub const MAJOR: u16 = 0;
   pub const MINOR: u16 = 1;
   pub const fn get_version() -> (u16, u16) { (MAJOR, MINOR) }
   ```
2. **`pyo3-polars`** exports them as a C symbol — `pyo3-polars/src/derive.rs`:
   ```rust
   #[no_mangle]
   pub unsafe extern "C" fn _polars_plugin_get_version() -> u32 {
       // (one-time start_up_init on first call)
       let (major, minor) = polars_ffi::get_version();
       ((major as u32) << 16) + minor as u32   // packed: major<<16 | minor
   }
   ```
3. **`pyo3-polars-derive`** generates the per-expression entry points the host calls once the version check passes — `_polars_plugin_<fn>` (compute) and `_polars_plugin_field_<fn>` (output schema), plus `_polars_plugin_get_last_error_message`.

## Host side — where the check runs

Compiled into polars-py; source in the monorepo at:

`crates/polars-plan/src/plans/aexpr/function_expr/plugin.rs`

- **`get_lib(lib)`** — on first use, `dlopen`s the `.so`, resolves `_polars_plugin_get_version`, calls it, unpacks `major = version >> 16`, `minor = version as u16`, and caches `(library, major, minor)` in a static `LOADED` map. The symbol lookup is `.unwrap()` — a plugin that does not export it (i.e. built before the handshake existed) panics here rather than producing a clean error.
- **`call_plugin(...)`** (the compute path) gates on the cached version:
  ```rust
  if major == 0 {
      match minor { /* dispatch */ }
  } else {
      polars_bail!(ComputeError: "this polars engine doesn't support plugin version: {}", major)
  }
  ```
- **`plugin_field(...)`** (the output-schema path) repeats the same `if major == 0 { match minor { 0 => …, 1 => …, _ => bail } }` dispatch.

### The dispatch logic

- **`major`**: exact. Only `major == 0` is handled; anything else bails.
- **`minor`**: a `match` over the minors the host knows (currently `0` and `1`), each calling the plugin entry point with the signature appropriate to that minor (minor `1` adds the kwargs pointer/length). A minor newer than the host knows hits `_ => bail`. Older known minors still dispatch — so the host is backward-compatible with older plugins within `major 0`.

### The one layout guard

Beyond the version dispatch, there is exactly one struct-layout check, and it lives only in the `minor == 0` arm of `plugin_field`:

```rust
let views = fields.iter().any(|f| f.dtype.contains_views());
polars_ensure!(!views, ComputeError:
    "cannot call plugin\n\nThis Polars' version has a different 'binary/string' layout. \
     Please compile with latest 'pyo3-polars'");
```

It catches one specific divergence (the binary/string "views" layout) and is dead on the current `minor == 1` path. There is no other runtime validation of struct layouts.

### What the guard does and does not check

- **Checks**: the FFI `(major, minor)` handshake only.
- **Does not check**: the polars-py version, the polars-rs version, or (on the `minor == 1` path) any struct layout. The handshake passing means only that the FFI generation is recognised, not that the two sides' `Series`/`SeriesExport`/Arrow layouts match.

## When it was introduced

| Component | First version with the guard | Predecessor |
|---|---|---|
| `polars-ffi` `MAJOR`/`MINOR` + `get_version` | `0.35.0` — value `(0, 0)` | ≤ `0.34.2`: no constants at all |
| FFI version bumped to `(0, 1)` | `0.37.0` | `0.35.0`–`0.36.2` were `(0, 0)` |
| `pyo3-polars` `_polars_plugin_get_version` export | **`0.9.0`** | `0.8.0` and earlier: no export |

The plugin-side export and the FFI constants landed together at the **polars `0.35` / pyo3-polars `0.9.0`** boundary (pyo3-polars `0.8.0 → polars ^0.34`, `0.9.0 → polars ^0.35`). Plugins built against pyo3-polars `≤ 0.8.0` export no version symbol, so a modern host's `.unwrap()` on the symbol lookup cannot load them.

(This corrects an earlier note of ours — since removed — which framed the runtime check as a strict `PYPOLARS_VERSION` string match introduced "in a later version of pyo3-polars (e.g. 0.10)". The actual check is the `(major, minor)` FFI handshake, and the export first appears in `0.9.0`.)

## Source references (local evidence)

Versions present in this machine's caches when the above was verified:

- Plugin export: `pyo3-polars-0.27.0/src/derive.rs` (`_polars_plugin_get_version`).
- FFI constants: `polars-ffi-0.54.4/src/lib.rs` (`MAJOR`/`MINOR`/`get_version`).
- Derive entry points: `pyo3-polars-derive-0.21.0/src/lib.rs` (`_polars_plugin_<fn>`, `_polars_plugin_field_<fn>`).
- Host check: `polars-runtime-32 1.41.2` → `crates/polars-plan/src/plans/aexpr/function_expr/plugin.rs` (`get_lib`, `call_plugin`, `plugin_field`).

## Related

- [`cargo-version-pins.md`](cargo-version-pins.md) — the compile-time side: how the `pyo3-polars` / `polars` / `pyo3` Cargo pins that produce the `.so` are chosen.
- [`polars-runtime-libraries.md`](polars-runtime-libraries.md) — the `polars-runtime-32`/`-64`/`-compat` engine split; the FFI version is identical across them.
- [`polars-ffi-version-table.md`](../../docs/polars-ffi-version-table.md) — the FFI version values across crate and package versions, and the method to regenerate them.
