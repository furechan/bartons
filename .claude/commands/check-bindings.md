---
description: Review the pyo3-polars version lock-in across the Rust and Python sides — show every pin, where it lives, and whether they are mutually consistent.
allowed-tools: Read, Bash, Grep, Glob
---

You are auditing the **version lock-in** that keeps this native polars plugin (Rust, built with `pyo3-polars`) ABI-compatible with the polars-Python it runs against. This is a **read-only review** — do not edit any files. Gather the facts, lay them out, flag problems, then discuss next steps with the user.

Background on *why* this coupling exists and how the version window is derived: read [docs/pyo3-polars-version-lockstep.md](../../docs/pyo3-polars-version-lockstep.md) and [docs/polars-plugin-abi-compatibility.md](../../docs/polars-plugin-abi-compatibility.md) first.

## Where the settings live — gather all of these

**Rust side — [bartons/Cargo.toml](../../bartons/Cargo.toml) `[dependencies]`:**
- `pyo3` — version + features (`extension-module`, `abi3-py*`)
- `pyo3-polars` — version + features
- `polars` — version
- `polars-arrow` — version

**Rust side — resolved:** read the actual resolved `polars` crate version from `bartons/Cargo.lock` (`grep -A1 '^name = "polars"' bartons/Cargo.lock`). The `Cargo.toml` range is the *request*; the lockfile is what was *built*.

**Python side — [pyproject.toml](../../pyproject.toml):**
- `[build-system] requires` — any `polars` / `maturin` bound
- `[project] requires-python`
- `[project] dependencies` — **is there an enforced `polars >=x,<y` cap here?** This is the *single* install-time gate the lockstep note argues for; note explicitly if it is missing.
- `[build-system] requires` — should **not** carry a polars bound (maturin doesn't need polars-Python to build); flag it as redundant if present.
- `[dependency-groups] dev` — should **not** pin/list polars; it is pulled in transitively under the `[project].dependencies` cap. Flag a redundant entry here.
- `[tool.maturin]` — `module-name`, `manifest-path` (for orientation)

**Installed runtime:** the polars-Python actually in the venv: `.venv/bin/python -c "import polars; print(polars.__version__)"`.

**Anything else:** `grep -rEn --exclude-dir=target --exclude-dir=.venv --exclude-dir=.git '^[+-]?\s*polars(-arrow)?\s*=' .` to catch stray references.

## Cross-checks to perform

1. **polars vs polars-arrow** in Cargo.toml must be the same version.
2. **Cargo.toml `polars` request vs Cargo.lock resolved** — are they consistent?
3. **Rust crate ↔ installed polars-Python.** Map the resolved Rust `polars` crate version to the polars-Python version family it pairs with (use the tables in the two docs as a prior; the crate and Python package use *different* numbering — crate `0.5x` vs package `1.4x`). Flag loudly if the plugin is compiled against a crate that does **not** match the installed polars-Python — that is a latent load/handshake failure or silent-corruption risk.
4. **The install cap — declared exactly once.** The `polars >=x,<y` cap belongs in `[project].dependencies` and **only there** (polars is a real runtime dependency of the plugin). If it is missing, the coupling is *de facto* (works) but not *enforced* — nothing stops a bad polars from being installed; call this out. Conversely, a polars bound in `[build-system].requires` or a polars entry in `[dependency-groups].dev` is **redundant duplication** that can drift out of sync — flag it for removal.
5. **pyo3 ↔ pyo3-polars.** pyo3-polars caret-pins a pyo3 range (its second lockstep axis — see the doc's "pyo3 is the single dial" section). Confirm the `pyo3` pin falls inside the range the installed pyo3-polars requires (read its `pyo3` `req` from `curl -s -H "User-Agent: bartons-bindings" https://crates.io/api/v1/crates/pyo3-polars/<ver>/dependencies`). Confirm `Cargo.lock` has **exactly one** pyo3 version (`grep -E '^name = "pyo3"$' -A1 bartons/Cargo.lock`) — two pyo3 copies mean a broken `extension-module` build.
6. **pyo3 abi3 floor vs requires-python** — sanity only.

## Output

Present a compact table: **setting → file → declared value → resolved/effective value**, grouped Rust side then Python side. Below it, a short findings list: each inconsistency or gap with its severity (mismatch = high, missing cap = medium, cosmetic = low).

Do **not** change anything. End by summarizing the situation in one or two sentences and asking the user how they want to proceed — e.g. run `/upgrade-bindings` to realign on the latest compatible set, or pin a specific target.
