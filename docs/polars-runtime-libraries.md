# Polars Runtime Libraries (the `polars-runtime-*` split)

Summary of what the `polars-runtime-32` / `-64` / `-compat` packages are, how the `polars` package selects one, and how that bears on a compiled plugin. Verified June 2026 from PyPI metadata, the `polars` wrapper source (`_plr.py`), and the runtime sdists.

## The wrapper / engine split

Since Python `polars 1.34.0`, the `polars` package is a **pure-Python wrapper**; the compiled Rust engine lives in a **separate package**. The wrapper declares (from `polars 1.42.1` metadata):

```
polars-runtime-32==1.42.1                            # unconditional → the default engine
polars-runtime-64==1.42.1 ; extra == "rt64"          # opt-in:  pip install polars[rt64]
polars-runtime-compat==1.42.1 ; extra == "rtcompat"  # opt-in:  pip install polars[rtcompat]
```

So a plain `pip install polars` installs the wrapper **+ `polars-runtime-32` only**. The other two engines are pulled in solely by their extras. A normal install never contains more than one engine; reading the Rust/FFI source "from `polars-runtime-32`" is reading the engine that `polars` actually runs.

## What `32` / `64` means — index width, not CPU

`32`/`64` is polars' internal **row-index integer width** (`IdxSize`), toggled by the `bigidx` Cargo feature (`rt64 = ["polars/bigidx"]`):

- **`-32`** → `IdxSize = u32`: addresses up to ~4.29 billion (2³²) rows. The default.
- **`-64`** → `IdxSize = u64` (`bigidx`): removes that ceiling; larger index columns.

It is **not** CPU architecture. CPU/OS is carried by the **wheel platform tag** — `polars-runtime-32` ships wheels for `x86_64`, `aarch64`, `arm64`, and Windows, all 64-bit CPUs. The `-32` is constant across them.

The third engine, **`-compat`**, is a CPU-portability build: each engine carries `BUILD_FEATURE_FLAGS` and the wrapper calls `check_cpu_flags(...)` at import, so `-compat` exists for CPUs lacking the newer SIMD the default build assumes. (Yet another axis, again unrelated to the FFI version.)

## How the engine is selected — additive extra, but a switch in effect

The wrapper picks its backend **at import time**, in `_plr.py`, by trying engines in a fixed preference order and using the first one installed:

```python
default_prefer = [rt_compat, rt_64, rt_32]   # compat > 64 > 32
for pkg in preference:
    try:
        pkg()        # imports _polars_runtime_<x>; ImportError if not installed
        ...          # then require engine __version__ == wrapper PKG_VERSION
```

- `polars` alone → only `-32` present → falls through to `rt_32`.
- `polars[rt64]` → `-32` **and** `-64` installed (the `-32` dep never goes away), but `rt_64` is reached first, so `-64` is used and `-32` is ignored.

Overrides: `POLARS_FORCE_PKG=64|32|compat` forces one; `POLARS_PREFER_PKG=...` moves one to the front. So although `rt64`/`rtcompat` are delivered as pip *extras* (additive), the import-time preference makes them function as a **backend switch**.

## Relationship to the FFI version

**Orthogonal.** The plugin FFI version (`polars-ffi` `MAJOR`/`MINOR`) is **identical `(0,1)` in both `-32` and `-64`** (verified by reading `crates/polars-ffi/src/lib.rs` from both sdists). The version guard does not distinguish runtime variants. See [`polars-ffi-version-guard.md`](polars-ffi-version-guard.md).

## What this means for a compiled plugin

A plugin links its **own** static copy of polars-rs; it does not link any `polars-runtime-*` library (see [`cargo-version-pins.md`](cargo-version-pins.md)). Compatibility with a given runtime is therefore a *source-level* match, invisible to the linker and only coarsely checked at runtime:

- **runtime-32** — a default-built plugin (no `bigidx`) matches: same crate version, same `IdxSize = u32`.
- **runtime-64** — `bigidx` flips `IdxSize` `u32→u64`. The FFI boundary structs (`SeriesExport`, `CallerContext`) contain **no `IdxSize`** (verified — they are Arrow-C pointers), so the boundary itself is bigidx-agnostic and a default plugin still loads and exchanges Arrow data safely. The only divergence is **index-typed columns** (`IDX_DTYPE`: `UInt32` vs `UInt64`). A plugin that never produces/consumes index columns (e.g. bartons' numeric `Float64` indicators) works on runtime-64 in practice; one that does would mismatch the engine's `IDX_DTYPE`.
- To build a **robust** runtime-64 plugin, compile with the `bigidx` feature so the plugin's `IdxSize` matches. `IdxSize` is a compile-time type, so one `.so` cannot serve both runtimes — ship two artifacts and match the installed runtime, mirroring polars' own split. See [`cargo-version-pins.md`](cargo-version-pins.md).

## Method / evidence

- Engine deps & extras: `GET https://pypi.org/pypi/polars/<ver>/json` → `info.requires_dist`.
- `32`/`64` = `bigidx`: `rt64 = ["polars/bigidx"]` in the runtime sdist Cargo manifests.
- CPU-arch independence: wheel platform tags in `GET https://pypi.org/pypi/polars-runtime-32/<ver>/json`.
- Selection logic: `src/polars/_plr.py` in the `polars` sdist.
- FFI version parity: `crates/polars-ffi/src/lib.rs` in both `polars-runtime-32` and `-64` sdists.

## Related

- [`cargo-version-pins.md`](cargo-version-pins.md) — compile-time crate pins, including the `bigidx` option for runtime-64.
- [`polars-ffi-version-guard.md`](polars-ffi-version-guard.md) — the runtime FFI handshake (identical across runtime variants).
- [`polars-ffi-version-table.md`](polars-ffi-version-table.md) — FFI ↔ crate ↔ Python-package version data.
