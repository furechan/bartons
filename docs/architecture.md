# Architecture

Bartons consists of one Rust crate and one Python package:

- `bartons/` — PyO3 `cdylib` crate, compiled to
  `python/bartons/kernels.abi3.so`
- `python/bartons/` — Python package wrapping the compiled plugin

The crate directory is named after the Cargo package (`bartons`), which is what
a Rust reader expects to find. Its `[lib] name = "kernels"` makes the compiled
module `bartons.kernels`.

## Kernels and indicators

The two layers are not mirrors. Rust holds *kernels*: materialized vector
computations, series in and series out, used where Polars cannot express the
logic or would be materially slower. Python holds *indicators*: expression
factories that compose on top.

The sets may sometimes coincide, but that is incidental. A composite such as
BBANDS (`SMA ± k·std`) belongs in Python and needs no Rust counterpart; `MACD`
and the `price` transforms are the shipped cases. The directories are named for these roles
(`bartons/src/kernels/` and `python/bartons/indicators/`) so their divergence
reads as intended rather than as drift.

### Elementwise reductions stay out of Rust

An indicator that reduces several columns elementwise — the price transforms in
`indicators/price.py`, such as `TYPPRICE`'s `(high + low + close) / 3` — gets
no kernel, and any kernel consuming it takes the reduced series. Polars already
computes the reduction vectorized on both surfaces: as an expression on the
lazy path, and as `Series` arithmetic on the eager one, so `kernels.cci((high +
low + close) / 3)` is the eager form. Adding a kernel would buy nothing and
cost the plugin boundary, where `.over()` partitions every input column per
group — a ternary CCI measured 0.51x there.

The test is whether the step needs the bar's values *together over time*, not
merely together. ATR's true range does — it reaches back to the previous
close — so `TrangeFilter` takes three columns and `run_ternary` exists for it.
Typical price does not.

Keeping the reduction in one place also keeps it defined once. `CCI` supplies
`TYPPRICE()` as its default `src`; nothing restates the formula.

These factories are grouped in one `price.py` rather than a file each — the
one-file-per-indicator rule tracks kernels, and they have none. They stay
re-exported flat from `indicators/__init__.py`, so there is still exactly one
import path.

## Rust layout

Each indicator kernel lives in `bartons/src/kernels/<name>.rs` and is declared
in `bartons/src/kernels/mod.rs`. The shared `Filter` trait, the
`run_unary`/`run_ternary` drivers, and the `check_len!` length guard live in
`bartons/src/utils.rs`. `bartons/src/lib.rs` is the `#[pymodule]` glue that
registers each eager pyfunction flat as `bartons.kernels.<name>`.

`Filter` carries an associated `Input`: `Option<f64>` for single-series kernels
and a three-tuple for TRANGE/ATR. The tuple is spelled `utils::Triple` on the
arity-generic driver side and re-aliased as `kernels::Hlc` on the kernel side.

The flat native-module layout is deliberate. A `kernels.indicators` submodule
was built and rejected because `import bartons.kernels.indicators` requires a
manual `sys.modules` workaround that is not worth its cost.

## Python layout

The Python package and distribution are both named `bartons`; the Rust module
is imported as `bartons.kernels`. The project name avoids colliding with the
separate `bearta` technical-analysis library. Polars expressions are registered
through `polars.plugins.register_plugin_function`.

For the end-to-end contribution path, see
[Adding an indicator](adding-an-indicator.md).
