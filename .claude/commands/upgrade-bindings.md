---
description: Derive the latest compatible pyo3-polars / polars / pyo3 version set from upstream, propose new Cargo.toml + pyproject.toml pins, and rebuild only after the user approves.
argument-hint: "[optional: target polars-Python version, e.g. 1.42]"
allowed-tools: Read, Bash, Grep, Glob, Edit
---

Upgrade the **version lock-in** of this native polars plugin to the latest mutually-compatible set, deriving the numbers from upstream machine-readable sources — never guess. **Propose the new settings and get explicit approval BEFORE recompiling.**

Read the derivation method in [docs/pyo3-polars-version-lockstep.md](../../docs/pyo3-polars-version-lockstep.md) before starting. Optional argument `$1` = a target polars-Python version to upgrade toward (e.g. `1.42`); if absent, target the latest stable release.

## Step 1 — current state

Establish the current pins exactly as `/check-bindings` does (Cargo.toml: `pyo3`, `pyo3-polars`, `polars`, `polars-arrow`; Cargo.lock resolved `polars`; pyproject `[build-system].requires`, `[project].dependencies` polars cap, dev-group polars; installed venv polars). Summarize them so the proposed diff is meaningful.

## Step 2 — derive the latest compatible set from upstream

Use these sources (all structured; prefer `gh`/`curl` + parse). **crates.io rejects requests without a `User-Agent`** — always pass `-H "User-Agent: bartons-bindings"`:

1. **Latest `pyo3-polars`** — `curl -s -H "User-Agent: bartons-bindings" https://crates.io/api/v1/crates/pyo3-polars | python3 -c "import sys,json;print(json.load(sys.stdin)['crate']['max_stable_version'])"`.
2. **That pyo3-polars → polars Rust crate `req`** — `curl -s -H "User-Agent: bartons-bindings" https://crates.io/api/v1/crates/pyo3-polars/<ver>/dependencies` and read the `polars` dependency `req` (e.g. `^0.54.4`).
3. **Latest (or `$1` target) polars-Python** — `curl -s https://pypi.org/pypi/polars/json | python -c "import sys,json;print(json.load(sys.stdin)['info']['version'])"`.
4. **polars-Python tag → Rust crate** — the `pola-rs/polars` monorepo dual-tags `py-*` and `rs-*`; the `[workspace.package] version` at a `py-` tag *is* the Rust crate version:
   `gh api -H "Accept: application/vnd.github.raw" "repos/pola-rs/polars/contents/Cargo.toml?ref=py-<X.Y.Z>"` then grep the workspace `version`.
   Walk a few adjacent `py-` minors to find the **contiguous run** on the same Rust crate — that run is your install window `>=lower,<upper` (remember: PEP 440, cap with `< next_minor`, never `<= this_minor`).
5. **`pyo3` — driven by pyo3-polars, NOT latest.** Read the chosen pyo3-polars's `pyo3` `req` from the same `/dependencies` JSON (e.g. 0.27 → `pyo3 ^0.28`). Pin pyo3 to satisfy *that* req — the latest pyo3 is often **ahead** of it (latest was `0.29` while 0.27 capped at `^0.28`). Do not take latest pyo3 blindly: the `extension-module` feature allows **exactly one pyo3 in the build tree**, so a pin that disagrees with pyo3-polars's pulls in two pyo3 copies and the build fails hard. Keep the existing `extension-module` + `abi3-py*` features.

Sanity-check that the pieces agree: the polars crate that the chosen pyo3-polars depends on should match the crate the target polars-Python tag resolves to. If they diverge, prefer the pyo3-polars-compatible crate and pick the polars-Python window that maps to it — explain the choice.

## Step 3 — propose, do not apply yet

Present a clear before → after table for every changed pin across both files:
- `bartons/Cargo.toml`: `pyo3`, `pyo3-polars`, `polars`, `polars-arrow` (preserve all existing feature flags).
- `pyproject.toml`: the enforced `polars >=lower,<upper` cap.

### The cap is declared exactly ONCE — in `[project].dependencies`

`polars` is a genuine runtime dependency of this plugin (it is a polars plugin, unusable without it), so its cap belongs in `[project].dependencies` and **only there**. Do not duplicate the version window across the file:

- **`[project].dependencies`** — add/maintain `polars >=lower,<upper` here. This is the single source of truth and the install-time gate uv resolves against.
- **`[build-system].requires`** — must **not** carry a polars bound. maturin compiles the Rust crate; the Rust `polars` comes from Cargo/crates.io, and the runtime version handshake happens at *import* time, not build time. polars-Python is not needed to build at all — if a `polars` entry exists here, **remove it**.
- **`[dependency-groups].dev`** — must **not** pin polars. Installing the project (editable) into the dev env already pulls polars in, constrained by the `[project].dependencies` cap. A bare `polars` line is redundant — **remove it**; leave the cap to flow transitively.

Rationale: one cap = one place to update and no chance of the three drifting out of sync. (See [docs/pyo3-polars-version-lockstep.md](../../docs/pyo3-polars-version-lockstep.md) "resolver model".)

State the derived ABI window in one line (e.g. "crate 0.54 → polars-Python >=1.42,<1.43"). Then **stop and ask the user to approve** the proposed pins. Do not edit files until they confirm.

## Step 4 — apply, rebuild, verify (only after approval)

1. Edit `bartons/Cargo.toml` and `pyproject.toml` with the approved values (Edit tool; keep feature flags and formatting intact).
2. If the installed venv polars is now outside the new window, note that `just build` / `uv sync` will move it.
3. Rebuild: `just build` (maturin develop). **Expect Rust source breakage on crate-minor jumps** — polars renames/removes API across minors (e.g. `ChunkedArray::into_iter` → `.iter()`), and several minors at once compounds it. A compile error here is normal, not a dead end: read the `cargo build --manifest-path bartons/Cargo.toml --lib` errors (faster than the full wheel build), fix the source on this branch, and re-try. Only if it fails to *load* (handshake/ABI) after compiling, or you can't resolve the API changes, surface the error and offer to revert — never leave the tree half-migrated silently.
4. On success run `just test`. Report pass/fail with output.
5. If `CHANGELOG.md` exists, add an entry under the latest version heading noting the polars/pyo3-polars bump.

End by reporting the final state and any follow-up (e.g. publishing a new plugin release so the cap chain lets consumers co-upgrade).
