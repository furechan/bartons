# GitHub Actions workflows

## Status

**Active. Dispatch-only. The release mechanism.**

| | |
|---|---|
| Releases today | built, confirmed and published by `release.yml` — see [CLAUDE.md](../CLAUDE.md) |
| This workflow | active and dispatch-only; nothing runs implicitly on a push, PR or tag |
| Repository | public, GitHub Free |
| Server-side config | GitHub confirmation configured; PyPI trusted publisher must be changed to `release.yml` |
| First publication | `0.1.3` on 2026-08-25; five wheels uploaded, sdist rejected for a missing declared license file |

CI became the sole release path on 2026-08-25. The separate `build.yml` and
`publish.yml` workflows were consolidated into `release.yml` on 2026-08-26. The local publisher must not upload
a version also handled by CI: PyPI never frees a filename, and the two paths cannot
safely share ownership of one release.

It is **dispatch-only** — nothing runs on a push, a pull request, a tag or a
schedule — and publication waits for approval on the protected `pypi` environment.

Built 2026-08-17, archived unused the same day, then reworked and installed for
experimentation on 2026-08-21. The first full matrix and trusted-publishing run
completed on 2026-08-25; the results and recovery notes below supersede the old
prototype status.

## What this is

A PyPI release pipeline for `bartons`: **`release.yml`** builds five
`cp311-abi3` wheels (Linux x86_64/aarch64, macOS arm64/x86_64, Windows x64) in
one complete matrix, alongside one sdist job. Every job installs and smoke-tests
its own artifact. Once all six builds succeed, the protected `pypi` environment
asks for confirmation; the publish job then downloads, counts and uploads those
exact six artifacts over OIDC.
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

Earlier versions ran Linux-only and full builds as separate jobs and later split
building from publishing across `build.yml` and `publish.yml`. Those designs are
retired. `release.yml` has one dispatch mode and one complete wheel matrix:
asking for a release always means building every wheel and the sdist.

`workflow_dispatch` is resolved from the **default branch**, so a change to the
workflow cannot be exercised before it lands. This is the deliberate cost of
having no automatic push or pull-request trigger.

**Wheels must not be accumulated across runs without proving provenance.** GitHub
artifacts are scoped to their run, so assembling a release from an earlier run
means pulling artifacts by run ID — and by itself nothing then guarantees they
came from the commit being released. Wheels from different runs can carry
identical version numbers and different code.

The current design rules that out structurally: all artifacts are uploaded by
the wheel matrix and sdist job in one run, and the publish job downloads
artifacts from that same run only after every build succeeds. The approval pause
does not start another run or rebuild anything, so the files tested are the files
published.

**On the approval gate.** `environment: pypi` with required reviewers pauses the
publish job after the matrix succeeds and before GitHub grants the job access or
OIDC credentials. It is declared in `release.yml`; the environment requires
confirmation from `furechan` and permits self-review.

Artifacts use GitHub's repository-default retention. They normally survive only
the build-to-approval interval, and a canceled release run is never reused as the
source for a later publication.

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

- PyPI trusted publishing still names the retired `publish.yml` workflow. Change
  it to owner `furechan`, repository `bartons`, workflow `release.yml`, and
  environment `pypi` before dispatching a release.
- GitHub's `pypi` environment requires approval from `furechan`, with self-review
  allowed, so the workflow pauses for confirmation after the build matrix.
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
- **Artifact storage becomes free**, which removes the former retention/quota
  tension.
- **Little is actually hidden today.** The published sdist on PyPI already contains
  every `.rs` and `.py` source file; making the repository public additionally
  exposes its docs, tests, tooling and commit history.

## Release commands

```sh
gh workflow run release.yml
gh run watch <run-id>
```

After the six build jobs succeed, approve the `pypi` environment deployment in
GitHub. Approval resumes the same run and publishes its artifacts.
