# Handoff — release automation

Written 2026-08-17. Delete this file once the first release is out.

## Where things stand

Branch `release-automation`, commit `5782971`, pushed to `origin`. `main` is untouched.

The commit adds CI release automation and settles where the project version lives:

- `.github/workflows/wheels.yml` — five `cp311-abi3` wheels (linux x86_64/aarch64,
  macOS arm64/x86_64, Windows x64) plus the sdist. Runs on PRs and pushes to main,
  and is `workflow_call`-able.
- `.github/workflows/release.yml` — on a `v*` tag: guard, build (through
  wheels.yml), publish to PyPI over OIDC.
- `pyproject.toml` — now the single authoritative version, at `0.1.0.dev0`.
- `bartons/Cargo.toml` — version frozen at `0.0.0`, unused, commented as such.
- `CHANGELOG.md` — full rationale for both decisions under `## 0.1.0`.

## Done already (no action needed)

- PyPI trusted publisher registered: `furechan/bartons`, workflow `release.yml`,
  environment `pypi`.
- GitHub `pypi` environment created.

## Next steps, in order

1. **Merge to main.** No PR is needed: there is no `push` trigger, so merging
   builds nothing and costs nothing, and only a `v*` tag can publish.

   ```sh
   git checkout main && git merge --ff-only release-automation && git push
   ```

2. **Fire one manual `full` run.** This is the step that must not be skipped.
   macOS and Windows have never compiled this crate — only linux-aarch64 has been
   built in this repo — and pull requests build linux only, so nothing so far has
   exercised them.

   ```sh
   gh workflow run wheels.yml -f scope=full
   gh run watch
   ```

   The button only appears once `wheels.yml` is on the default branch, which is
   why this follows the merge rather than preceding it. Budget ~195 billed
   minutes for the run. Two plausible failures:
   - the polars-rs tree not compiling cleanly on macOS or Windows;
   - `macos-13` no longer being offered as a runner (GitHub has been retiring
     older macOS images). That is the intel-mac target; dropping it from the
     matrix is a fine answer if so, and it is 40% of the full matrix's cost.

3. **Cut the release** once that run is green.

   ```sh
   # drop the .dev0 suffix in pyproject.toml -> version = "0.1.0"
   git commit -am "Release 0.1.0"
   git tag -a v0.1.0 -m "0.1.0"
   git push --follow-tags
   ```

   `release.yml` fires, the guard checks the tag against `[project].version`,
   the matrix builds, and the publish job uploads over OIDC.

4. **Reopen development.** Bump `pyproject.toml` to `0.2.0.dev0`, commit, push.

5. **Yank the old PyPI releases** — `bartons` `0.0.0` and `0.0.1`, the unrelated
   stock-price skeleton that never shipped. Independent of everything above; do it
   whenever. Yank rather than delete: existing pins keep resolving, and PyPI never
   allows a deleted version or filename to be re-uploaded.

## Things to not get wrong

- **A tag publishes, PR or no PR.** `release.yml` triggers on `v*` regardless of
  whether the matrix has ever run green. Do not skip step 2 by tagging directly,
  or the first macOS/Windows build ever attempted will be the one also trying to
  publish to PyPI.
- **Bump before tagging, never after.** The tag must point at a commit whose
  `pyproject.toml` already reads the release version. The guard enforces this and
  was tested against four cases, including the realistic mistake of tagging
  `v0.2.0` while main still says `0.2.0.dev0` — rejected.
- **The polars range is frozen at upload.** `polars>=1.28,<1.44` from
  `pyproject.toml` becomes immutable `Requires-Dist` metadata on the published
  wheel. `just raise-ceiling` moving the ceiling only affects *future* releases,
  so raising it means cutting a new one. Expect releases to track polars-py.
- **`runtime-64` users are not served.** `IdxSize` is compile-time, so one `.so`
  cannot serve both polars engines, and no wheel tag can express the difference —
  pip cannot pick correctly. These wheels are runtime-32 (the default, correct for
  nearly everyone). A `bartons-bigidx` distribution is the answer if anyone asks.
  See `docs/polars-runtime-libraries.md`.
- **Version lives in one place.** `pyproject.toml`. `bartons/Cargo.toml` stays at
  `0.0.0` forever unless the crate is ever published to crates.io on its own.

## Reference numbers (measured 2026-08-17, 11-core arm64)

- Cold build from an empty `target/`: **1 m 42 s** wall, 13 m 48 s CPU, 379 crates.
  Budget 5–8 min per target on a 2–4 core CI runner; `sccache` is enabled.
- Incremental rebuild after a kernel edit: ~5 s. No-op: ~1 s.
- Fresh-machine install is roughly 1 min of download (~500 MB, mostly the rustup
  toolchain; the 378 crate tarballs are only 70 MB) plus the compile above.
- `maturin build` tags linux wheels with the host glibc (`manylinux_2_34` locally),
  which is why CI pins the `2_28` containers instead.
