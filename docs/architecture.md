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

Recognized standalone indicators may still warrant fused kernels even when
their formulas can be expressed from existing primitives. DEMA, TEMA, HMA, and ZLEMA
are the shipped examples: they are part of the conventional moving-average
vocabulary, and fusion avoids intermediate series and repeated plugin
boundaries. Incidental combinations such as MACD remain expression graphs.

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
merely together. ATR's true range does — it reaches back to the previous close —
so `TrangeFilter` takes three columns and its `Hlc` row type selects the typed
three-source `run_filter` path. Typical price does not.

Keeping the reduction in one place also keeps it defined once. `CCI` and `MFI`
supply `TYPPRICE()` as their default `src`; nothing restates the formula. MFI's
kernel then combines that reduced source with volume over time.

These factories are grouped in one `price.py` rather than a file each — the
one-file-per-indicator rule tracks kernels, and they have none. They stay
re-exported flat from `indicators/__init__.py`, so there is still exactly one
import path.

## Output names

Polars names a plugin or arithmetic expression after its leftmost input column,
so an undecorated factory would return a column called `close` or `high` —
overwriting the column it read, and colliding with any sibling reading the same
source. The `_named` step inside `wrap_indicator` and `wrap_src_indicator`
aliases each result with the factory's own lowercased name.

This lives at the expression layer, not in Rust. The kernels do name their
output — `run_filter` takes a name and `kernels.ema` returns a series called
`ema` — but the expression engine discards it, so naming there would not reach
the surface that needs it, and would cover only the kernel-backed factories.
`MACD` and the price transforms have no kernel to take a name from. An output
name is a presentation concern of the indicator layer.

The name is the bare factory name, matching the kernels and bearta, so
`EMA(20)` and `EMA(50)` still collide and still want an explicit `.alias`. An
outer alias always wins. An `ExprBundle` is left alone: its members carry their
own names and the bundle has none of its own.

The two names are therefore independent strings — a literal in the Rust driver
call, and the Python factory's `__name__` — for the kernel-backed indicators,
which have both. Neither side can see the other, so
`test_kernel_and_expression_names_agree` pins them together.

## Rust layout

Each indicator kernel lives in `bartons/src/kernels/<name>.rs` and is declared
in `bartons/src/kernels/mod.rs`. The shared `Filter`, `FilterInput` and
`FilterOutput` traits, the typed `run_filter` driver, and the `check_len!`
length guard live in `bartons/src/utils.rs`.
`bartons/src/lib.rs` is the `#[pymodule]` glue that registers each eager
pyfunction flat as `bartons.kernels.<name>`.

`Filter` carries associated `Input` and `Output` types. The input is
`Option<f64>` for single-series kernels, a pair for SAR and MFI, and a triple for
TRANGE/ATR. The arity-generic tuples are re-aliased as `kernels::Hl` and
`kernels::Hlc` so the kernels name their domain inputs. `FilterInput` maps
each row type to its exact Polars source signature, casted storage and traversal.
STREAK exercises the non-float path: `Option<bool>` from a Boolean series and
`i64` into an Int64 output builder. A filter needing another source shape adds
only that concrete row type and `FilterInput` implementation; `run_filter`
itself is already independent of source arity and dtype.

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
