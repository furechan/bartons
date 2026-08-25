# GitHub Actions workflows

## Status

**Active. Dispatch-only. The release mechanism.**

| | |
|---|---|
| Releases today | built by `build.yml`, published by `publish.yml` — see [CLAUDE.md](../CLAUDE.md) |
| These workflows | active and dispatch-only; nothing runs implicitly on a push, PR or tag |
| Repository | public, GitHub Free |
| Server-side config | PyPI trusted publisher and GitHub `pypi` environment configured |
| First publication | `0.1.3` on 2026-08-25; five wheels uploaded, sdist rejected for a missing declared license file |

CI became the sole release path on 2026-08-25. The local publisher must not upload
a version also handled by CI: PyPI never frees a filename, and the two paths cannot
safely share ownership of one release.

Both are **dispatch-only** — nothing runs on a push, a pull request, a tag or a
schedule — and `publish.yml` publishes nothing unless explicitly told to.

Built 2026-08-17, archived unused the same day, then reworked and installed for
experimentation on 2026-08-21. The first full matrix and trusted-publishing run
completed on 2026-08-25; the results and recovery notes below supersede the old
prototype status.

## What this is

A PyPI release pipeline for `bartons`:

- **`build.yml`** — builds five `cp311-abi3` wheels (linux x86_64/aarch64, macOS
  arm64/x86_64, Windows x64) plus the sdist. Native YAML matrices separate the
  always-built Linux targets from the macOS and Windows targets selected by a
  `full` dispatch.
- **`publish.yml`** — on manual dispatch: resolve the `build.yml` run for this
  commit, verify it, and publish its artifacts to PyPI over OIDC. Builds nothing.
  `dry_run` defaults to true, so the default invocation resolves and reports
  without publishing.
A step-by-step release handoff also existed; it was dropped rather than archived.
The live procedure is in [CLAUDE.md](../CLAUDE.md); the design and operational
history remain here.

## Why it was archived at first

The repository is private and early, and its only consumers are two machines the
author controls — an OrbStack VM and `boston`, an EC2 Graviton instance. Both are
**aarch64 Linux**: orb on Ubuntu 25.04 (glibc 2.41, Python 3.11), boston on Ubuntu
24.04 (glibc 2.39, Python 3.12). A single locally-built aarch64 wheel serves both,
so four of the five CI targets existed for users who do not exist. Building sdists
and aarch64 wheels from the dev machine is the proportionate answer at this stage.

## What was learned along the way

**`abi3-py311` collapses the build matrix.** One `cp311-abi3` wheel per (OS, arch)
serves every Python 3.11+, so there is no Python axis at all. Demonstrated on the
author's own fleet: orb runs 3.11.14, boston runs 3.12.3, one wheel covers both.

**Private-repo CI minutes are metered with per-OS multipliers** — linux ×1,
windows ×2, macOS ×10. The full six-job matrix bills roughly:

| Job | Wall | Multiplier | Billed |
|---|---|---|---|
| linux-x86_64 | ~8 min | ×1 | 8 |
| linux-aarch64 (native) | ~10 min | ×1 | 10 |
| macos-arm64 | ~8 min | ×10 | 80 |
| macos-x86_64 | ~8 min | ×10 | 80 |
| windows-x64 | ~8 min | ×2 | 16 |
| sdist | ~1 min | ×1 | 1 |
| | | | **~195** |

That number is why there is no `push` trigger at all: a README fix landing on
`main` would otherwise have cost ~200 billed minutes.

As archived, `build.yml` also ran on pull requests (linux only, and only when
packaging or compiled code changed) and could be called by `publish.yml` via
`workflow_call`. Both were removed on 2026-08-21, leaving `workflow_dispatch`
alone: every build is now something asked for by name. `workflow_call` in
particular is incompatible with how `publish.yml` now works — a reusable
workflow uploads its artifacts to the *caller's* run, so a called build has no
run of its own for the commit -> full-run search to find.

Two costs of that, both deliberate. `workflow_dispatch` is resolved from the
**default branch**, so a change to `build.yml` cannot be exercised before it
merges — `pull_request` was the only pre-merge path that ran it. And the dispatch
default is `linux`, so a release wants `-f scope=full`; each run records its
scope in its display name so `publish.yml` can select only `Build (full)`.

**Wheels must not be accumulated across runs without proving provenance.** GitHub
artifacts are scoped to their run, so assembling a release from an earlier run
means pulling artifacts by run ID — and by itself nothing then guarantees they
came from the commit being released. Wheels from different runs can carry
identical version numbers and different code.

The original design ruled that out by building everything inside the tag's own
run, at the cost of rebuilding artifacts you may have just built by hand — and it
then needed an approval gate to make the result inspectable before upload.

**The current design closes the gap directly instead** (rewritten 2026-08-21).
Every run records the `head_sha` it was built from and its scope in its display
name. `publish.yml` selects the newest successful `Build (full)` run whose
`head_sha` equals the commit being released. Workflow success guarantees every
full-matrix job completed; artifact download fails if its files have expired.

What it buys is a build step and a publish step that are genuinely separate: build
on demand, inspect the real artifacts at leisure, publish exactly those. It also
halves the cost, since the release no longer rebuilds what you already built.

**On the approval gate.** `environment: pypi` with required reviewers pauses the
publish job, giving the same inspect-then-ship shape within one run. It is
declared in `publish.yml`; the environment was created on 2026-08-25. Required
reviewers were unavailable while the repository was private on GitHub Free and
can be enabled now that it is public. The explicit dry-run/full-publish split
remains required even with an approval gate.

Note the interaction with **artifact retention**: with build and publish fused,
artifacts only had to survive minutes. Split apart, the retention window is how
long a build stays releasable — downloading expired artifacts fails, so an
aged-out build must be rebuilt. `build.yml` sets `retention-days: 30` rather than
the 90-day default. This originally protected the private repository's 500 MB
Free storage quota; public-repository Actions storage is unmetered, but the
30-day release deadline remains explicit.

**Publishing failure is not atomic.** PyPI accepts files one at a time and never
frees their names. The first CI publication uploaded all five `0.1.3` wheels, then
rejected the sdist because its metadata declared `LICENSE.txt` while the archive
omitted it. `skip-existing: true` makes a retry capable of filling missing files,
but it cannot replace an accepted file. Always inspect PyPI after a failed upload.

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

## Notes independent of CI

These are properties of the project, not of CI:

- **The polars-py range freezes at upload.** `polars>=1.28,<1.44` becomes immutable
  `Requires-Dist` metadata on a published wheel. `uv run inv raise-ceiling` only affects
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
  uploads what the version already says; the publish task's patch bump afterwards
  names the one after. A `.devN` scheme was tried first and dropped before 0.1.0. This README
  and `publish.yml` both described that retired scheme until 2026-08-21; the
  decision to keep stable-only rather than restore it is recorded in
  `BACKLOG.md`. The CI publisher skips filenames already present on PyPI, making
  a repeated dispatch idempotent for those files; advancing the version remains
  the release process's responsibility.

## Current server-side setup

- PyPI trusts owner `furechan`, repository `bartons`, workflow `publish.yml`, and
  environment `pypi`.
- GitHub has a `pypi` environment. Add a required reviewer now that the repository
  is public if an account-side approval pause is desired.
- Full build run [`32898960470`](https://github.com/furechan/bartons/actions/runs/32898960470)
  succeeded on 2026-08-25 at commit `8200fbf`, producing and smoke-testing five
  platform wheels plus the sdist.
- Publish run [`32902795340`](https://github.com/furechan/bartons/actions/runs/32902795340)
  authenticated successfully through OIDC and partially published `0.1.3`. The
  sdist license omission is fixed for `0.1.4`; `0.1.3` should be yanked after the
  complete replacement release is available.

## Why the repository is public

The repository became public on 2026-08-25 for these operational benefits:

- **Runner minutes become free.** Standard runners are unmetered on public repos,
  so the multipliers stop mattering and the full six-target matrix costs nothing.
  The full matrix no longer consumes the private-repository Free allowance.
- **The approval gate becomes available.** Environment protection rules — required
  reviewers pausing the publish job — are available on a public Free repository.
- **Artifact storage becomes free**, which removes the retention/quota tension and
  the reason `retention-days` is capped at 30.
- **Little is actually hidden today.** The published sdist on PyPI already contains
  every `.rs` and `.py` source file; making the repository public additionally
  exposes its docs, tests, tooling and commit history.

## Release commands

```sh
gh workflow run build.yml -f scope=full
gh run watch <run-id>
gh run download <run-id> --dir /tmp/check
gh workflow run publish.yml                   # dry run: resolves, reports, publishes nothing
gh workflow run publish.yml -f dry_run=false  # publish the inspected artifacts
```

The dry run is safe to repeat. Only `-f dry_run=false` uploads.
