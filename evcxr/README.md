# evcxr Rust notebooks

The notebooks in this folder run on the [evcxr](https://github.com/evcxr/evcxr) Rust Jupyter kernel (kernel name `rust`). They use `:dep` directives to pull crates at runtime.

## Setup

Run the install script. It installs the kernel at the system/user level and deliberately ignores any active project virtualenv. Requires a Rust toolchain (`cargo`) and a C compiler.

```sh
./scripts/install-evcxr.sh
```

The script performs two steps:

1. `cargo install evcxr_jupyter` — builds the kernel binary into `~/.cargo/bin` (compiles, takes a few minutes).
2. `evcxr_jupyter --install` — registers the `rust` kernelspec in your user-level Jupyter data dir.

Both land at the user level (available to any Jupyter on the machine), not inside a `.venv`. The script strips an active virtualenv from `PATH` first to guarantee this.

Verify the kernel is registered:

```sh
jupyter kernelspec list   # should list "rust"
```

## Notes

- The `:dep` directives are fetched and compiled on the first run of each cell, so the first execution in a fresh session is slow.
- An optional init file at `~/.config/evcxr/init.evcxr` (Linux) can hold default `:dep` lines so they don't need repeating per notebook.
