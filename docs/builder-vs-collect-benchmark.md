# EMA kernel micro-benchmark: abstraction cost vs output-construction cost

**Date:** 2026-08-17
**N:** 100,000 values, one leading null (forces the nullable path)
**Period:** 20
**Runs:** 200 per variant
**Platform:** Linux aarch64 (OrbStack VM), rustc 1.96.1, `opt-level = 3`
**polars-rs:** 0.55.2 (resolved from the `0.55.1` pin), default features + `dtype-struct`

Two independent choices go into a kernel: whether the per-element logic is
inlined into the loop or lives in a struct method, and how the output is
appended. This measures them as a 2x2 rather than a diagonal, because measuring
only the diagonal conflates them — which is exactly what the earlier run did
(see *History* below).

## Results

| Variant       | per-element logic | append          | min     | mean    |
|---------------|-------------------|-----------------|---------|---------|
| `builder`     | inline            | manual `match`  | 355µs   | 373µs   |
| `filter_mat`  | `Ema::next`       | manual `match`  | 355µs   | 405µs   |
| `builder_opt` | inline            | `append_option` | 559µs   | 629µs   |
| `filter`      | `Ema::next`       | `append_option` | 560µs   | 584µs   |
| `collect`     | inline            | `.collect()`    | 566µs   | 581µs   |

All five produce bit-identical output; the program asserts this before timing.
Figures are the `min` over 200 runs, stable to ~3% across repeats and
**independent of benchmark order** (checked by running the variants in several
permutations — the gap is not a warmup artifact).

## Reading

**The streaming-filter abstraction is free.** `filter_mat` (355µs) and `builder`
(355µs) are indistinguishable. Moving the per-element logic out of the loop into
an `#[inline] fn next(&mut self, Option<f64>) -> Option<f64>` costs nothing
measurable — the compiler flattens it completely. This is the load-bearing
result for the crate: the `Filter` trait plus `run_unary`/`run_ternary` in
[../bartons/src/utils.rs](../bartons/src/utils.rs) buys its readability and code
reuse at no runtime price.

**`append_option` costs ~1.6×, and it is the only thing that does.** It is the
sole difference between 355µs and 559µs, on *both* rows of the 2x2. A hand-rolled

```rust
match filter.next(opt_val) {
    Some(v) => builder.append_value(v),
    None => builder.append_null(),
}
```

is 1.6× faster than the `builder.append_option(filter.next(opt_val))` it appears
to be shorthand for. Both drivers already do this — the shape is deliberate, so
**do not "simplify" it to `append_option`**. That is the trap this document
exists to record; it is the kind of edit that looks like a tidy-up and silently
costs a third of the runtime.

**`.collect()` (566µs) is not a way out.** It lands with the `append_option`
group, so there is nothing to gain by restructuring the drivers around it.

No mechanism is established here for *why* `append_option` is slower — plausibly
the validity bitmap is updated per element rather than in the runs that
`append_value`/`append_null` permit, but that is a guess and was not verified.
The measurement is solid; the explanation is not.

## History

An earlier run of this benchmark lived in `evcxr/builder-vs-collect.ipynb`, on
the evcxr Rust Jupyter kernel — polars-rs 0.54.4, `:opt 2`, macOS. It recorded:

| Variant   | min     | mean    |
|-----------|---------|---------|
| `builder` | 231µs   | 235µs   |
| `collect` | 205µs   | 432µs   |
| `filter`  | 266µs   | 305µs   |

That run had no 2x2: its `filter` used `append_option` while its `builder` used
a manual `match`, so the 15% gap it showed was read as the cost of the
abstraction when it was in fact the cost of the append. The conclusion drawn
then — that the abstraction is near-free — was right, but for the wrong reason,
and it understated the `append_option` penalty by a wide margin. Its `collect`
figure also does not reproduce: fastest there, slowest here. Confounds are
stacked (different polars version, opt level, machine and kernel), so nothing
useful can be attributed to any one of them; the older numbers are kept only to
document why the reading changed.

The notebooks were removed in favour of the standalone program below — see the
CHANGELOG entry for 0.1.0.

## Reproduction

The source is [../scripts/builder-vs-collect.rs](../scripts/builder-vs-collect.rs),
with the recipe in its header comment: a `cargo new` throwaway crate, `cargo add
polars`, copy the file to `src/main.rs`, `cargo run --release`. About a minute,
almost all of it compiling polars.

It cannot be a `cargo` example inside `bartons/`, which would otherwise be the
obvious home. `polars-utils` depends on `numpy`, which depends on `pyo3`, and
the crate enables pyo3's `extension-module` — so the dependency graph is built
without linking libpython and *no* example, test or bin target in that package
can link. Adding a second in-tree crate just to host a benchmark was judged not
worth the second polars pin to keep in step.

Match the polars version to the pin in [../bartons/Cargo.toml](../bartons/Cargo.toml)
when re-running, or the numbers describe a version the crate does not use.
