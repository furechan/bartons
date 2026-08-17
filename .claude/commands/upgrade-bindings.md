---
description: Derive the latest compatible pyo3-polars / polars / pyo3 version set from upstream, propose new Cargo.toml + pyproject.toml pins, and rebuild only after the user approves.
argument-hint: "[optional: target polars-py version, e.g. 1.42]"
allowed-tools: Read, Bash, Grep, Glob, Edit
---

Upgrade the **version lock-in** of this native polars plugin to the latest mutually-compatible set, deriving the numbers from upstream machine-readable sources — never guess. **Propose the new settings and get explicit approval BEFORE recompiling.**

Read the derivation method in [docs/cargo-version-pins.md](../../docs/cargo-version-pins.md) before starting, including its Naming section: **polars-rs** is the Rust crate (`0.5x`) and **polars-py** the Python package (`1.4x`) — never a bare "polars <version>". Optional argument `$1` = a target polars-py version to upgrade toward (e.g. `1.42`); if absent, target the latest stable release.

## Step 0 — require a clean, synced tree

Check `git status` and the tracking branch **before anything else**. Require a
clean working tree, in sync with `origin`. If it is dirty or behind, **stop** and
ask the user to commit, stash or pull first — do not start and do not "work
around" it.

This is not hygiene, it is what makes the rest of the procedure safe. The steps
below edit `Cargo.toml`, `Cargo.lock`, possibly several kernel source files (a
crate-minor jump breaks Rust API), and `pyproject.toml` — and the documented
escape at every gate is *revert*. `git checkout -- .` only backs out the upgrade
if the upgrade is the only thing in the tree. Starting dirty means a failed
upgrade can no longer be cleanly undone, which is exactly the half-migrated state
step 4 warns against.

Being in sync matters for the same reason in the other direction: an upgrade
derived on top of a stale branch may conflict with pins someone already changed.

## Step 1 — current state

Establish the current pins exactly as `/check-bindings` does (Cargo.toml: `pyo3`, `pyo3-polars`, `polars`, `polars-arrow`; Cargo.lock resolved `polars`; pyproject `[build-system].requires`, `[project].dependencies` polars-py range, dev-group polars; installed venv polars). Summarize them so the proposed diff is meaningful.

## Step 2 — derive the latest compatible set from upstream

Use these sources (all structured; prefer `gh`/`curl` + parse). **crates.io rejects requests without a `User-Agent`** — always pass `-H "User-Agent: bartons-bindings"`:

1. **Latest `pyo3-polars`** — `curl -s -H "User-Agent: bartons-bindings" https://crates.io/api/v1/crates/pyo3-polars | python3 -c "import sys,json;print(json.load(sys.stdin)['crate']['max_stable_version'])"`.
2. **That pyo3-polars → polars-rs `req`** — `curl -s -H "User-Agent: bartons-bindings" https://crates.io/api/v1/crates/pyo3-polars/<ver>/dependencies` and read the `polars` dependency `req` (e.g. `^0.54.4`).
3. **Latest (or `$1` target) polars-py** — `curl -s https://pypi.org/pypi/polars/json | python -c "import sys,json;print(json.load(sys.stdin)['info']['version'])"`.
4. **polars-py tag → polars-rs** — the `pola-rs/polars` monorepo dual-tags `py-*` and `rs-*`; the `[workspace.package] version` at a `py-` tag *is* the polars-rs version:
   `gh api -H "Accept: application/vnd.github.raw" "repos/pola-rs/polars/contents/Cargo.toml?ref=py-<X.Y.Z>"` then grep the workspace `version`.
   Walk a few adjacent `py-` minors to find the **contiguous run** on the same polars-rs — that run tells you which polars-py versions share the engine you are building against, which is what the matrix should cover. The ceiling itself is set by `just raise-ceiling` (step 6), not derived here.
5. **`pyo3` — driven by pyo3-polars, NOT latest.** Read the chosen pyo3-polars's `pyo3` `req` from the same `/dependencies` JSON (e.g. 0.27 → `pyo3 ^0.28`). Pin pyo3 to satisfy *that* req — the latest pyo3 is often **ahead** of it (latest was `0.29` while 0.27 capped at `^0.28`). Do not take latest pyo3 blindly: the `extension-module` feature allows **exactly one pyo3 in the build tree**, so a pin that disagrees with pyo3-polars's pulls in two pyo3 copies and the build fails hard. Keep the existing `extension-module` + `abi3-py*` features.

Sanity-check that the pieces agree: the polars-rs version the chosen pyo3-polars depends on should match the one the target polars-py tag resolves to. If they diverge, prefer the pyo3-polars-compatible polars-rs and pick the polars-py window that maps to it — explain the choice.

## Step 3 — propose, do not apply yet

Present a clear before → after table for every changed pin across both files:
- `bartons/Cargo.toml`: `pyo3`, `pyo3-polars`, `polars`, `polars-arrow` (preserve all existing feature flags).
- `pyproject.toml`: the enforced `polars >=floor,<ceiling` range.

### The range is declared exactly ONCE — in `[project].dependencies`

`polars` is a genuine runtime dependency of this plugin (it is a polars plugin, unusable without it), so its range belongs in `[project].dependencies` and **only there**. Do not duplicate the version window across the file:

- **`[project].dependencies`** — add/maintain `polars >=lower,<upper` here. This is the single source of truth and the install-time gate uv resolves against.
- **`[build-system].requires`** — must **not** carry a polars bound. maturin compiles the Rust crate; polars-rs comes from Cargo/crates.io, and the runtime version handshake happens at *import* time, not build time. polars-py is not needed to build at all — if a `polars` entry exists here, **remove it**.
- **`[dependency-groups].dev`** — must **not** pin polars. Installing the project (editable) into the dev env already pulls polars in, constrained by the `[project].dependencies` range. A bare `polars` line is redundant — **remove it**; leave the range to flow transitively.

Rationale: one range = one place to update and no chance of the three drifting out of sync. (See [docs/cargo-version-pins.md](../../docs/cargo-version-pins.md), "The single dial: pick `pyo3-polars` first".)

State in one line which polars-py versions share the polars-rs you are building against (e.g. "polars-rs 0.54.4 → polars-py 1.42.0–1.43.2"). Then **stop and ask the user to approve** the proposed pins. Do not edit files until they confirm.

## Applying it — one variable at a time

Do **not** edit both files at once. Changing the Cargo pins moves the compiled
binary; changing the polars-py range moves the *installed engine*. Do them
together and a failure tells you nothing about which side caused it. Each step
below has a single success criterion — stop at the first one that fails.

### Step 4 — apply the Cargo pins, get a working binary (only after approval)

Touch **`bartons/Cargo.toml` only**. Leave `pyproject.toml` alone so the
installed polars-py stays exactly where it is.

1. Edit the four crate pins to the approved values; keep every feature flag
   (`extension-module`, `abi3-py*`, the `dtype-*` set) intact.
2. `just develop`. **Expect Rust source breakage on crate-minor jumps** — polars
   renames/removes API across minors (e.g. `ChunkedArray::into_iter` → `.iter()`),
   and several minors at once compounds it. A compile error here is normal, not a
   dead end: read `cargo build --manifest-path bartons/Cargo.toml --lib` (faster
   than the full wheel build), fix the source, re-try.
3. Confirm `bartons/Cargo.lock` resolved to what step 2 predicted.

**Success: it compiles and the module imports.** If you cannot resolve the API
changes, surface the errors and offer to revert — never leave the tree
half-migrated silently.

### Step 5 — test the Python side against the *installed* polars-py

Still no `pyproject.toml` edit. This is the question that matters most, and it is
only answerable while the engine is held fixed: **does the newly built plugin
still work against the polars-py already in the venv?**

Run `just test` and report pass/fail with output.

**Success: the suite passes.** A failure here is a genuine
new-plugin-vs-existing-engine incompatibility, not a build problem — which is
precisely the thing the pins exist to prevent, so say so plainly rather than
patching tests. If the module *fails to load* with a version/handshake error, go
to step 7.

### Step 6 — update the polars-py range, if it should move

Only now edit `pyproject.toml`, and only the `[project].dependencies` range.

- The **floor** moves only for a functional reason (something the plugin needs
  that older polars-py lacks) — not merely because the crate advanced.
- The **ceiling** is whatever the matrix has verified. Do not edit the number by
  hand: run **`just raise-ceiling`**, which looks up the newest polars-py, adds it
  to `COMPAT_VERSIONS`, runs `compat` against it, and moves the ceiling only if
  that passes — rolling back and leaving the range honest if it does not. If you
  do not run it, leave the ceiling alone and say so.

If the range moved, note that `just develop` / `uv sync` will pull a different
polars-py into the venv — which makes step 5's result no longer the last word;
re-run `just test` afterwards.

### Step 7 — FFI handshake — only if needed

**Skip this in the normal case.** The plugin FFI version has been `(0, 1)` since
polars-rs `0.37.0`; it almost never moves, and checking it on every routine bump
is noise.

Do check it when either is true: step 4 or 5 ended in a *load*/handshake failure,
or the polars-rs jump crosses a boundary where
[docs/polars-ffi-version-table.md](../../docs/polars-ffi-version-table.md) shows
the FFI version changing. That table also documents how to read the constants out
of any published `polars-ffi` crate.

**If the FFI version has actually changed, stop.** That is a compatibility event,
not a version bump, and this procedure is the wrong tool for it — every existing
polars-py in the range may no longer be able to load the plugin. Report it and
work out the consequences separately.

### Finally

If `CHANGELOG.md` exists, add an entry under the latest version heading noting
the polars-rs / pyo3-polars bump and any range change. End by reporting the final
state and any follow-up (e.g. publishing a new plugin release so the range chain
lets consumers co-upgrade).
