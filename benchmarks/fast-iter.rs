//! Controlled unary/ternary iterator benchmark using EMA and TRANGE.
//!
//! Both filters run in this executable with the same fixture, timer, output
//! builder, and three traversal strategies:
//!
//!   polars        `Float64Chunked::iter()`
//!   flatmap       the same chunk `flat_map` without `trust_my_length`
//!   fast          bartons' former custom chunk cursor, retained as a
//!                 historical control
//!   arrow-chunks  native Arrow iterators inside an outer chunk loop; this is
//!                 an aligned-chunk ceiling, not a general ternary iterator
//!
//! ```sh
//! cargo run --release --manifest-path bartons/Cargo.toml \
//!   --no-default-features --example fast-iter
//! ```

use std::hint::black_box;
use std::time::{Duration, Instant};

use itertools::izip;
use kernels::samples::{random_prices, RandomPricesOptions};
use polars::prelude::*;
use polars_arrow::array::PrimitiveArray;
use polars_arrow::legacy::utils::CustomIterTools;

const N: usize = 100_000;
const PERIOD: usize = 20;
const RUNS: usize = 300;
const CHUNK_COUNTS: [usize; 3] = [1, 8, 64];

struct Ema {
    alpha: f64,
    value: f64,
    count: usize,
}

impl Ema {
    fn new() -> Self {
        Self {
            alpha: 2.0 / (PERIOD as f64 + 1.0),
            value: f64::NAN,
            count: 0,
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
        (self.count >= PERIOD).then_some(self.value)
    }
}

#[derive(Default)]
struct Trange {
    previous_close: Option<f64>,
}

impl Trange {
    #[inline]
    fn next(&mut self, (high, low, close): (Option<f64>, Option<f64>, Option<f64>)) -> Option<f64> {
        let output = match (high, low) {
            (Some(high), Some(low)) => {
                let mut value = high - low;
                if let Some(previous) = self.previous_close {
                    value = value
                        .max((high - previous).abs())
                        .max((low - previous).abs());
                }
                Some(value)
            },
            _ => None,
        };
        self.previous_close = close;
        output
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
        Some(unsafe { self.parts[self.chunk].get_unchecked(index) })
    }

    #[inline]
    fn size_hint(&self) -> (usize, Option<usize>) {
        (self.remaining, Some(self.remaining))
    }
}

impl ExactSizeIterator for ChunkCursor<'_> {}

#[inline]
fn append(builder: &mut PrimitiveChunkedBuilder<Float64Type>, value: Option<f64>) {
    match value {
        Some(value) => builder.append_value(value),
        None => builder.append_null(),
    }
}

fn ema_polars(input: &Float64Chunked) -> Float64Chunked {
    let mut filter = Ema::new();
    let mut output = PrimitiveChunkedBuilder::new("ema".into(), input.len());
    for value in input.iter() {
        append(&mut output, filter.next(value));
    }
    output.finish()
}

fn ema_fast(input: &Float64Chunked) -> Float64Chunked {
    let mut filter = Ema::new();
    let mut output = PrimitiveChunkedBuilder::new("ema".into(), input.len());
    for value in input.fast_iter() {
        append(&mut output, filter.next(value));
    }
    output.finish()
}

fn ema_flatmap(input: &Float64Chunked) -> Float64Chunked {
    let mut filter = Ema::new();
    let mut output = PrimitiveChunkedBuilder::new("ema".into(), input.len());
    for value in input
        .downcast_iter()
        .flat_map(|array| array.iter().map(|value| value.copied()))
    {
        append(&mut output, filter.next(value));
    }
    output.finish()
}

fn ema_flatmap_trusted(input: &Float64Chunked) -> Float64Chunked {
    let mut filter = Ema::new();
    let mut output = PrimitiveChunkedBuilder::new("ema".into(), input.len());
    let values = input
        .downcast_iter()
        .flat_map(|array| array.iter().map(|value| value.copied()));
    // SAFETY: all chunk lengths sum to `input.len()`.
    let values = unsafe { values.trust_my_length(input.len()) };
    for value in values {
        append(&mut output, filter.next(value));
    }
    output.finish()
}

fn ema_arrow(input: &Float64Chunked) -> Float64Chunked {
    let mut filter = Ema::new();
    let mut output = PrimitiveChunkedBuilder::new("ema".into(), input.len());
    for array in input.downcast_iter() {
        for value in array.iter().map(|value| value.copied()) {
            append(&mut output, filter.next(value));
        }
    }
    output.finish()
}

fn trange_polars(
    high: &Float64Chunked,
    low: &Float64Chunked,
    close: &Float64Chunked,
) -> Float64Chunked {
    let mut filter = Trange::default();
    let mut output = PrimitiveChunkedBuilder::new("trange".into(), high.len());
    for values in izip!(high.iter(), low.iter(), close.iter()) {
        append(&mut output, filter.next(values));
    }
    output.finish()
}

fn trange_fast(
    high: &Float64Chunked,
    low: &Float64Chunked,
    close: &Float64Chunked,
) -> Float64Chunked {
    let mut filter = Trange::default();
    let mut output = PrimitiveChunkedBuilder::new("trange".into(), high.len());
    for values in izip!(high.fast_iter(), low.fast_iter(), close.fast_iter()) {
        append(&mut output, filter.next(values));
    }
    output.finish()
}

fn trange_flatmap(
    high: &Float64Chunked,
    low: &Float64Chunked,
    close: &Float64Chunked,
) -> Float64Chunked {
    let mut filter = Trange::default();
    let mut output = PrimitiveChunkedBuilder::new("trange".into(), high.len());
    let high = high
        .downcast_iter()
        .flat_map(|array| array.iter().map(|value| value.copied()));
    let low = low
        .downcast_iter()
        .flat_map(|array| array.iter().map(|value| value.copied()));
    let close = close
        .downcast_iter()
        .flat_map(|array| array.iter().map(|value| value.copied()));
    for values in izip!(high, low, close) {
        append(&mut output, filter.next(values));
    }
    output.finish()
}

fn trange_flatmap_trusted(
    high: &Float64Chunked,
    low: &Float64Chunked,
    close: &Float64Chunked,
) -> Float64Chunked {
    let mut filter = Trange::default();
    let mut output = PrimitiveChunkedBuilder::new("trange".into(), high.len());
    let high_values = high
        .downcast_iter()
        .flat_map(|array| array.iter().map(|value| value.copied()));
    let low_values = low
        .downcast_iter()
        .flat_map(|array| array.iter().map(|value| value.copied()));
    let close_values = close
        .downcast_iter()
        .flat_map(|array| array.iter().map(|value| value.copied()));
    // SAFETY: each column's chunk lengths sum to its logical length.
    let high_values = unsafe { high_values.trust_my_length(high.len()) };
    let low_values = unsafe { low_values.trust_my_length(low.len()) };
    let close_values = unsafe { close_values.trust_my_length(close.len()) };
    for values in izip!(high_values, low_values, close_values) {
        append(&mut output, filter.next(values));
    }
    output.finish()
}

fn trange_arrow(
    high: &Float64Chunked,
    low: &Float64Chunked,
    close: &Float64Chunked,
) -> Float64Chunked {
    let high_chunks: Vec<_> = high.chunks().iter().map(|chunk| chunk.len()).collect();
    let low_chunks: Vec<_> = low.chunks().iter().map(|chunk| chunk.len()).collect();
    let close_chunks: Vec<_> = close.chunks().iter().map(|chunk| chunk.len()).collect();
    assert_eq!(high_chunks, low_chunks, "high/low chunks are not aligned");
    assert_eq!(
        high_chunks, close_chunks,
        "high/close chunks are not aligned"
    );

    let mut filter = Trange::default();
    let mut output = PrimitiveChunkedBuilder::new("trange".into(), high.len());
    for (high_array, low_array, close_array) in izip!(
        high.downcast_iter(),
        low.downcast_iter(),
        close.downcast_iter()
    ) {
        for values in izip!(high_array.iter(), low_array.iter(), close_array.iter()) {
            append(
                &mut output,
                filter.next((values.0.copied(), values.1.copied(), values.2.copied())),
            );
        }
    }
    output.finish()
}

fn minimum<F: FnMut() -> Float64Chunked>(mut run: F) -> Duration {
    black_box(run());
    let mut best = Duration::MAX;
    for _ in 0..RUNS {
        let start = Instant::now();
        black_box(run());
        best = best.min(start.elapsed());
    }
    best
}

fn micros(duration: Duration) -> f64 {
    duration.as_secs_f64() * 1_000_000.0
}

fn same(left: &Float64Chunked, right: &Float64Chunked) -> bool {
    left.clone()
        .into_series()
        .equals_missing(&right.clone().into_series())
}

fn main() {
    println!("fast-iter: {N} rows, EMA period {PERIOD}, {RUNS} runs");
    println!("minimum microseconds; lower is better\n");
    println!("filter | chunks | polars | flatmap | + trusted | fast | arrow-chunks");
    println!("------ | ------:| ------:| -------:| ----------:| ----:| ------------:");

    for n_chunks in CHUNK_COUNTS {
        let frame = random_prices(RandomPricesOptions {
            n_rows: N,
            n_chunks,
            n_tickers: 1,
            seed: 0,
            null_first: true,
        })
        .unwrap();
        let high = frame.column("high").unwrap().f64().unwrap().clone();
        let low = frame.column("low").unwrap().f64().unwrap().clone();
        let close = frame.column("close").unwrap().f64().unwrap().clone();

        let ema_expected = ema_polars(&close);
        assert!(same(&ema_expected, &ema_flatmap(&close)));
        assert!(same(&ema_expected, &ema_flatmap_trusted(&close)));
        assert!(same(&ema_expected, &ema_fast(&close)));
        assert!(same(&ema_expected, &ema_arrow(&close)));

        println!(
            "EMA    | {n_chunks:>6} | {:>6.1} | {:>7.1} | {:>10.1} | {:>4.1} | {:>12.1}",
            micros(minimum(|| ema_polars(black_box(&close)))),
            micros(minimum(|| ema_flatmap(black_box(&close)))),
            micros(minimum(|| ema_flatmap_trusted(black_box(&close)))),
            micros(minimum(|| ema_fast(black_box(&close)))),
            micros(minimum(|| ema_arrow(black_box(&close)))),
        );

        let trange_expected = trange_polars(&high, &low, &close);
        assert!(same(&trange_expected, &trange_flatmap(&high, &low, &close)));
        assert!(same(
            &trange_expected,
            &trange_flatmap_trusted(&high, &low, &close)
        ));
        assert!(same(&trange_expected, &trange_fast(&high, &low, &close)));
        assert!(same(&trange_expected, &trange_arrow(&high, &low, &close)));

        println!(
            "TRANGE | {n_chunks:>6} | {:>6.1} | {:>7.1} | {:>10.1} | {:>4.1} | {:>12.1}",
            micros(minimum(|| trange_polars(
                black_box(&high),
                black_box(&low),
                black_box(&close)
            ))),
            micros(minimum(|| trange_flatmap(
                black_box(&high),
                black_box(&low),
                black_box(&close)
            ))),
            micros(minimum(|| trange_flatmap_trusted(
                black_box(&high),
                black_box(&low),
                black_box(&close)
            ))),
            micros(minimum(|| trange_fast(
                black_box(&high),
                black_box(&low),
                black_box(&close)
            ))),
            micros(minimum(|| trange_arrow(
                black_box(&high),
                black_box(&low),
                black_box(&close)
            ))),
        );
    }
}
