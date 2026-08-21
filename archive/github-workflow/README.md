# Archived: GitHub Actions release automation

Built 2026-08-17, archived the same day, unused. Kept because the analysis behind
it is worth more than the YAML, and because reviving it is a matter of unzipping
into `.github/` if the project ever has consumers beyond the two machines it was
written for.

## What this was

A complete PyPI release pipeline for `bartons`:

- **`wheels.yml`** — builds five `cp311-abi3` wheels (linux x86_64/aarch64, macOS
  arm64/x86_64, Windows x64) plus the sdist. A `setup` job emits the matrix as
  JSON so the target list can be scoped at dispatch time.
- **`release.yml`** — on a `v*` tag: verify the tag against the version, build
  everything through `wheels.yml`, publish to PyPI over OIDC.
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

That number is why the final version had no `push` trigger at all: a README fix
landing on `main` would otherwise have cost ~200 billed minutes. Pull requests
built linux only, and only when packaging or compiled code changed; the full
matrix ran on a release tag or an explicit manual dispatch.

**Wheels must be built in one run, not accumulated.** GitHub artifacts are scoped
to their run, so assembling a release from several earlier runs means pulling
artifacts by run ID — and nothing then guarantees they came from the same commit.
Wheels from different runs can carry identical version numbers and different code.
Building everything inside the tag's own run rules that out by construction, at
the cost of rebuilding artifacts you may have just built by hand.

**The approval gate is what makes that acceptable.** `environment: pypi` with
required reviewers pauses the publish job after the build. The artifacts are
already uploaded and downloadable (`gh run download <id>`), so the sequence is
build once → inspect the real artifacts → approve → publish exactly those bits.
That is the local build-check-publish flow, with better provenance. The
environment was declared in `release.yml`; enabling required reviewers on it was a
repository setting, never turned on.

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
cp archive/github-workflow/release.yml archive/github-workflow/wheels.yml .github/workflows/
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
