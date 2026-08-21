
# The two recipes below mirror maturin's own verbs, so `just <verb>` and
# `maturin <verb>` mean the same thing: `develop` installs into the active .venv,
# `build` produces artifacts on disk and installs nothing.

# Install (optimized) into the active .venv. Matches what uv/pip produce, so the
# installed plugin is never accidentally a slow debug build. This is the one you
# want for day-to-day work — tests, benchmarks and stubs all depend on it.
develop:
    maturin develop --release

# Fast unoptimized install for quick iteration — NOT for benchmarking (~20x slower).
develop-debug:
    maturin develop

# Build the distributable artifacts — wheel + sdist — into dist/. Installs
# nothing: this is what you hand to another machine. dist/ is wiped first, since a
# stale wheel from an earlier version is indistinguishable from a fresh one to any
# `dist/*` glob.
#
# Build as often as you like; the version in pyproject.toml already names the next
# release, so nothing needs editing first.
# Pass `full` to include a cross-compiled Linux AMD64 wheel alongside the native
# wheel and sdist: `just build full`.
build mode="":
    #!/usr/bin/env bash
    set -euo pipefail
    mode={{quote(mode)}}
    case "$mode" in
        ""|full) ;;
        *)
            echo "unknown build option: $mode (supported: full)" >&2
            exit 2
            ;;
    esac
    rm -rf dist
    uv run maturin build --release --sdist --out dist
    if [[ "$mode" == full ]]; then
        rustup target add x86_64-unknown-linux-gnu
        uv run --with 'maturin[zig]' maturin build --release \
            --target x86_64-unknown-linux-gnu --zig \
            --compatibility manylinux2014 --out dist
    fi
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
    just build full
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
    [[ ${#wheels[@]} -eq 2 && ${#sdists[@]} -eq 1 ]] || {
        echo "expected two wheels and one sdist from: just preflight" >&2
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
    cargo test --manifest-path bartons/Cargo.toml --no-default-features
    pytest

# Build optimized, then run a benchmark against one baseline, e.g. `just bench`
# or `just bench vs-talib`. Baselines: vs-native (polars built-ins, no extra deps
# — hence the default), vs-talib (needs polars_talib + libta-lib), vs-mintalib.
bench baseline="vs-native": develop
    python scripts/benchmark-{{baseline}}.py

# Test the newest polars-py and, only if it passes, raise the ceiling in
# pyproject.toml. The ceiling records what the compat matrix has verified, so this
# is how it stays current. Changes nothing on failure; never commits.
raise-ceiling:
    python scripts/raise-ceiling.py

# Regenerate python/bartons/kernels.pyi by introspecting the built extension.
# Depends on `develop` so the module being introspected is current.
stubs: develop
    python scripts/generate-stubs.py

clean:
    find bartons -type d -name target -print -exec rm -rf {} +
    find python -type f -name "*.so" -print -delete
    touch pyproject.toml
