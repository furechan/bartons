# GitHub Actions workflows

## Status

**Experimental. Inactive. Not the release mechanism.**

| | |
|---|---|
| Releases today | cut locally with `uv run inv build` and `uv run inv publish` — see [CLAUDE.md](../CLAUDE.md) |
| These workflows | installed, dispatch-only, **never used to publish anything** |
| Repository | private, GitHub Free |
| Server-side config | **absent** — no PyPI trusted publisher, no GitHub environment |
| Would benefit from | the repo going public — see [Why public would help](#why-public-would-help) |

Nothing should be published through these until that is a deliberate decision
rather than a default. They are a *second* upload path for the same artifacts,
and PyPI never frees a filename, so only one path may own a release.

**Standing decision (2026-08-21): kept as a prototype, deferred until the
repository goes public or the project becomes more prominent.** The local release
cycle is sufficient at this scale — the author is effectively the only consumer,
and the local `uv run inv build` task already builds and validates the complete
sdist-to-wheel artifact chain. Everything CI would add is either free only
on a public repo (unmetered runners, the approval gate, artifact storage) or
matters only with users to protect. Revisit at that point, not before; the
workflows stay installed and inert so the analysis and the working YAML are both
to hand when it happens.

Both are **dispatch-only** — nothing runs on a push, a pull request, a tag or a
schedule — and `publish.yml` publishes nothing unless explicitly told to.

Built 2026-08-17, archived unused the same day, then reworked and installed for
experimentation on 2026-08-21. The history matters because much of what follows
was learned while deciding *not* to run this, and the cost analysis is why it is
shaped the way it is.

## What this is

A PyPI release pipeline for `bartons`, on trial:

- **`build.yml`** — builds five `cp311-abi3` wheels (linux x86_64/aarch64, macOS
  arm64/x86_64, Windows x64) plus the sdist. Native YAML matrices separate the
  always-built Linux targets from the macOS and Windows targets selected by a
  `full` dispatch.
- **`publish.yml`** — on manual dispatch: resolve the `build.yml` run for this
  commit, verify it, and publish its artifacts to PyPI over OIDC. Builds nothing.
  `dry_run` defaults to true, so the default invocation resolves and reports
  without publishing.
A step-by-step release handoff also existed; it was dropped rather than archived,
being wholly CI-specific. The parts of it that outlive CI — the version policy and
the PyPI notes — are recorded below.

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
declared in `publish.yml` and the environment was created on 2026-08-17, but
required reviewers were never enabled — and cannot be, on a **private** repo on
the **Free** plan, where environment protection rules are unavailable. The
two-step flow above needs no plan and no pause, which is why it is the primary
mechanism; the gate becomes an option if the repo goes public.

Note the interaction with **artifact retention**: with build and publish fused,
artifacts only had to survive minutes. Split apart, the retention window is how
long a build stays releasable — downloading expired artifacts fails, so an
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

## Setup still outstanding

The workflows are in place, but the account-side configuration is not finished:

- **PyPI trusted publisher — none exists.** One was registered on 2026-08-17
  naming workflow `release.yml`, and has since been removed. Nothing on the PyPI
  side authorizes this repository today, which also means the 2026-08-21 rename to
  `publish.yml` costs nothing: there is no stale entry to correct, only one to
  create. Registering it — owner/repo, workflow **`publish.yml`**, environment
  `pypi` — is a prerequisite for any upload, since trusted publishing is keyed to
  the workflow *filename*. Without it, OIDC auth fails at the last step, after the
  whole matrix has been built.
- **The `pypi` GitHub environment — does not exist either.** The GitHub API reports
  zero environments on this repository. `publish.yml` names `environment: pypi`, and
  GitHub creates an environment implicitly the first time a job references one, so
  this is not a hard failure — but it will be created bare. Required reviewers, the
  protection rule that would pause the publish job, **cannot be enabled at all**
  while the repo is private on the Free plan. That is not blocking: the two-step
  build-then-publish flow gives the same inspect-before-ship shape without a pause.
  The gate becomes available if the repo goes public.
- **Action versions** in the YAML were current on 2026-08-17 and should be checked
  before the first real release.
- **`build.yml` has run once; `publish.yml` has never run.** Linux-scope build run
  [`32527717046`](https://github.com/furechan/bartons/actions/runs/32527717046)
  succeeded on 2026-08-21 at commit `0d6c28f`, producing the Linux x86_64 and
  aarch64 wheels plus the sdist. The full cross-platform matrix remains untested,
  and no artifact from these workflows has been published.

## Why public would help

Every remaining rough edge is softer, or gone, on a public repository:

- **Runner minutes become free.** Standard runners are unmetered on public repos,
  so the multipliers stop mattering and the full six-target matrix costs nothing.
  Today a full matrix is billed against the 2,000-minute monthly Free allowance.
- **The approval gate becomes available.** Environment protection rules — required
  reviewers pausing the publish job — are public-repo-only on Free. That is the one
  piece of the design that cannot be exercised at all while the repo is private.
- **Artifact storage becomes free**, which removes the retention/quota tension and
  the reason `retention-days` is capped at 30.
- **Little is actually hidden today.** The published sdist on PyPI already contains
  every `.rs` and `.py` source file, so the private repo protects the docs, tests,
  tooling and commit history rather than the code.

## Next steps

**None of this is scheduled.** Per the standing decision above, the trigger for
picking it up is the repository going public — everything below is deferred until
then, recorded so the thread can be resumed without re-deriving it.

1. **Measure the steady-state cost.** Dispatch `build.yml` a second time, unchanged,
   on the same commit:

   ```sh
   gh workflow run build.yml -f scope=linux
   ```

   The first run reported `Cache hits: 0` but wrote 360 objects to the GitHub
   Actions cache (`ghac`) with zero errors, so its ~14-minute jobs are a cold-start
   cost. A second run is the first chance to see what a build normally costs. If the
   wheel jobs drop to a few minutes, sccache works — and the `sdist` job, which has
   no caching at all, becomes the sole long pole and would want the same treatment.
   If they do not, the cache is being written but not restored, and the fix is an
   explicit `actions/cache` or `Swatinem/rust-cache` step.

2. **Register a PyPI trusted publisher** naming owner/repo, workflow
   `publish.yml`, environment `pypi` — none exists at present (see above).

3. **Run `publish.yml` in dry-run mode** against a real `build.yml` run, to exercise
   the resolution and every guard without uploading anything.

4. **Refresh the action versions**, current as of 2026-08-17.

5. **Only then** decide whether CI owns publishing. It cannot share that job with
   `uv run inv publish`.

## First run

```sh
gh workflow run build.yml -f scope=linux      # cheapest end-to-end check
gh run watch <run-id>
gh run download <run-id> --dir /tmp/check
gh workflow run publish.yml                   # dry run: resolves, reports, publishes nothing
```

The dry run is safe to repeat. Only `-f dry_run=false` uploads.
