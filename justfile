
# Build (optimized) and install into the active .venv. Matches what uv/pip
# produce, so the installed plugin is never accidentally a slow debug build.
build:
    maturin develop --release

# Fast unoptimized build for quick iteration — NOT for benchmarking (~20x slower).
build-debug:
    maturin develop

dump:
    tar -ztvf  target/wheels/*.tar.gz

test:
    pytest

# Build optimized, then run a benchmark against one baseline, e.g. `just bench`
# or `just bench vs-talib`. Baselines: vs-native (polars built-ins, no extra deps
# — hence the default), vs-talib (needs polars_talib + libta-lib), vs-mintalib.
bench baseline="vs-native": build
    python scripts/benchmark-{{baseline}}.py

# Regenerate python/bartons/plugin.pyi by introspecting the built extension.
# Depends on `build` so the module being introspected is current.
stubs: build
    python scripts/generate-stubs.py

clean:
    find bartons -type d -name target -print -exec rm -rf {} +
    find python -type f -name "*.so" -print -delete
    touch pyproject.toml
