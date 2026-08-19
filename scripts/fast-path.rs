//! EMA input-null fast-path benchmark at the Arrow-array level.
//!
//! The output remains nullable because EMA warmup emits nulls. This benchmark
//! changes only how input values reach the filter:
//!
//!   option    every row goes through `Option<f64>` and `next_option`
//!   dispatch  inspect validity once per Arrow chunk; no-null chunks call
//!             `next_float`, nullable chunks call `next_float`/`next_null`
//!   float     raw values only; the no-null performance ceiling
//!
//! ```sh
//! cargo run --release --manifest-path bartons/Cargo.toml \
//!   --no-default-features --example fast-path
//! ```

use std::hint::black_box;
use std::time::{Duration, Instant};

use plugin::samples::{random_prices, RandomPricesOptions};
use polars::prelude::*;

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
    fn next_option(&mut self, input: Option<f64>) -> Option<f64> {
        match input {
            Some(value) => self.next_float(value),
            None => self.next_null(),
        }
    }

    #[inline]
    fn next_null(&mut self) -> Option<f64> {
        // EMA skips a null: emit null while carrying its running state.
        None
    }

    #[inline]
    fn next_float(&mut self, input: f64) -> Option<f64> {
        if self.count == 0 {
            self.value = input;
        } else {
            self.value += self.alpha * (input - self.value);
        }
        self.count += 1;
        (self.count >= PERIOD).then_some(self.value)
    }
}

#[inline]
fn append(output: &mut PrimitiveChunkedBuilder<Float64Type>, value: Option<f64>) {
    match value {
        Some(value) => output.append_value(value),
        None => output.append_null(),
    }
}

fn option_path(input: &Float64Chunked) -> Float64Chunked {
    let mut filter = Ema::new();
    let mut output = PrimitiveChunkedBuilder::new("ema".into(), input.len());
    for array in input.downcast_iter() {
        for value in array.iter().map(|value| value.copied()) {
            append(&mut output, filter.next_option(value));
        }
    }
    output.finish()
}

fn dispatch_path(input: &Float64Chunked) -> Float64Chunked {
    let mut filter = Ema::new();
    let mut output = PrimitiveChunkedBuilder::new("ema".into(), input.len());

    for array in input.downcast_iter() {
        if array.validity().is_none() {
            for value in array.values_iter().copied() {
                append(&mut output, filter.next_float(value));
            }
        } else {
            for value in array.iter() {
                let value = match value {
                    Some(value) => filter.next_float(*value),
                    None => filter.next_null(),
                };
                append(&mut output, value);
            }
        }
    }
    output.finish()
}

fn float_path(input: &Float64Chunked) -> Float64Chunked {
    assert_eq!(input.null_count(), 0);
    let mut filter = Ema::new();
    let mut output = PrimitiveChunkedBuilder::new("ema".into(), input.len());
    for array in input.downcast_iter() {
        for value in array.values_iter().copied() {
            append(&mut output, filter.next_float(value));
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

fn make_input(n_chunks: usize, null_first: bool) -> Float64Chunked {
    let frame = random_prices(RandomPricesOptions {
        n_rows: N,
        n_chunks,
        n_tickers: 1,
        seed: 0,
        null_first,
    })
    .unwrap();
    let input = frame.column("close").unwrap().f64().unwrap().clone();
    if !null_first {
        assert!(
            input
                .downcast_iter()
                .all(|array| array.validity().is_none()),
            "no-null fixture unexpectedly carries validity bitmaps"
        );
    }
    input
}

fn main() {
    println!("EMA input-null fast path: {N} rows, period {PERIOD}, {RUNS} runs");
    println!("minimum microseconds; lower is better\n");
    println!("input        | chunks | option | dispatch | float");
    println!("------------ | ------:| ------:| --------:| -----:");

    for n_chunks in CHUNK_COUNTS {
        let input = make_input(n_chunks, false);
        let expected = option_path(&input);
        assert!(same(&expected, &dispatch_path(&input)));
        assert!(same(&expected, &float_path(&input)));
        println!(
            "no nulls     | {n_chunks:>6} | {:>6.1} | {:>8.1} | {:>5.1}",
            micros(minimum(|| option_path(black_box(&input)))),
            micros(minimum(|| dispatch_path(black_box(&input)))),
            micros(minimum(|| float_path(black_box(&input)))),
        );

        let input = make_input(n_chunks, true);
        let expected = option_path(&input);
        assert!(same(&expected, &dispatch_path(&input)));
        println!(
            "leading null | {n_chunks:>6} | {:>6.1} | {:>8.1} |     —",
            micros(minimum(|| option_path(black_box(&input)))),
            micros(minimum(|| dispatch_path(black_box(&input)))),
        );
    }
}
