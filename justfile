
build:
    maturin develop

dump:
    tar -ztvf  target/wheels/*.tar.gz  

test:
    pytest

clean:
    find bearta_plugin -type d -name target -print -exec rm -rf {} +
    find python -type f -name "*.so" -print -delete
    touch pyproject.toml
