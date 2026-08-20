
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

# Upload the wheel + sdist to PyPI. Guarded: refuses a version already published,
# which is the "forgot to bump" mistake and is unrecoverable — PyPI never permits
# reusing a version or filename, even after deletion.
#
# Credentials come from MATURIN_PYPI_TOKEN, which .envrc supplies by importing the
# `pypi` sops bundle — so an active direnv in this directory is all that is needed,
# and no token is ever at rest in the repo.
#
# The release ritual is deliberately linear: preflight the committed source,
# build once, test and inspect those exact files, upload them, verify their PyPI
# hashes, then bump. Commit and push the bump after this recipe succeeds.
publish:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run python scripts/check-release-version.py
    just build full
    BARTONS_RELEASE=1 uv run nox
    BARTONS_RELEASE=1 uv run nox -s wheel_smoke
    uv run --with twine twine check dist/*
    sha256sum dist/*
    read -r -p "Upload these exact artifacts to PyPI? [y/N] " answer
    [[ "$answer" == y || "$answer" == Y ]] || { echo "publish cancelled"; exit 1; }
    uv run maturin upload --non-interactive dist/*
    uv run python scripts/check-release-version.py --verify dist/*
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
