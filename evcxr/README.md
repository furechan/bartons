# evcxr Rust notebooks

The notebooks in this folder run on the [evcxr](https://github.com/evcxr/evcxr) Rust Jupyter kernel (kernel name `rust`).

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

## Dependencies: versionless `:dep` cells

Each notebook declares its own crates in a `:dep` cell, without versions:

```
:dep polars
:dep itertools
:dep serde
```

A bare `:dep` resolves to whatever is newest on crates.io — it does **not** track `bartons/Cargo.toml`. That is deliberate. These notebooks compare patterns and methods, where the crate version is rarely the variable; when it is, pin that one line for that experiment. The alternative, pinning everything, is what silently rotted last time: the notebooks sat on polars 0.54.4 long after the crate moved to 0.55.1, and nothing said so.

**Use the same `:dep` block in every notebook that needs one.** The build cache is keyed on the *complete* dependency set, not per crate, so `{polars}` and `{polars, itertools}` are different keys and each pays its own full build. Declaring `polars`, `itertools` and `serde` everywhere costs nothing — polars pulls the other two transitively anyway — and means all of them share a single cached build.

## Startup cost

polars is expensive to compile, and there is no way around it:

| | time |
|---|---|
| first use of a given dependency set | ~80s |
| every use after that | ~2s |
| a set that differs by one crate | ~80s again |

The cache doing that work is `:cache`, set in `~/.config/evcxr/init.evcxr` — machine-level configuration, managed in the dotfiles repo rather than here, along with `:opt 3` for release-comparable timings. Without it every session rebuilds from scratch. Notebooks still work without it; they are just slow.

**Do not add an `evcxr.toml`.** It looks like the tidier home for a shared dependency block and is a trap: it shadows `init.evcxr` completely — settings and `:dep` lines alike — and its schema has no cache key, so it silently disables `:cache`. It also moves the build from first-cell-execution to *kernel startup*, which then exceeds VS Code's 60s launch timeout and fails as "Failed to start the Kernel" with cargo output and no mention of configuration. Measured alternatives, none of which recover it: `sccache = "sccache"` in the toml is engaged but buys ~8%, and `EVCXR_CACHE_ENABLED` is an internal marker that does nothing when set.

## Notes

- A cell-level `let` needs an explicit type annotation; evcxr persists variables across cells and cannot always infer them. Wrapping work in a `fn` avoids this entirely.
- Notebooks are for exploration. Conclusions worth keeping go in `docs/` with their provenance — date, platform, and the resolved crate versions — because a notebook's stored outputs carry none of that and read as current long after they stop being true. See [`../docs/builder-vs-collect-benchmark.md`](../docs/builder-vs-collect-benchmark.md) for the format.
