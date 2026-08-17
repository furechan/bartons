
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
build:
    rm -rf dist
    maturin build --release --sdist --out dist
    @ls -l dist

# Inspect what actually went into the sdist.
dump:
    tar -ztvf dist/*.tar.gz

# Upload the wheel + sdist to PyPI. Guarded: refuses a version already published,
# which is the "forgot to bump" mistake and is unrecoverable — PyPI never permits
# reusing a version or filename, even after deletion.
#
# Credentials come from MATURIN_PYPI_TOKEN (or ~/.pypirc). Keep the token in a
# credential bundle rather than plaintext, per the fleet's env contract:
#   envs exec pypi -- just publish
#
# The release ritual:
#   just publish          # builds fresh, then uploads
#   git commit -am "Release 0.1.0" && git push
#   just bump && git commit -am "Bump version" && git push
publish: build
    python scripts/check-release-version.py
    maturin upload dist/*

# Bump the patch version in pyproject.toml, so the repo names the next release
# again. Run right after publishing, not before.
bump:
    python scripts/bump-version.py

test:
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

# Regenerate python/bartons/plugin.pyi by introspecting the built extension.
# Depends on `develop` so the module being introspected is current.
stubs: develop
    python scripts/generate-stubs.py

clean:
    find bartons -type d -name target -print -exec rm -rf {} +
    find python -type f -name "*.so" -print -delete
    touch pyproject.toml
