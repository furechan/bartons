
# Internal optimized install used by source preparation, benchmarks and stubs.
# It is plumbing rather than a public workflow; run `just make` to prepare and
# validate the complete source tree.
_develop:
    maturin develop --release

# Make the source tree ready before artifact construction: install the current
# native extension, regenerate every checked-in derived file, and validate it.
make: _develop
    python scripts/generate-kernel-stubs.py
    python scripts/generate-indicator-stubs.py
    uv run python scripts/update-readme.py
    just test
    uv run ty check

# Build the distributable artifacts — wheel + sdist — into dist/. Installs
# nothing: this is what you hand to another machine. dist/ is wiped first, since a
# stale wheel from an earlier version is indistinguishable from a fresh one to any
# `dist/*` glob.
#
# Build as often as you like; the version in pyproject.toml already names the next
# release, so nothing needs editing first.
#
# Native wheel only. A cross-compiled Linux AMD64 wheel used to be built here with
# zig and published alongside it, and was dropped on 2026-08-21: it could not be
# imported on this ARM64 host, so two releases shipped a binary nobody had ever
# run. Every machine here is ARM64, and x86_64 users fall back to the sdist —
# which needs a Rust toolchain and a full polars build (~12 min), so this is a
# real narrowing, taken deliberately. Restore it when CI can smoke-test the
# artifact on a native AMD64 runner; see docs/github-workflow.md.
build:
    #!/usr/bin/env bash
    set -euo pipefail
    rm -rf dist
    uv run maturin build --release --sdist --out dist
    ls -l dist

# Inspect what actually went into the sdist.
dump:
    tar -ztvf dist/*.tar.gz

# Refuse to publish anything that does not correspond to a pushed commit.
#
# A wheel built from a dirty tree, or from a commit that never reached the
# remote, matches no public revision — and PyPI never permits reusing a version
# or filename, even after deletion, so that can never be corrected, only
# superseded by a new version. Those two checks are the whole point.
#
# The PyPI lookup is a third, cheaper thing: it catches a forgotten bump. It sits
# here rather than at upload time because preflight runs the entire nox matrix —
# failing in two seconds beats failing after several minutes. It fails closed:
# the test is `== 404`, so a timeout or a 5xx blocks the release too.
release-guard:
    #!/usr/bin/env bash
    set -euo pipefail
    [[ -z $(git status --porcelain) ]] || {
        echo "refusing to publish: the working tree is not clean" >&2
        exit 1
    }
    upstream=$(git rev-parse --abbrev-ref '@{upstream}' 2>/dev/null) || {
        echo "refusing to publish: no upstream branch to compare against" >&2
        exit 1
    }
    read -r behind ahead < <(git rev-list --left-right --count '@{upstream}...HEAD')
    [[ "$behind" -eq 0 && "$ahead" -eq 0 ]] || {
        echo "refusing to publish: HEAD is $ahead ahead and $behind behind $upstream" >&2
        exit 1
    }
    version=$(uv version --short)
    code=$(curl -sS -o /dev/null -w '%{http_code}' "https://pypi.org/pypi/bartons/$version/json")
    [[ "$code" == 404 ]] || {
        echo "refusing to publish bartons $version: already on PyPI (HTTP $code) — bump the version" >&2
        exit 1
    }
    echo "ok: clean, synchronized $(git branch --show-current) at $(git rev-parse --short HEAD)"
    echo "ok: bartons $version is not yet on PyPI"

# Build and validate the release artifacts, then stamp them as ready to publish.
# dist/ is cleared by the build, so a failed preflight can never leave an older
# success stamp behind. The stamp certifies only these local artifacts: publish
# checks that every upload file still predates it.
preflight:
    #!/usr/bin/env bash
    set -euo pipefail
    just release-guard
    just make
    git diff --exit-code
    just build
    BARTONS_USE_DIST=1 uv run nox
    BARTONS_USE_DIST=1 uv run nox -s wheel_smoke
    uv run --with twine twine check dist/*
    sha256sum dist/*
    touch dist/.preflight-ok
    echo "preflight passed; inspect dist/, then run: just publish"

# Upload the wheel + sdist already qualified by `just preflight`. Guarded:
# refuses a missing/stale stamp, artifacts for another version, or a version
# already published. PyPI never permits reusing a version or filename, even
# after deletion.
#
# Credentials come from MATURIN_PYPI_TOKEN, which .envrc supplies by importing the
# `pypi` sops bundle — so an active direnv in this directory is all that is needed,
# and no token is ever at rest in the repo.
#
# Publishing never compiles. It uploads the exact local artifacts qualified by
# preflight, then bumps. Commit and push the bump after this recipe succeeds.
publish:
    #!/usr/bin/env bash
    set -euo pipefail
    shopt -s nullglob
    stamp=dist/.preflight-ok
    [[ -f "$stamp" ]] || { echo "no valid preflight stamp; run: just preflight" >&2; exit 1; }
    wheels=(dist/*.whl)
    sdists=(dist/*.tar.gz)
    [[ ${#wheels[@]} -eq 1 && ${#sdists[@]} -eq 1 ]] || {
        echo "expected one wheel and one sdist from: just preflight" >&2
        exit 1
    }
    artifacts=("${wheels[@]}" "${sdists[@]}")
    version=$(uv version --short)
    for artifact in "${artifacts[@]}"; do
        [[ ! "$artifact" -nt "$stamp" ]] || {
            echo "$artifact changed after preflight; rerun: just preflight" >&2
            exit 1
        }
        filename=${artifact#dist/}
        [[ "$filename" == bartons-"$version"-*.whl || "$filename" == bartons-"$version".tar.gz ]] || {
            echo "$artifact does not belong to bartons $version; rerun: just preflight" >&2
            exit 1
        }
    done
    just release-guard
    read -r -p "Upload these exact artifacts to PyPI? [y/N] " answer
    [[ "$answer" == y || "$answer" == Y ]] || { echo "publish cancelled"; exit 1; }
    uv run maturin upload --non-interactive "${artifacts[@]}"
    just bump

# Bump the patch version in pyproject.toml, so the repo names the next release
# again, and refresh uv.lock without syncing the environment. Run right after
# publishing, not before.
bump:
    uv version --bump patch --no-sync

test:
    #!/usr/bin/env bash
    set -euo pipefail
    python_libdir=$(python -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')
    PYO3_PYTHON="$PWD/.venv/bin/python" \
    LD_LIBRARY_PATH="$python_libdir${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
        cargo test --manifest-path bartons/Cargo.toml --no-default-features
    uv run pytest

# Build optimized, then run a benchmark against one baseline, e.g. `just bench`
# or `just bench vs-talib`. Baselines: vs-native (polars built-ins, no extra deps
# — hence the default), vs-talib (needs polars_talib + libta-lib), vs-mintalib.
bench baseline="vs-native": _develop
    python benchmarks/benchmark-{{baseline}}.py

# Test the newest polars-py and, only if it passes, raise the ceiling in
# pyproject.toml. The ceiling records what the compat matrix has verified, so this
# is how it stays current. Changes nothing on failure; never commits.
raise-ceiling:
    python scripts/raise-ceiling.py

# Regenerate the README indicator catalog from the public exports.
readme:
    uv run python scripts/update-readme.py

# Regenerate the compiled-kernel stub and typed indicator re-exports.
# Depends on the internal release install so native introspection is current.
stubs: _develop
    python scripts/generate-kernel-stubs.py
    python scripts/generate-indicator-stubs.py

clean:
    find bartons -type d -name target -print -exec rm -rf {} +
    find python -type f -name "*.so" -print -delete
    touch pyproject.toml
