# Archived: GitHub Actions release automation

Built 2026-08-17, archived the same day, unused. Kept because the analysis behind
it is worth more than the YAML, and because reviving it is a matter of unzipping
into `.github/` if the project ever has consumers beyond the two machines it was
written for.

## What this was

A complete PyPI release pipeline for `bartons`:

- **`build.yml`** — builds five `cp311-abi3` wheels (linux x86_64/aarch64, macOS
  arm64/x86_64, Windows x64) plus the sdist. A `setup` job emits the matrix as
  JSON so the target list can be scoped at dispatch time (`linux` or `full`).
- **`release.yml`** — on manual dispatch: resolve the `build.yml` run for this
  commit, verify it, and publish its artifacts to PyPI over OIDC. Builds nothing.
  `dry_run` defaults to true, so the default invocation resolves and reports
  without publishing.
A step-by-step release handoff also existed; it was dropped rather than archived,
being wholly CI-specific. The parts of it that outlive CI — the version policy and
the PyPI notes — are recorded below.

## Why it was archived

The repository is private and early, and its only consumers are two machines the
author controls — an OrbStack VM and `boston`, an EC2 Graviton instance. Both are
**aarch64 Linux**: orb on Ubuntu 25.04 (glibc 2.41, Python 3.11), boston on Ubuntu
24.04 (glibc 2.39, Python 3.12). A single locally-built aarch64 wheel serves both,
so four of the five CI targets existed for users who do not exist. Building sdists
and aarch64 wheels from the dev machine is the proportionate answer at this stage.

## What was learned along the way

Worth keeping whether or not the workflows come back.

**`abi3-py311` collapses the build matrix.** One `cp311-abi3` wheel per (OS, arch)
serves every Python 3.11+, so there is no Python axis at all. Demonstrated on the
author's own fleet: orb runs 3.11.14, boston runs 3.12.3, one wheel covers both.

**Private-repo CI minutes are metered with per-OS multipliers** — linux ×1,
windows ×2, macOS ×10. The full six-job matrix bills roughly:

| Job | Wall | Multiplier | Billed |
|---|---|---|---|
| linux-x86_64 | ~8 min | ×1 | 8 |
| linux-aarch64 (cross) | ~10 min | ×1 | 10 |
| macos-arm64 | ~8 min | ×10 | 80 |
| macos-x86_64 | ~8 min | ×10 | 80 |
| windows-x64 | ~8 min | ×2 | 16 |
| sdist | ~1 min | ×1 | 1 |
| | | | **~195** |

That number is why there is no `push` trigger at all: a README fix landing on
`main` would otherwise have cost ~200 billed minutes.

As archived, `build.yml` also ran on pull requests (linux only, and only when
packaging or compiled code changed) and could be called by `release.yml` via
`workflow_call`. Both were removed on 2026-08-21, leaving `workflow_dispatch`
alone: every build is now something asked for by name. `workflow_call` in
particular is incompatible with how `release.yml` now works — a reusable
workflow uploads its artifacts to the *caller's* run, so a called build has no
run of its own for the commit -> run -> artifacts search to find.

Two costs of that, both deliberate. `workflow_dispatch` is resolved from the
**default branch**, so a change to `build.yml` cannot be exercised before it
merges — `pull_request` was the only pre-merge path that ran it. And the dispatch
default is `linux`, so a release wants `-f scope=full`; `release.yml`'s guard
names the missing artifacts when it is short.

**Wheels must not be accumulated across runs without proving provenance.** GitHub
artifacts are scoped to their run, so assembling a release from an earlier run
means pulling artifacts by run ID — and by itself nothing then guarantees they
came from the commit being released. Wheels from different runs can carry
identical version numbers and different code.

The original design ruled that out by building everything inside the tag's own
run, at the cost of rebuilding artifacts you may have just built by hand — and it
then needed an approval gate to make the result inspectable before upload.

**The current design closes the gap directly instead** (rewritten 2026-08-21).
Every run records the `head_sha` it was built from, and each artifact belongs to
exactly one run, so `release.yml` searches commit -> run -> artifacts: the run it
resolves must have `head_sha` equal to the commit being released, must have
succeeded, must carry the complete artifact set, and none of them may have
expired. That is the same guarantee the single-run design got structurally, made
explicit — which is the trade, since it is now code that can have bugs rather
than an invariant that cannot be violated.

What it buys is a build step and a publish step that are genuinely separate: build
on demand, inspect the real artifacts at leisure, publish exactly those. It also
halves the cost, since the release no longer rebuilds what you already built.

**On the approval gate.** `environment: pypi` with required reviewers pauses the
publish job, giving the same inspect-then-ship shape within one run. It is
declared in `release.yml` and the environment was created on 2026-08-17, but
required reviewers were never enabled — and cannot be, on a **private** repo on
the **Free** plan, where environment protection rules are unavailable. The
two-step flow above needs no plan and no pause, which is why it is the primary
mechanism; the gate becomes an option if the repo goes public.

Note the interaction with **artifact retention**: with build and publish fused,
artifacts only had to survive minutes. Split apart, the retention window is how
long a build stays releasable — `release.yml` refuses expired artifacts, so an
aged-out build must be rebuilt. `build.yml` sets `retention-days: 30` rather than
the 90-day default: a generous deadline that still needs ~15 full matrices in a
month to press the 500 MB Free storage quota, a full run being ~33 MB. Actions
storage is free on public repos, so this only binds while the repo is private.

**Publishing failure is atomic.** `publish` declared `needs: build`, so any failing
target meant nothing was published. A broken release is a wasted run and a deleted
tag, never a half-published version.

**manylinux tags come from the build environment, not the host you want.**
`maturin build` on the dev machine (glibc 2.41) produced `manylinux_2_34`, which
would fail to install on anything older. CI built inside `manylinux_2_28`
containers instead. Relevant to manual releases too: a wheel built locally carries
whatever floor the local toolchain implies.

**OIDC / PyPI trusted publishing** removes the stored API token. The job mints a
short-lived signed JWT identifying repo + workflow + ref, PyPI validates it and
returns a 15-minute project-scoped credential. It requires `id-token: write` on
the publish job only, and a trusted publisher registered on PyPI naming the
workflow file and environment. A laptop cannot do this — publishing by hand means
an API token again.

## Notes that outlived the workflows

These are properties of the project, not of CI:

- **The polars-py range freezes at upload.** `polars>=1.28,<1.44` becomes immutable
  `Requires-Dist` metadata on a published wheel. `just raise-ceiling` only affects
  future releases, so raising the ceiling means cutting one.
- **`runtime-64` users are unserved.** `IdxSize` is compile-time, one `.so` cannot
  serve both polars engines, and no wheel tag can express the difference. The
  wheels are runtime-32. A `bartons-bigidx` distribution is the answer if it ever
  matters. See `docs/polars-runtime-libraries.md`.
- **PyPI never lets a filename be reused.** Deleting a release or file does not
  free its name, so a bad wheel cannot be replaced — only superseded by a new
  version. Yank rather than delete; yanking is per-release, not per-file.
- **The old `bartons` on PyPI** (`0.0.0`, `0.0.1`, April 2025) is an unrelated
  stock-price skeleton by the same author, superseded by `bardata`. It should be
  yanked before or alongside the first real release.
- **Version policy** (kept in the repo, unrelated to CI): `pyproject.toml` is the
  single authoritative version and the crate's stays at `0.0.0`. The in-repo
  version names the *next* release, **plain — no `.devN` suffix**, so the tree is
  publishable at any moment and nothing needs editing before a build. Releasing
  uploads what the version already says; `just bump` afterwards names the one
  after. A `.devN` scheme was tried first and dropped before 0.1.0. This README
  and `release.yml` both described that retired scheme until 2026-08-21; the
  decision to keep stable-only rather than restore it is recorded in
  `BACKLOG.md`, and rests on the PyPI-availability check in `guard` making a
  re-publish structurally impossible — the protection `.devN` was buying.

## Reviving it

```sh
mkdir -p .github/workflows
cp archive/github-workflow/release.yml archive/github-workflow/build.yml .github/workflows/
```

These were a zip until 2026-08-21, unpacked so they can be read and edited in
place. The `.yml` files are inert here — GitHub only runs what is under
`.github/workflows/` — and the original zip remains in git history.

Then: register the PyPI trusted publisher (owner/repo, workflow `release.yml`,
environment `pypi`), create the `pypi` environment in repository settings, and add
required reviewers to it. Action versions in the YAML were current on 2026-08-17
and will need refreshing.

Note that the PyPI trusted publisher and the `pypi` environment were both
configured on 2026-08-17 and were never removed. They are inert while no
`release.yml` exists — nothing can invoke them — but the trusted publisher entry
is a standing authorization for a workflow of that name in this repository, and
can be deleted from the PyPI project settings if that is not wanted.
