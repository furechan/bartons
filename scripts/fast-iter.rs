//! Unary iterator micro-benchmark using the real EMA recurrence.
//!
//! This intentionally compares only the three traversal shapes needed to
//! explain the performance difference in `bartons/src/utils.rs`:
//!
//!   polars        `Float64Chunked::iter()`
//!   fast          bartons' chunk cursor, reproduced here verbatim
//!   arrow-chunks  one outer loop over chunks, then each Arrow array's iterator
//!
//! The EMA, nullable output builder, input values, and chunk boundaries are
//! identical. Results are checked for equality before timing. Testing 1, 8,
//! and 64 chunks distinguishes single-array iterator overhead from repeated
//! chunk-boundary handling.
//!
//! Run against bartons' shared deterministic price fixture:
//!
//! ```sh
//! cargo run --release --manifest-path bartons/Cargo.toml \
//!   --no-default-features --example fast-iter
//! ```
//!
//! Release mode is required; debug timings are not meaningful.

use std::hint::black_box;
use std::time::{Duration, Instant};

use plugin::samples::{random_prices, RandomPricesOptions};
use polars::prelude::*;
use polars_arrow::array::PrimitiveArray;

const N: usize = 100_000;
const PERIOD: usize = 20;
const RUNS: usize = 300;
const CHUNK_COUNTS: [usize; 3] = [1, 8, 64];

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

struct ChunkCursor<'a> {
    parts: Vec<&'a PrimitiveArray<f64>>,
    chunk: usize,
    offset: usize,
    remaining: usize,
}

trait FastIter {
    fn fast_iter(&self) -> ChunkCursor<'_>;
}

impl FastIter for Float64Chunked {
    #[inline]
    fn fast_iter(&self) -> ChunkCursor<'_> {
        ChunkCursor {
            parts: self.downcast_iter().collect(),
            chunk: 0,
            offset: 0,
            remaining: self.len(),
        }
    }
}

impl Iterator for ChunkCursor<'_> {
    type Item = Option<f64>;

    #[inline]
    fn next(&mut self) -> Option<Self::Item> {
        if self.remaining == 0 {
            return None;
        }
        self.remaining -= 1;

        while self.offset >= self.parts[self.chunk].len() {
            self.chunk += 1;
            self.offset = 0;
        }

        let index = self.offset;
        self.offset += 1;
        // SAFETY: the loop above establishes that `index` is in bounds.
        Some(unsafe { self.parts[self.chunk].get_unchecked(index) })
    }

    #[inline]
    fn size_hint(&self) -> (usize, Option<usize>) {
        (self.remaining, Some(self.remaining))
    }
}

impl ExactSizeIterator for ChunkCursor<'_> {}

fn make_input(n_chunks: usize) -> Float64Chunked {
    let frame = random_prices(RandomPricesOptions {
        n_rows: N,
        n_chunks,
        n_tickers: 1,
        seed: 0,
        null_first: true,
    })
    .unwrap();
    frame.column("close").unwrap().f64().unwrap().clone()
}

#[inline]
fn append(builder: &mut PrimitiveChunkedBuilder<Float64Type>, value: Option<f64>) {
    match value {
        Some(value) => builder.append_value(value),
        None => builder.append_null(),
    }
}

fn polars_iter(input: &Float64Chunked) -> Float64Chunked {
    let mut ema = Ema::new(PERIOD);
    let mut builder = PrimitiveChunkedBuilder::new("ema".into(), input.len());
    for value in input.iter() {
        append(&mut builder, ema.next(value));
    }
    builder.finish()
}

fn fast_iter(input: &Float64Chunked) -> Float64Chunked {
    let mut ema = Ema::new(PERIOD);
    let mut builder = PrimitiveChunkedBuilder::new("ema".into(), input.len());
    for value in input.fast_iter() {
        append(&mut builder, ema.next(value));
    }
    builder.finish()
}

fn arrow_chunks(input: &Float64Chunked) -> Float64Chunked {
    let mut ema = Ema::new(PERIOD);
    let mut builder = PrimitiveChunkedBuilder::new("ema".into(), input.len());
    for array in input.downcast_iter() {
        for value in array.iter().map(|value| value.copied()) {
            append(&mut builder, ema.next(value));
        }
    }
    builder.finish()
}

fn minimum(input: &Float64Chunked, run: fn(&Float64Chunked) -> Float64Chunked) -> Duration {
    let mut best = Duration::MAX;
    for _ in 0..RUNS {
        let start = Instant::now();
        black_box(run(black_box(input)));
        best = best.min(start.elapsed());
    }
    best
}

fn micros(duration: Duration) -> f64 {
    duration.as_secs_f64() * 1_000_000.0
}

fn main() {
    println!("EMA iterator benchmark: {N} rows, period {PERIOD}, {RUNS} runs");
    println!("minimum microseconds; lower is better\n");
    println!("chunks | polars | fast | arrow-chunks | fast speedup");
    println!("------ | ------:| ----:| -------------:| ------------:");

    for chunks in CHUNK_COUNTS {
        let input = make_input(chunks);
        assert_eq!(input.chunks().len(), chunks);

        let expected = polars_iter(&input);
        let fast = fast_iter(&input);
        let arrow = arrow_chunks(&input);
        assert!(expected
            .clone()
            .into_series()
            .equals_missing(&fast.into_series()));
        assert!(expected
            .clone()
            .into_series()
            .equals_missing(&arrow.into_series()));

        // Warm each path before measuring it.
        black_box(polars_iter(&input));
        black_box(fast_iter(&input));
        black_box(arrow_chunks(&input));

        let polars = minimum(&input, polars_iter);
        let fast = minimum(&input, fast_iter);
        let arrow = minimum(&input, arrow_chunks);

        println!(
            "{chunks:>6} | {:>6.1} | {:>4.1} | {:>12.1} | {:>11.2}x",
            micros(polars),
            micros(fast),
            micros(arrow),
            polars.as_secs_f64() / fast.as_secs_f64(),
        );
    }
}
