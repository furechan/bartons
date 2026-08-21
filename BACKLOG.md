# Backlog

Items decided or considered but not scheduled. Add new items at the end.

## Rust


## Tooling

- Tag release commits. Nothing in git currently marks which commit a published version came from, since the version carries no `.dev` marker and no tag is cut. Revisit alongside the mintalib/mplchart publish-path review rather than diverging here first.
- Reviving the archived CI workflows (`archive/github-workflow.zip`) requires rewriting their version ritual before use. They were written against a `.devN` scheme — `release.yml`'s header documents "drop the `.dev0` suffix" and its `guard` job rejects any version containing `.dev`, and the archive README's "Version policy" bullet says the same. That policy was dropped before 0.1.0 (see CHANGELOG): the in-repo version is now a plain `X.Y.Z` naming the next release, so the tree is publishable at all times. Decided 2026-08-21 to keep stable-only rather than restore `.devN`, because the PyPI-availability check makes re-publishing an existing version structurally impossible, which is the protection `.devN` was buying — at two version edits per release instead of one. On revival: rewrite the header ritual, drop the `.dev`/`+` rejection from `guard` (matching its removal from `just release-guard`), and add the `curl -o /dev/null -w '%{http_code}' https://pypi.org/pypi/bartons/$version/json` 404 check so local and CI guards agree on the same remote-state test. The archive zip is deliberately left unedited — it is a record of what was built on 2026-08-17, not a template. One caveat to re-decide if the repo goes public: the CHANGELOG's stated reason for dropping `.devN` ends "not worth it when the only consumers are two machines the author controls", which no longer holds, and on a public repo `pip install git+https://github.com/furechan/bartons` would yield a build claiming a version it is not.
