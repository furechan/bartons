
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

# Build optimized, then run a benchmark, e.g. `just bench` (ema) or `just bench sma`.
bench indicator="ema": build
    python scripts/benchmark-{{indicator}}.py

clean:
    find bartons -type d -name target -print -exec rm -rf {} +
    find python -type f -name "*.so" -print -delete
    touch pyproject.toml
