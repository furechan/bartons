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
[../../bartons/src/utils.rs](../../bartons/src/utils.rs) buys its readability and code
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

**The mechanism was subsequently isolated to a missing inline annotation.**
`ChunkedBuilder::append_option` is a default trait method without `#[inline]`,
while `append_value`, `append_null`, and the underlying Arrow `push` method are
all explicitly inline. Rebuilding the same Polars 0.55.2 dependency tree with
only `#[inline]` added to `append_option` changed the result as follows:

| Variant | Unmodified Polars | Patched Polars |
|---------|-------------------|----------------|
| manual `match` | 344.5µs | 354.4µs |
| `append_option` | 544.5µs | 354.1µs |

Both variants were run twice in alternating order over 200 runs. With the
annotation, `append_option` became indistinguishable from the manual builder;
the Cargo registry source was restored immediately after the experiment.
Current Polars `main` still lacks the annotation as of 2026-08-29. This proves
the cause of the `append_option` result, but not necessarily the separate
`.collect()` result, whose nullable array construction takes a different path.

The `.collect()` path was tested separately. Explicitly selecting Polars'
`collect_ca_trusted()` path produced 567.7µs versus 566.9µs for ordinary
`.collect()`, so the non-trusted capacity check is not material. Adding
`#[inline]` only to nullable `PrimitiveArray::arr_from_iter` and rebuilding the
full dependency tree in a fresh target directory likewise produced 565.1µs
versus a 354.5µs manual builder. Thus the `.collect()` gap is **not** another
missing-inline issue. It lies within the collector's direct `Vec` plus
`BitmapBuilder` construction strategy or the optimizer behavior induced by
that strategy; those were not separated by this experiment.

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

The source is [../../benchmarks/builder-vs-collect.rs](../../benchmarks/builder-vs-collect.rs),
with the recipe in its header comment: a `cargo new` throwaway crate, `cargo add
polars`, copy the file to `src/main.rs`, `cargo run --release`. About a minute,
almost all of it compiling polars.

It can now be moved into a `cargo` example inside `bartons/` if useful: the
crate also emits an `rlib`. Native examples, tests and benchmarks must use
`--no-default-features`, which disables pyo3's default `extension-module` mode
and links libpython. The standalone script remains convenient for reproducing
the recorded experiment without changing the production crate.

Match the polars version to the pin in [../../bartons/Cargo.toml](../../bartons/Cargo.toml)
when re-running, or the numbers describe a version the crate does not use.
