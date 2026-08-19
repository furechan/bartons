//! Ternary driver micro-benchmark: `izip!` over three iterators vs a loop over
//! indexes. Recorded results and the reading of them are in
//! `docs/izip-vs-index-benchmark.md`.
//!
//! `run_ternary` in `bartons/src/utils.rs` walks three series with `izip!`.
//! This measures that against the alternatives, with the real TRANGE recurrence
//! as the per-element logic and the output path held constant (manual `match`
//! into a `PrimitiveChunkedBuilder` — never `append_option`, which
//! `docs/builder-vs-collect-benchmark.md` measures at ~1.6x):
//!
//!   izip       izip!(a.iter(), b.iter(), c.iter())     <- what run_ternary does
//!   index      for i in 0..len { a.get(i), b.get(i), .. }
//!   unchecked  same, with get_unchecked
//!   rechunk    rechunk to one chunk, then index the values slice + validity
//!              bitmap directly (rechunk cost is inside the timed region)
//!   chunked    walk every chunk, hoisting the downcast once per chunk; no
//!              rechunk, so no temporaries at any chunking
//!   iternext   three ChunkedArray::iter() advanced by hand with .next(), to
//!              separate izip!'s machinery from the per-call cost of next
//!   ziparr     hoists the downcast, then zips the *arrow array* iterators —
//!              same iteration without ChunkedArray's FlatMap-over-chunks layer
//!   valiter    three raw values_iter() slice iterators, validity read by index
//!   threeidx   like the single-chunk hoisted loop but with one index per array
//!              instead of a shared one — isolates cursor count from chunk logic
//!   fastiter   `chunked`'s hand-rolled cursor expressed as an Iterator behind a
//!              `FastIter` trait — measures what that abstraction costs
//!   fast-iternext  three `FastIter` cursors advanced by hand with `.next()`,
//!              isolating `izip!` from the custom iterator implementation
//!   fastpath   single-chunk inputs take the hoisted loop, everything else
//!              takes `chunked` <- the candidate
//!
//! The result that matters is *why* the last three win: `ChunkedArray::get` and
//! `get_unchecked` both re-derive the array on every element — index chunks[0],
//! deref the Arc<dyn Array>, downcast — and that cannot be hoisted through
//! `&self`. Doing the downcast once halves the time. Rechunking is only one way
//! to make that legal, and an expensive one; walking chunks gets the same win
//! for free.
//!
//! Run at 1, 8 and 64 chunks: `ChunkedArray::get` resolves which chunk an index
//! falls in on every call, and that is where the shapes diverge. A unary
//! (single-series) pair runs too, to locate whether any gap belongs to `iter()`
//! generally or specifically to zipping three of them.
//!
//! NOT part of the cargo build, and it could not be: `polars-utils` pulls
//! `numpy` -> `pyo3`, and the crate enables pyo3's `extension-module`, so no
//! example, test or bin target in that package can link. Same constraint as
//! `builder-vs-collect.rs`, and the same remedy — a standalone program plus a
//! recipe.
//!
//! **This must be built by cargo, not run in an evcxr notebook.** A notebook
//! version of this same source reversed the izip-vs-rechunk result; see the
//! Divergence section of the doc. Anything measured here is a claim about a
//! `cargo run --release` build and nothing else.
//!
//! Run it as a bartons example so every path uses the shared deterministic
//! `random_prices` fixture:
//!
//! ```sh
//! cargo run --release --manifest-path bartons/Cargo.toml \
//!   --no-default-features --example izip-vs-index
//! ```
//!
//! Timing is noisy run to run — compare `min`, and treat differences under ~10%
//! as noise. Passing names in a different order guards against ordering
//! artifacts, which is worth doing before believing any gap.

use itertools::izip;
use plugin::samples::{random_prices, RandomPricesOptions};
use polars_arrow::array::PrimitiveArray;
use polars::prelude::*;
use std::fmt::Write as _;
use std::time::Instant;

type Hlc = (Option<f64>, Option<f64>, Option<f64>);

/// Accumulates the report so it can go to stdout and, optionally, a file.
#[derive(Default)]
struct Report {
    body: String,
}

impl Report {
    fn line(&mut self, s: String) {
        println!("{s}");
        let _ = writeln!(self.body, "{s}");
    }
}

#[derive(Default)]
struct TrangeFilter {
    prev_close: Option<f64>,
}

impl TrangeFilter {
    #[inline]
    fn next(&mut self, (high, low, close): Hlc) -> Option<f64> {
        let tr = match (high, low) {
            (Some(hi), Some(lo)) => {
                let mut tr = hi - lo;
                if let Some(pc) = self.prev_close {
                    tr = tr.max((hi - pc).abs()).max((lo - pc).abs());
                }
                Some(tr)
            }
            _ => None,
        };
        self.prev_close = close;
        tr
    }
}

fn make_input(n_rows: usize, n_chunks: usize) -> DataFrame {
    random_prices(RandomPricesOptions {
        n_rows,
        n_chunks,
        n_tickers: 1,
        seed: 0,
        null_first: true,
    })
    .unwrap()
}

fn v_izip(a: &Float64Chunked, b: &Float64Chunked, c: &Float64Chunked) -> Float64Chunked {
    let mut f = TrangeFilter::default();
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("trange".into(), a.len());
    for triple in izip!(a.iter(), b.iter(), c.iter()) {
        match f.next(triple) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }
    builder.finish()
}

fn v_index(a: &Float64Chunked, b: &Float64Chunked, c: &Float64Chunked) -> Float64Chunked {
    let mut f = TrangeFilter::default();
    let len = a.len();
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("trange".into(), len);
    for i in 0..len {
        match f.next((a.get(i), b.get(i), c.get(i))) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }
    builder.finish()
}

fn v_unchecked(a: &Float64Chunked, b: &Float64Chunked, c: &Float64Chunked) -> Float64Chunked {
    let mut f = TrangeFilter::default();
    let len = a.len();
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("trange".into(), len);
    for i in 0..len {
        let triple = unsafe { (a.get_unchecked(i), b.get_unchecked(i), c.get_unchecked(i)) };
        match f.next(triple) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }
    builder.finish()
}

/// Index the raw values slice + validity bitmap. Single-chunk input only, so it
/// is the ceiling for an index loop rather than a candidate implementation.
fn v_slices(a: &Float64Chunked, b: &Float64Chunked, c: &Float64Chunked) -> Float64Chunked {
    let mut f = TrangeFilter::default();
    let len = a.len();
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("trange".into(), len);

    // Hoist the downcast; the arrow array yields Option<f64> directly, so there
    // is no need to take values() and validity() apart and reassemble them.
    let aa = a.downcast_iter().next().unwrap();
    let ba = b.downcast_iter().next().unwrap();
    let cc = c.downcast_iter().next().unwrap();

    for i in 0..len {
        let triple = unsafe { (aa.get_unchecked(i), ba.get_unchecked(i), cc.get_unchecked(i)) };
        match f.next(triple) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }
    builder.finish()
}

/// The shippable shape of `v_slices`: rechunk so the single-chunk assumption
/// always holds, then index. Rechunk is a cheap Arc clone when the array is
/// already one chunk and a memcpy otherwise — inside the timed region on
/// purpose, since a real driver would have to pay it.
fn v_rechunk(a: &Float64Chunked, b: &Float64Chunked, c: &Float64Chunked) -> Float64Chunked {
    let a = a.rechunk();
    let b = b.rechunk();
    let c = c.rechunk();
    v_slices(&a, &b, &c)
}

// ---- unary: is any gap about `iter()`, or about zipping three of them? ------

struct Ema {
    alpha: f64,
    value: f64,
    count: usize,
    period: usize,
}

impl Ema {
    fn new(period: usize) -> Self {
        Self {
            alpha: 2.0 / (period as f64 + 1.0),
            value: f64::NAN,
            count: 0,
            period,
        }
    }

    #[inline]
    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        let value = input?;
        if self.count == 0 {
            self.value = value;
        } else {
            self.value += self.alpha * (value - self.value);
        }
        self.count += 1;
        (self.count >= self.period).then_some(self.value)
    }
}

fn u_iter(a: &Float64Chunked, period: usize) -> Float64Chunked {
    let mut f = Ema::new(period);
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("ema".into(), a.len());
    for x in a.iter() {
        match f.next(x) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }
    builder.finish()
}

fn u_rechunk(a: &Float64Chunked, period: usize) -> Float64Chunked {
    let a = a.rechunk();
    let mut f = Ema::new(period);
    let len = a.len();
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("ema".into(), len);
    let arr = a.downcast_iter().next().unwrap();
    let vals = arr.values();
    let val = arr.validity();
    for i in 0..len {
        let x = match val {
            Some(bm) if !bm.get_bit(i) => None,
            _ => Some(vals[i]),
        };
        match f.next(x) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }
    builder.finish()
}

/// Native Arrow iterator after hoisting the single chunk's downcast. This is
/// the single-chunk path now used by `run_unary`.
fn u_arrowiter(a: &Float64Chunked, period: usize) -> Float64Chunked {
    assert_eq!(a.chunks().len(), 1);
    let mut f = Ema::new(period);
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("ema".into(), a.len());
    let arr = a.downcast_iter().next().unwrap();
    for x in arr.iter().map(|value| value.copied()) {
        match f.next(x) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }
    builder.finish()
}

/// General copy-free cursor path now used by `run_unary` for fragmented input.
fn u_fastiter(a: &Float64Chunked, period: usize) -> Float64Chunked {
    let mut f = Ema::new(period);
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("ema".into(), a.len());
    for x in a.fast_iter() {
        match f.next(x) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }
    builder.finish()
}

/// Walk each Arrow chunk with its native iterator, carrying one filter and
/// builder across the outer loop. Copy-free, without a cross-chunk cursor.
fn u_arrowchunks(a: &Float64Chunked, period: usize) -> Float64Chunked {
    let mut f = Ema::new(period);
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("ema".into(), a.len());
    for arr in a.downcast_iter() {
        for x in arr.iter().map(|value| value.copied()) {
            match f.next(x) {
                Some(v) => builder.append_value(v),
                None => builder.append_null(),
            }
        }
    }
    builder.finish()
}

/// The production unary setup, including the same-dtype `Series::cast` and
/// typed downcast before entering `FastIter`.
fn u_runstyle(series: &Series, period: usize) -> Float64Chunked {
    let series = series.cast(&DataType::Float64).unwrap();
    u_fastiter(series.f64().unwrap(), period)
}

/// Copy-free candidate: when all three inputs are a single chunk — the common
/// case for plugin input — hoist the downcast once and index the values slice
/// and validity bitmap directly. Otherwise fall back to `izip!`, which handles
/// fragmentation well. No rechunk, so no temporaries at any chunking.
fn v_fastpath(a: &Float64Chunked, b: &Float64Chunked, c: &Float64Chunked) -> Float64Chunked {
    if a.chunks().len() == 1 && b.chunks().len() == 1 && c.chunks().len() == 1 {
        v_slices(a, b, c)
    } else {
        v_fastiter(a, b, c)
    }
}

/// Fully general copy-free version: walk every chunk of every input, hoisting
/// the downcast once per chunk and threading one filter through the whole
/// series. Chunk boundaries need not align across the three inputs, so each
/// carries its own cursor. No rechunk, so no temporaries at any chunking.
fn v_chunked(a: &Float64Chunked, b: &Float64Chunked, c: &Float64Chunked) -> Float64Chunked {
    let len = a.len();
    let mut f = TrangeFilter::default();
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("trange".into(), len);

    // Hoist the downcast per chunk. `Vec<_>` keeps the arrow type unnamed,
    // which would otherwise need a polars-arrow dependency.
    let pa: Vec<_> = a.downcast_iter().collect();
    let pb: Vec<_> = b.downcast_iter().collect();
    let pc: Vec<_> = c.downcast_iter().collect();

    // Read one element and advance, skipping any empty chunks.
    macro_rules! take {
        ($parts:expr, $ci:expr, $off:expr) => {{
            while $off >= $parts[$ci].len() {
                $ci += 1;
                $off = 0;
            }
            let i = $off;
            $off += 1;
            unsafe { $parts[$ci].get_unchecked(i) }
        }};
    }

    let (mut ai, mut ao) = (0usize, 0usize);
    let (mut bi, mut bo) = (0usize, 0usize);
    let (mut ci, mut co) = (0usize, 0usize);
    for _ in 0..len {
        let triple = (take!(pa, ai, ao), take!(pb, bi, bo), take!(pc, ci, co));
        match f.next(triple) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }
    builder.finish()
}

/// Idiomatic alternative to `v_slices`: still hoists the downcast, but zips the
/// *arrow array* iterators rather than indexing. These are plain validity-zipped
/// slice iterators with no FlatMap over chunks, which is the structure that
/// makes `ChunkedArray::iter()` expensive to zip three of. Single-chunk only.
fn v_ziparr(a: &Float64Chunked, b: &Float64Chunked, c: &Float64Chunked) -> Float64Chunked {
    let mut f = TrangeFilter::default();
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("trange".into(), a.len());
    let aa = a.downcast_iter().next().unwrap();
    let ba = b.downcast_iter().next().unwrap();
    let cc = c.downcast_iter().next().unwrap();
    for triple in izip!(aa.iter(), ba.iter(), cc.iter()) {
        let triple = (triple.0.copied(), triple.1.copied(), triple.2.copied());
        match f.next(triple) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }
    builder.finish()
}

/// Same shape as `v_chunked` — three independent cursors advanced in lockstep —
/// but the cursors are `ChunkedArray::iter()` and advancing is `.next()` rather
/// than a hand-rolled chunk/offset pair. Isolates whether the cost is `izip!`'s
/// zipping machinery or the per-call cost of `FlatMap::next` itself. Correct at
/// any chunking, since `iter()` handles chunk boundaries.
fn v_iternext(a: &Float64Chunked, b: &Float64Chunked, c: &Float64Chunked) -> Float64Chunked {
    let mut f = TrangeFilter::default();
    let len = a.len();
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("trange".into(), len);
    let mut ia = a.iter();
    let mut ib = b.iter();
    let mut ic = c.iter();
    for _ in 0..len {
        let triple = (
            ia.next().unwrap(),
            ib.next().unwrap(),
            ic.next().unwrap(),
        );
        match f.next(triple) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }
    builder.finish()
}

/// Three raw `values_iter()` slice iterators for the values, with validity read
/// separately by index. Isolates the `ZipValidity` wrapper from the underlying
/// slice iteration. Single-chunk only.
fn v_valiter(a: &Float64Chunked, b: &Float64Chunked, c: &Float64Chunked) -> Float64Chunked {
    let mut f = TrangeFilter::default();
    let len = a.len();
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("trange".into(), len);
    let aa = a.downcast_iter().next().unwrap();
    let ba = b.downcast_iter().next().unwrap();
    let cc = c.downcast_iter().next().unwrap();
    let (an, bn, cn) = (aa.validity(), ba.validity(), cc.validity());
    let mut ia = aa.values_iter();
    let mut ib = ba.values_iter();
    let mut ic = cc.values_iter();
    for i in 0..len {
        let va = *ia.next().unwrap();
        let vb = *ib.next().unwrap();
        let vc = *ic.next().unwrap();
        let triple = (
            match an { Some(m) if !m.get_bit(i) => None, _ => Some(va) },
            match bn { Some(m) if !m.get_bit(i) => None, _ => Some(vb) },
            match cn { Some(m) if !m.get_bit(i) => None, _ => Some(vc) },
        );
        match f.next(triple) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }
    builder.finish()
}

/// Same as `v_slices` — single chunk, no chunk-boundary logic — but each array
/// is walked by its OWN index rather than one shared `i`. Isolates "one shared
/// position" from "no chunk branching", which `v_slices` vs `v_chunked`
/// confounds. Single-chunk only.
fn v_threeidx(a: &Float64Chunked, b: &Float64Chunked, c: &Float64Chunked) -> Float64Chunked {
    let mut f = TrangeFilter::default();
    let len = a.len();
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("trange".into(), len);
    let aa = a.downcast_iter().next().unwrap();
    let ba = b.downcast_iter().next().unwrap();
    let cc = c.downcast_iter().next().unwrap();
    let (mut ia, mut ib, mut ic) = (0usize, 0usize, 0usize);
    for _ in 0..len {
        let triple = unsafe { (aa.get_unchecked(ia), ba.get_unchecked(ib), cc.get_unchecked(ic)) };
        ia += 1;
        ib += 1;
        ic += 1;
        match f.next(triple) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }
    builder.finish()
}

// ---- the take! macro, as a trait -------------------------------------------

/// A cursor over one `ChunkedArray`'s chunks, hoisting the downcast once per
/// chunk. This is the `take!` macro in `v_chunked` expressed as an `Iterator`;
/// `v_fastiter` measures whether that abstraction is free.
struct ChunkCursor<'a> {
    parts: Vec<&'a PrimitiveArray<f64>>,
    ci: usize,
    off: usize,
    left: usize,
}

/// Extension trait so this reads as `ca.fast_iter()`.
trait FastIter {
    fn fast_iter(&self) -> ChunkCursor<'_>;
}

impl FastIter for Float64Chunked {
    #[inline]
    fn fast_iter(&self) -> ChunkCursor<'_> {
        ChunkCursor {
            parts: self.downcast_iter().collect(),
            ci: 0,
            off: 0,
            left: self.len(),
        }
    }
}

impl<'a> Iterator for ChunkCursor<'a> {
    type Item = Option<f64>;

    #[inline]
    fn next(&mut self) -> Option<Option<f64>> {
        if self.left == 0 {
            return None;
        }
        self.left -= 1;
        while self.off >= self.parts[self.ci].len() {
            self.ci += 1;
            self.off = 0;
        }
        let i = self.off;
        self.off += 1;
        // SAFETY: i < parts[ci].len() by the loop above.
        Some(unsafe { self.parts[self.ci].get_unchecked(i) })
    }

    #[inline]
    fn size_hint(&self) -> (usize, Option<usize>) {
        (self.left, Some(self.left))
    }
}

/// `v_chunked` with the macro replaced by the `FastIter` trait.
fn v_fastiter(a: &Float64Chunked, b: &Float64Chunked, c: &Float64Chunked) -> Float64Chunked {
    let mut f = TrangeFilter::default();
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("trange".into(), a.len());
    for triple in izip!(a.fast_iter(), b.fast_iter(), c.fast_iter()) {
        match f.next(triple) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }
    builder.finish()
}

/// The same three `FastIter` cursors as `v_fastiter`, advanced explicitly.
/// Comparing these two isolates `izip!` while holding the iterator types fixed.
fn v_fast_iternext(
    a: &Float64Chunked,
    b: &Float64Chunked,
    c: &Float64Chunked,
) -> Float64Chunked {
    let mut f = TrangeFilter::default();
    let len = a.len();
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("trange".into(), len);
    let mut ia = a.fast_iter();
    let mut ib = b.fast_iter();
    let mut ic = c.fast_iter();

    for _ in 0..len {
        let triple = (
            ia.next().unwrap(),
            ib.next().unwrap(),
            ic.next().unwrap(),
        );
        match f.next(triple) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }
    builder.finish()
}

fn same(x: &Float64Chunked, y: &Float64Chunked) -> bool {
    x.len() == y.len()
        && x.iter().zip(y.iter()).all(|(p, q)| match (p, q) {
            (Some(p), Some(q)) => p == q,
            (None, None) => true,
            _ => false,
        })
}

fn bench<F: FnMut() -> Float64Chunked>(rep: &mut Report, label: &str, runs: usize, mut f: F) {
    std::hint::black_box(f()); // warmup
    let mut best = f64::INFINITY;
    let mut total = 0.0f64;
    for _ in 0..runs {
        let t = Instant::now();
        let r = f();
        std::hint::black_box(&r);
        let us = t.elapsed().as_secs_f64() * 1e6;
        total += us;
        if us < best {
            best = us;
        }
    }
    rep.line(format!(
        "  {:<10} min = {:8.1} us   mean = {:8.1} us   ({} runs)",
        label,
        best,
        total / runs as f64,
        runs
    ));
}

fn main() {
    let n = 100_000usize;
    let period = 20usize;
    let runs = 200;

    // `--out <path>` writes the report alongside stdout; remaining args name
    // variants to run, in that order.
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    let mut out_path: Option<String> = None;
    if let Some(i) = args.iter().position(|a| a == "--out") {
        out_path = args.get(i + 1).cloned();
        args.drain(i..=(i + 1).min(args.len() - 1));
    }
    let order: Vec<&str> = if args.is_empty() {
        vec!["izip", "iternext", "index", "unchecked", "rechunk", "chunked", "fastiter", "fast-iternext", "ziparr", "valiter", "threeidx", "fastpath"]
    } else {
        args.iter().map(|s| s.as_str()).collect()
    };

    let mut rep = Report::default();
    rep.line(format!(
        "izip-vs-index  n = {n}  runs = {runs}  target = {}-{}",
        std::env::consts::ARCH,
        std::env::consts::OS
    ));
    rep.line(String::new());

    let inputs = [1usize, 8, 64]
        .map(|n_chunks| (n_chunks, make_input(n, n_chunks)));

    rep.line("--- unary (EMA): is it iter() itself? ---".to_string());
    for (n_chunks, frame) in &inputs {
        let close = frame.column("close").unwrap().f64().unwrap().clone();
        let series = close.clone().into_series();
        let expected = u_iter(&close, period);
        assert!(same(&expected, &u_rechunk(&close, period)), "unary variants disagree");
        assert!(same(&expected, &u_fastiter(&close, period)), "unary fastiter disagrees");
        assert!(same(&expected, &u_arrowchunks(&close, period)), "unary arrowchunks disagrees");
        if *n_chunks == 1 {
            assert!(same(&expected, &u_arrowiter(&close, period)), "unary arrowiter disagrees");
        }
        rep.line(format!("chunks = {}", close.chunks().len()));
        bench(&mut rep, "iter", runs, || u_iter(&close, period));
        bench(&mut rep, "rechunk", runs, || u_rechunk(&close, period));
        bench(&mut rep, "fastiter", runs, || u_fastiter(&close, period));
        bench(&mut rep, "arrowchunks", runs, || u_arrowchunks(&close, period));
        bench(&mut rep, "runstyle", runs, || u_runstyle(&series, period));
        if *n_chunks == 1 {
            bench(&mut rep, "arrowiter", runs, || u_arrowiter(&close, period));
        }
        rep.line(String::new());
    }

    rep.line("--- ternary (TRANGE) ---".to_string());
    for (n_chunks, frame) in &inputs {
        let h = frame.column("high").unwrap().f64().unwrap().clone();
        let l = frame.column("low").unwrap().f64().unwrap().clone();
        let c = frame.column("close").unwrap().f64().unwrap().clone();

        // Agreement first — timings mean nothing if the variants disagree.
        let a = v_izip(&h, &l, &c);
        let mut ok = same(&a, &v_index(&h, &l, &c))
            && same(&a, &v_unchecked(&h, &l, &c))
            && same(&a, &v_rechunk(&h, &l, &c))
            && same(&a, &v_fastpath(&h, &l, &c))
            && same(&a, &v_chunked(&h, &l, &c))
            && same(&a, &v_iternext(&h, &l, &c))
            && same(&a, &v_fast_iternext(&h, &l, &c));
        // `ziparr` reads one chunk only, so it is correct — and benchmarked —
        // solely at one chunk. Running it elsewhere silently truncates the
        // output and reports an absurdly fast time.
        if *n_chunks == 1 {
            ok = ok && same(&a, &v_ziparr(&h, &l, &c)) && same(&a, &v_valiter(&h, &l, &c)) && same(&a, &v_threeidx(&h, &l, &c));
        }
        assert!(ok, "implementations disagree — timings are meaningless");
        rep.line(format!(
            "chunks = {:<3} len = {} nulls = {} identical = {}",
            h.chunks().len(),
            h.len(),
            h.null_count(),
            ok
        ));

        for name in &order {
            match *name {
                "izip" => bench(&mut rep, "izip", runs, || v_izip(&h, &l, &c)),
                "index" => bench(&mut rep, "index", runs, || v_index(&h, &l, &c)),
                "unchecked" => bench(&mut rep, "unchecked", runs, || v_unchecked(&h, &l, &c)),
                "fastpath" => bench(&mut rep, "fastpath", runs, || v_fastpath(&h, &l, &c)),
                "chunked" => bench(&mut rep, "chunked", runs, || v_chunked(&h, &l, &c)),
                "fastiter" => bench(&mut rep, "fastiter", runs, || v_fastiter(&h, &l, &c)),
                "fast-iternext" => bench(&mut rep, "fast-iternext", runs, || v_fast_iternext(&h, &l, &c)),
                "iternext" => bench(&mut rep, "iternext", runs, || v_iternext(&h, &l, &c)),
                "threeidx" => {
                    if *n_chunks == 1 {
                        bench(&mut rep, "threeidx", runs, || v_threeidx(&h, &l, &c))
                    }
                }
                "valiter" => {
                    if *n_chunks == 1 {
                        bench(&mut rep, "valiter", runs, || v_valiter(&h, &l, &c))
                    }
                }
                "ziparr" => {
                    if *n_chunks == 1 {
                        bench(&mut rep, "ziparr", runs, || v_ziparr(&h, &l, &c))
                    }
                }
                "rechunk" => bench(&mut rep, "rechunk", runs, || v_rechunk(&h, &l, &c)),
                other => panic!("unknown bench: {other}"),
            }
        }
        rep.line(String::new());
    }

    if let Some(path) = out_path {
        std::fs::write(&path, &rep.body).expect("failed to write report");
        println!("wrote {path}");
    }
}
