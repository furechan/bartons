# pyo3-polars Version Lockstep

How a native polars plugin (Rust, built with `pyo3-polars`) is coupled to a polars version window, why that coupling exists, and how to derive the correct `polars >=x,<y` cap from **machine-readable** sources instead of guessing. Applies to any polars plugin (`polars_talib`, custom Rust expression plugins), and frames the trade against the pure-Python `map_batches` alternative used by barcalc.

## TL;DR

- A native plugin is a **compiled `.so`** that the host polars **Rust engine** calls over a C FFI. It carries its own statically-linked copy of polars-core, so there are effectively **two polars runtimes** in one process. The **data** crossing is stable (Arrow C Data Interface); the **plugin ABI** (FFI structs + kwargs blob + version handshake, defined by `pyo3-polars`) is **not** frozen, so it's coupled to a polars version window.
- The Cargo polars-crate pin sets the **de facto** window (what *works*). It is **invisible to pip/uv** — you must mirror it as an **enforced** `polars >=x,<y` cap in your own `pyproject.toml`. Cargo decides what works; pyproject decides what installs.
- `map_batches` (barcalc) sidesteps all of it: a **Python callback** runs inside the host polars, gets the host's own `Series` object — no second runtime, no FFI, no version window, no cap, no rebuild. Cost is the GIL/per-callback boundary (slow under `.over()` with many groups).

## Why the coupling exists

`register_plugin_function` is *not* a Python callback. Registration is kicked off from Python, but at execution time the host polars Rust engine `dlopen`s the plugin `.so`, finds the entrypoint symbol, and calls it directly. The plugin reconstructs the incoming Series using its **own compiled-in polars-core**. The contract between host and plugin — entrypoint signature, the kwargs serialization format, and a load-time compatibility check — is set by `pyo3-polars`, which pins a specific polars Rust crate. Minor polars releases can move that contract; when they do, the plugin fails to **load/register** (handshake error or panic), not degrade gracefully.

Contrast `map_batches`: polars calls back into the Python interpreter with a real host `Series`. Same runtime, no FFI, no compiled coupling — works on whatever polars the user has.

## Version-space gotcha

The **Rust `polars` crate is on `0.5x`** while the **Python `polars` package is on `1.4x`**. Different numbering. A Cargo pin like `polars = "0.54.4"` does not literally name any `1.x` bound — you must translate crate → Python-package version via the polars monorepo. Also: PEP 440 `<= 1.41` excludes `1.41.1/.2`; always cap with `< next_minor` (or `~=1.41.0` / `==1.41.*`), never `<= this_minor`.

## Deriving the window from machine-readable sources

Since 2025-07-28 `pyo3-polars` was **archived and vendored into the polars monorepo** (`pola-rs/polars/pyo3-polars`), so pyo3-polars, the Rust crate, and the Python package now release **in lockstep** from one repo. Two structured lookups give the full mapping:

**Link 1 — pyo3-polars → polars Rust crate** (crates.io JSON, structured):
`GET https://crates.io/api/v1/crates/pyo3-polars/<ver>/dependencies` → the `polars` crate `req` string.

**Link 2 — polars-Python → polars Rust crate** (polars monorepo dual-tags `py-*` and `rs-*`; `[workspace.package] version` at a `py-` tag *is* the Rust crate version):
`gh api -H "Accept: application/vnd.github.raw" "repos/pola-rs/polars/contents/Cargo.toml?ref=py-<X>"` → workspace version.

**Compose** → the polars-Python versions your plugin (built on pyo3-polars `<ver>`) is ABI-compatible with.

### Verified snapshot (June 2026)

| pyo3-polars | depends on polars crate |
|---|---|
| 0.27.0 (2026-06-10) | `^0.54.4` (= `>=0.54.4,<0.55`) |

| polars-Python tag | Rust crate (workspace version) |
|---|---|
| py-1.42.0 | 0.54.4 |
| py-1.41.0 | 0.53.0 |
| py-1.40.1 | 0.53.0 |

Key consequence: **py-1.40 and py-1.41 are both rs 0.53.0**, so a plugin compiled against polars crate `0.53` is compatible with *two* Python minors → window `polars >=1.40,<1.42`. The window is naturally a **range**, and it is *derived*, not guessed. A plugin on pyo3-polars 0.27.0 (crate `^0.54.4`) → polars-Python `1.42.x`.

## pyo3-polars is the single dial (and it also pins pyo3)

pyo3-polars releases **in lockstep** with the polars crate — since the 2025-07-28 vendoring into the monorepo, each pyo3-polars minor tracks the next polars crate minor 1:1:

| pyo3-polars | polars crate | pyo3 |
|---|---|---|
| 0.20 | `^0.46.0` | `^0.23` |
| 0.26 | `^0.53.0` | `^0.27` |
| 0.27 | `^0.54.4` | `^0.28` |

So **pick pyo3-polars first** — it names *both* the polars crate (→ the polars-Python window) *and* the pyo3 range. This is a second, narrower lockstep axis that's easy to miss: you cannot independently take the latest pyo3.

- pyo3-polars caret-pins pyo3 (e.g. 0.27 → `pyo3 ^0.28` = `>=0.28,<0.29`). At upgrade time, latest pyo3 may be **ahead** of that cap (it was `0.29` when 0.27 wanted `0.28`) — pin pyo3 to satisfy pyo3-polars's `req`, not to latest.
- The `extension-module` feature requires **exactly one pyo3 in the build tree**. A direct pyo3 pin that disagrees with pyo3-polars's pulls in two pyo3 copies and the build **fails hard** (pyo3 detects the conflict) — it does not silently pick one.

Read pyo3-polars's pyo3 `req` from the same crates.io `/dependencies` JSON as the polars `req`.

## Two-way spec: which bound is knowable

- **Lower (`>=`)**: the first `py-` minor whose workspace version is your crate. **Fully known now** from git tags.
- **Upper (`<`)**: the first `py-` minor that bumps past your crate's caret range. **Known up to the latest released `py-` tag** (e.g. crate 0.53 → py-1.42 moved to 0.54 → `<1.42`). The genuine *future* edge is irreducible — no table or agent can know whether an unreleased polars keeps the ABI. Reduce it to a **deterministic git-tag re-query** when a new polars minor drops: read the new `py-` tag's workspace version; if still your crate, widen the cap; if bumped, that's your `<` boundary.

This is the only residual "knowledge" cost — everything else is structured lookups. No README-prose parsing, no LLM judgment required.

## The resolver model (why the cap is the solution, not a burden)

Ship the cap as **static metadata** (`pyproject.toml` `dependencies`, visible in sdist PKG-INFO without building). Then:

- uv resolves **before** building, so an incompatible polars is simply *unsolvable* — never installed, never a runtime crash.
- A chain of releases each declaring its window (`0.1 → polars<1.42`, `0.2 → polars<1.45`) lets the resolver **co-upgrade plugin + polars in lockstep**: ask for a newer polars and uv bumps the plugin to one whose window admits it.
- If no wider plugin is published yet, uv does the **safe** thing — holds polars back (graceful block + resolver message), not a crash. The publish cadence remains, but it's reactive and can be done ahead of time, not last-minute.
- The resolver enforces what you **declare**, not what's **true**. A wrong cap installs a broken pair silently — so the declared window's accuracy should be backed by a build+import+query **test matrix** at release time (the derivation gives the *prior*; the matrix gives ground truth).

## sdist vs wheel

- **sdist does not remove the cap.** The build compiles against *your* pinned crate (Cargo.lock in the sdist) on the user's machine — **not** against their installed polars-Python. So the window is still fixed by your crate; you still declare the cap. sdist also goes **stale**: compiled once at install, a later `pip install -U polars` doesn't retrigger the build (no recompile-on-dep-change hook) — unless the resolver co-upgrades the plugin too (it will, given the cap chain above).
- **sdist taxes every install**: each user needs a Rust toolchain + C compiler, and for `polars_talib` specifically the **TA-Lib C library present and discoverable** for the link to succeed — i.e. the exact `undefined symbol` linking fragility becomes a per-user problem instead of solved once in CI.
- **The ecosystem answer for broad support is a cibuildwheel matrix** (platform × Python × polars-window prebuilt wheels), not per-user compilation. sdist-only is fine for experiment/private use where you control the build environment and can measure build time.

## Automating it (tasks.py sketch)

At plugin build/release time, derive the cap from the pinned crate instead of hand-writing it:

1. Read the resolved polars crate version from `Cargo.lock` (not the `Cargo.toml` range).
2. Read pyo3-polars's `polars` `req` from crates.io (or the vendored manifest) to confirm the crate family.
3. Walk `pola-rs/polars` `py-*` tags, reading each `[workspace.package] version`, to find the contiguous run of Python minors on your crate → `>=lower`.
4. Set `<` to the first Python minor that bumped past your crate (or `< next_minor` conservatively, re-queried as tags land).
5. Write `polars >=lower,<upper` into `pyproject.toml`; back it with a CI import+query matrix across that range.

## Related

- [`polars-plugin-abi-compatibility.md`](polars-plugin-abi-compatibility.md) — companion note on the ABI coupling itself, the `PYPOLARS_VERSION` runtime check, and the editable-install rebuild workflow for internal plugins.
- `~/Projects/python-dev/docs/barcalc/native-migration.md` — barcalc's `map_batches` + numba choice and the GIL/`.over()` cost it pays to avoid all of the above.
- `polars_talib` linking fragility: its prebuilt wheel leaves TA-Lib C symbols undefined (no `DT_NEEDED`), requiring an `RTLD_GLOBAL` preload of the bundled `libta-lib`; same class as upstream issues "undefined symbol `TA_CDL3BLACKCROWS_Lookback`" (Linux) and "`_TA_ACOS` not found in flat namespace" (macOS).
- `expression-struct-pattern.md`, `expression-tuple-pattern.md` (in `~/Projects/dev-notes/patterns/`) — polars expression design notes.
