# Release Workflow

Bartons uses a tag-driven PyPI release workflow. Artifact construction is separate from publication, the default branch carries the next development version, and the first push provides a failure boundary before development advances.

## Version lifecycle

After publishing `0.1.7`, `main` carries `0.1.8.dev0`. A release produces two commits and two pushes:

```text
A  Release version 0.1.7             <- tag v0.1.7, first push
B  Start development of 0.1.8.dev0   <- main, second push
```

The first push updates `main` to commit A and pushes the tag. The tag triggers publication CI. If this push fails, the local task stops before creating commit B. After it succeeds, the task creates commit B and pushes `main` again. CI checks out the tagged release commit A rather than the later development commit.

## Local release task

Run `uv run inv release` from `main`. The task requires a three-part `.dev0` version, runs the complete default Nox matrix, changes the version to its plain release form with `uv version --no-sync`, commits it, creates an annotated version tag, and pushes `main` and the tag together. It then advances to the following patch's `.dev0`, commits, and pushes `main` separately.

Git handles duplicate tags and rejected pushes. The release workflow validates the tag and PyPI state. Changelog management remains independent of the release task.

## Build workflow

`.github/workflows/build.yml` supports both `workflow_call` and `workflow_dispatch`. It creates and smoke-tests five `cp311-abi3` wheels and one source distribution, uploads each result as a workflow artifact, downloads the complete set in a verification job, and checks the expected counts.

An independently dispatched build is only a confidence check. A release calls Build again from the tagged commit so the published artifacts come from the exact immutable source revision being released.

## Release workflow

`.github/workflows/release.yml` runs on pushed `v*` tags. It verifies that the tag equals `v` plus the plain three-part version in `pyproject.toml` and that the release is absent from PyPI, calls the reusable Build workflow, then publishes its verified artifacts with `uv publish` through PyPI Trusted Publishing.

Only the publish job receives `id-token: write`. The `pypi` environment remains part of the trusted-publisher identity; publication pauses only if that GitHub environment has a protection rule.
