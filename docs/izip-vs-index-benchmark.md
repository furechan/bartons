# Ternary driver: `izip!` vs indexing

**Date:** 2026-08-18
**N:** 100,000 values, one leading null in each series (forces the nullable path)
**Runs:** 200 per variant
**Platform:** Linux aarch64 (OrbStack VM), rustc 1.96.1, `cargo run --release`
**polars-rs:** 0.55.2 (resolved from the `0.55.1` pin), default features + `dtype-struct`
**itertools:** 0.14.0

The ternary driver at the time of this benchmark walked three series with
`izip!`; that traversal now lives in the float-triple `FilterInput`
implementation used by `run_filter`. This measures it against the alternatives,
with the real TRANGE recurrence as the per-element logic and the output path
held constant — manual `match` into a `PrimitiveChunkedBuilder`, never
`append_option`, which
[builder-vs-collect-benchmark.md](builder-vs-collect-benchmark.md) measures at
~1.6x.

| variant | how it reads a row |
|---|---|
| `izip` | `izip!(a.iter(), b.iter(), c.iter())` — the ternary driver at benchmark time |
| `index` | `for i in 0..len` with `ca.get(i)` |
| `unchecked` | same, with `get_unchecked` |
| `rechunk` | rechunk to one chunk, then index the values slice + validity bitmap directly; rechunk cost is inside the timed region |
| `chunked` | walk every chunk, hoisting the downcast once per chunk; no rechunk, so no temporaries |
| `iternext` | three `ChunkedArray::iter()` advanced by hand with `.next()` instead of `izip!` — isolates the zipping machinery from the per-call cost of `next` |
| `valiter` | three raw `values_iter()` slice iterators, validity read by index — isolates the `ZipValidity` wrapper. Single-chunk only |
| `fastiter` | `chunked`'s hand-rolled cursor expressed as an `Iterator` behind a `FastIter` extension trait, so it reads as `ca.fast_iter()` |
| `fast-iternext` | advances the same three `FastIter` cursors explicitly with `.next()`, isolating `izip!` while holding the custom iterator types fixed |
| `threeidx` | the hoisted loop with one index per array instead of a shared one — isolates cursor count from chunk logic. Single-chunk only |
| `ziparr` | hoists the downcast, then zips the *arrow array* iterators — the same iteration without `ChunkedArray`'s `FlatMap`-over-chunks layer. Single-chunk only, so measured at 1 chunk alone |
| `slices` | the hoisted single-chunk loop itself: three arrays indexed by one `i`, no chunk logic. Not run directly; reached through `fastpath` |
| `fastpath` | a **dispatcher**, not a loop: single-chunk inputs go to `slices`, everything else to `chunked` — **the candidate**. Its 1-chunk row is `slices`, its 8- and 64-chunk rows are `chunked` |

## Results

Minimum µs over 200 runs.

### Ternary (TRANGE)

| chunks | `izip` | `iternext` | `index` | `unchecked` | `rechunk` | `chunked` | `fastiter` | `ziparr` | `valiter` | `threeidx` | `fastpath` |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 854 | 856 | 934 | 625 | 305 | 531 | 447 | 411 | 349 | 306 | **306** |
| 8 | 722 | 726 | 1418 | 1225 | 444 | 419 | 354 | — | — | — | **354** |
| 64 | 704 | 703 | 5139 | 4885 | 450 | 413 | 347 | — | — | — | **347** |

### Unary (EMA), to locate the effect

| chunks | `iter()` | rechunk + index | `fastiter` | Arrow `iter().copied()` |
|---|---|---|---|---|
| 1 | 343 | 287 | **287** | **287** |
| 8 | 304 | 298 | **291** | — |

All variants produce bit-identical output; the program asserts this before
timing. Figures are stable across repeats and independent of benchmark order
(checked by running the variants in several permutations — at 1 chunk, reversed
order gives `rechunk` 362 against `izip` 878).

### `FastIter`: `izip!` versus explicit `.next()`

An additional control holds the three custom iterator types fixed and changes
only how they are advanced. Minimum µs over 200 runs:

| chunks | `izip!(fast_iter...)` | explicit `.next()` | `izip!` advantage |
|---|---:|---:|---:|
| 1 | 442.9 | 471.7 | 6.1% |
| 8 | 354.0 | 374.1 | 5.4% |
| 64 | 345.9 | 366.0 | 5.5% |

Unlike the Polars iterator pair, these two are not identical: `izip!` is
slightly faster. This reinforces that the macro is not the source of the slow
Polars path. Its `Zip` structure gives LLVM at least as much optimization
opportunity as spelling out the three calls manually, and a little more for
the custom cursor.

## Reading

**`izip!` beats an index loop, and the margin grows with fragmentation.**
`ChunkedArray::get(i)` degrades as chunks multiply — 8.4x worse than `izip` at 64
chunks — while `izip` stays flat. `get_unchecked` drops two `assert!`s but keeps
everything else, so it does not rescue it. An index loop is never the answer.

**But the real finding is what makes the fast variants fast, and it is not the
chunking.** `index_to_chunked_index` has an explicit single-chunk fast path, so
chunk *search* costs nothing at one chunk — yet `unchecked` (608) is still 2x
slower than a hoisted loop (305) on the same single chunk. What both `get` and
`get_unchecked` do on **every element** is re-derive the array: index `chunks[0]`,
deref the `Arc<dyn Array>`, downcast to `&PrimitiveArray<f64>`, then read value
and validity. That chain runs through `&self` with aliasing the optimizer cannot
see through, so it is never hoisted.

Do the downcast once and the per-element work becomes a validity test plus a
value read — and the hoisted arrow array yields `Option<f64>` directly via
`StaticArray::get`/`get_unchecked`, so there is no need to take `values()` and
`validity()` apart and reassemble them. Nothing is materialized either way:
`values()` returns `&Buffer<f64>` (a field borrow, `Deref<Target = [f64]>`) and
`validity()` an `Option<&Bitmap>`, both views into memory the `ChunkedArray`
already owns. Reading the `Option` directly is both shorter and ~15% faster than
splitting them (305 against 361 at one chunk).

**Rechunking is only one way to make the hoist legal, and the expensive one.**
It is what would copy `3 x n x 8` bytes — ~240MB on a 10M-row frame. Walking
chunks and hoisting per chunk gets the same win with **no copy at all**, and is
faster than rechunking on fragmented input (413 against 450 at 64 chunks)
because it never pays the concatenation.

**`fastpath` is the candidate**: 2.8x faster than today's `izip` on single-chunk
input and 2.0x on fragmented input, allocation-free at every chunking.

**Expressing the chunk cursor as a trait made it faster, not slower.** `fastiter`
is `chunked`'s hand-rolled `take!` macro rewritten as an `Iterator` behind a
`FastIter` extension trait, and it beats the macro at every chunking — 447
against 531 at one chunk, 347 against 413 at 64. Carrying a remaining-element
count gives a cheap exhaustion test and an exact `size_hint`, which the macro's
`for _ in 0..len` could not supply. So the abstraction is not merely free here,
in the way `docs/builder-vs-collect-benchmark.md` found for `Filter`; it pays.
`fastpath` therefore dispatches to `fastiter`, not to `chunked`, whenever the
input has more than one chunk. It branches
because the two regimes want different loops — the per-element cursor that makes
`chunked` general costs it 536 against 305 when there is only one chunk to walk.

**We are not out-engineering `ChunkedArray::iter()`.** It is
`downcast_iter().flat_map(|arr| arr.iter())` — structurally the same chunk walk
the fast variants do by hand. What costs is **per-element chunk-boundary
handling**, and everything else is nearly free. Each claim below is isolated by
its own variant rather than inferred, at 1 chunk:

| comparison | µs | what it isolates |
|---|---|---|
| `izip` 857 vs `iternext` 856 | ~0 | `izip!`'s machinery — free |
| `slices` 305 vs `threeidx` 305 | ~0 | one index reused for three arrays, vs one index each — free |
| `ziparr` 411 vs `valiter` 350 | 61 | the `ZipValidity` wrapper |
| `valiter` 350 vs `slices` 305 | 45 | iterator protocol vs indexing |
| `slices` 305 vs `chunked` 532 | 227 | per-element chunk-boundary logic |
| `slices` 305 vs `izip` 857 | 552 | all of it, `FlatMap` included |

Two of these were things this benchmark was originally written to assert and had
to retract. `izip!` is not the problem — advancing the same three iterators by
hand costs the same. And the number of cursors is not the problem — giving each array its own index
is exactly as fast as reusing one, because the compiler handles parallel
induction variables for free. What remains is chunk-boundary
work done per element, whether `FlatMap`'s or hand-rolled, and it dominates
everything else combined.

That is also why arrow's own iterator (411) beats the hand-rolled cursor (532):
over a single chunk it has no chunk logic at all, just a slice iterator and a
bitmap iterator. So `chunked` is not the best general shape — per-chunk arrow
iterators would be — and there is no `unsafe` iterator variant that closes the
remaining gap to indexing; `no_null_iter()` exists but drops validity entirely,
changing semantics rather than cost.

**The gap barely shows for a single series.** At one chunk, `FastIter` and the
native Arrow iterator with `.copied()` are tied at 287µs; neither warrants a
dispatcher. Both beat `ChunkedArray::iter()` by ~16%, nothing like the ternary
2.8x, which is the superlinearity above. That leaves the "streaming-filter
abstraction is free" result in
[builder-vs-collect-benchmark.md](builder-vs-collect-benchmark.md) untouched:
this gap sits below `Filter`, in how rows are gathered.

## Divergence under evcxr — unexplained

**The same source run on the evcxr Jupyter kernel reverses the `rechunk`
result.** Measured 2026-08-18, same machine, same day, polars 0.55.2, `:opt 3`:

| environment | `izip` (1 chunk) | `rechunk` (1 chunk) |
|---|---|---|
| `cargo run --release` | 883 | 371 |
| evcxr, `:opt 3` | 510 | 810 |

Both directions moved. Collapsing every notebook cell into one changed nothing
(510 against 516), so it is not cross-cell compilation preventing inlining.
The cause is unidentified; the untested candidates are evcxr's build profile
beyond `opt-level` — codegen units, LTO, `prefer-dynamic` — against cargo's
release profile.

**This does not weaken the result above.** The plugin is built by `maturin
develop --release` / `maturin build --release`, and `bartons/Cargo.toml` carries
no `[profile]` override — so cargo's release profile is exactly what compiles the
shipped `.so`, and exactly what the table above measures. evcxr disagreeing means
**evcxr is not a valid instrument for this measurement**, which is a fact about
notebooks rather than about `run_ternary`.

That is why the experiment is a cargo-built program rather than a notebook, and
why the script's header says so.

## Status

Implemented as the `FastIter` extension trait and `ChunkCursor` in
`bartons/src/utils.rs`; both drivers use it. A separate unary measurement found
the native single-chunk Arrow iterator and `FastIter` identical (286.6µs), so
`run_unary` deliberately keeps one traversal. The separately measured ternary
direct-index single-chunk dispatch remains unimplemented.

## Reproduction

The source is [../benchmarks/izip-vs-index.rs](../benchmarks/izip-vs-index.rs),
registered as a Cargo example so it can use bartons' shared `random_prices`
fixture. Run it with `cargo run --release --manifest-path bartons/Cargo.toml
--no-default-features --example izip-vs-index`.

`cargo run --release -- --out report.out` also writes the report to a file.
Trailing arguments name variants to run, in that order, which is how the
ordering check above was done.

It can now be moved into a `cargo` example inside `bartons/` if useful: the
crate also emits an `rlib`. Native examples, tests and benchmarks must use
`--no-default-features`, which disables pyo3's default `extension-module` mode
and links libpython. The standalone script remains convenient for reproducing
the recorded experiment without changing the production crate.
