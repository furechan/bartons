# Backlog

Items decided or considered but not scheduled. Add new items at the end.

## Rust


## Tooling

- Tag release commits. Nothing in git currently marks which commit a published version came from, since the version carries no `.dev` marker and no tag is cut. Revisit alongside the mintalib/mplchart publish-path review rather than diverging here first.
- ~~Rewrite the archived CI workflows' `.devN` version ritual~~ — done 2026-08-21: `archive/github-workflow/` was written against a `.devN` scheme (`release.yml`'s header documented "drop the `.dev0` suffix", its `guard` job rejected any version containing `.dev`, and the README's "Version policy" bullet said the same), but that policy was dropped before 0.1.0 — the in-repo version is now a plain `X.Y.Z` naming the next release, so the tree is publishable at all times. Kept stable-only rather than restoring `.devN`, because the PyPI-availability check makes re-publishing an existing version structurally impossible, which is the protection `.devN` was buying, at two version edits per release instead of one. The CI guard checks tag/version agreement and PyPI availability; the local Invoke publish guard checks clean-tree and upstream synchronization (which CI satisfies by construction) plus PyPI availability.
- Re-decide the `.devN` question if the repo goes public. The CHANGELOG's stated reason for dropping it ends "not worth it when the only consumers are two machines the author controls", which no longer holds now that bartons is on PyPI; on a public repo `pip install git+https://github.com/furechan/bartons` would yield a build claiming a version it is not. Not decisive — anyone sane installs the wheel — but it is the one `.devN` argument that survives, and it should be decided deliberately rather than inherited.
- Reconsider the CI workflows when the repository goes public or the project becomes more prominent. Decided 2026-08-21 to keep `.github/workflows/build.yml` and `publish.yml` installed but inert, as a prototype: the local `uv run inv build` / `uv run inv publish` cycle is sufficient while the author is effectively the only consumer, and what CI adds is either free only on a public repo (unmetered runners, the approval gate, artifact storage) or only matters once there are users to protect. [docs/github-workflow.md](docs/github-workflow.md) holds the status, the cost measurements from the one exploratory run, what is still missing server-side, and the deferred next steps.
