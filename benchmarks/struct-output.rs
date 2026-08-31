//! Two-field nullable struct-output construction benchmark.
//!
//! This isolates output construction from indicator calculation:
//!
//!   builder       today's explicit pair of typed child builders
//!   vec-collect   ergonomic tuple `collect()` into two `Vec<Option<f64>>`,
//!                 then collect each vector into a Polars child array
//!   direct-collect tuple `collect()` into a reusable collector which writes
//!                  directly into the same typed child builders as `builder`
//!
//! All paths produce the same physical Arrow struct: two nullable Float64 child
//! arrays and no outer struct validity. Run in release mode:
//!
//! ```sh
//! cargo run --release --manifest-path bartons/Cargo.toml \
//!   --no-default-features --example struct-output
//! ```

use std::hint::black_box;
use std::time::{Duration, Instant};

use polars::prelude::*;

const N: usize = 100_000;
const RUNS: usize = 300;

type Row = (Option<f64>, Option<f64>);

#[inline]
fn rows() -> impl ExactSizeIterator<Item = Row> {
    (0..N).map(|index| {
        let value = index as f64 * 0.25;
        let left = (index >= 20 && index % 997 != 0).then_some(value);
        let right = (index >= 40 && index % 991 != 0).then_some(value * 2.0);
        (left, right)
    })
}

#[inline]
fn append(builder: &mut PrimitiveChunkedBuilder<Float64Type>, value: Option<f64>) {
    match value {
        Some(value) => builder.append_value(value),
        None => builder.append_null(),
    }
}

fn finish_struct(left: Float64Chunked, right: Float64Chunked) -> Series {
    let mut left = left;
    let mut right = right;
    left.rename("left".into());
    right.rename("right".into());
    let fields = [left.into_series(), right.into_series()];
    StructChunked::from_series("output".into(), fields[0].len(), fields.iter())
        .unwrap()
        .into_series()
}

fn builder_path() -> Series {
    let mut left = PrimitiveChunkedBuilder::<Float64Type>::new("left".into(), N);
    let mut right = PrimitiveChunkedBuilder::<Float64Type>::new("right".into(), N);

    for (left_value, right_value) in rows() {
        append(&mut left, left_value);
        append(&mut right, right_value);
    }

    finish_struct(left.finish(), right.finish())
}

fn vec_collect_path() -> Series {
    let (left, right): (Vec<Option<f64>>, Vec<Option<f64>>) = rows().collect();
    finish_struct(left.into_iter().collect(), right.into_iter().collect())
}

struct PairColumns {
    left: PrimitiveChunkedBuilder<Float64Type>,
    right: PrimitiveChunkedBuilder<Float64Type>,
}

impl FromIterator<Row> for PairColumns {
    #[inline]
    fn from_iter<I: IntoIterator<Item = Row>>(rows: I) -> Self {
        let rows = rows.into_iter();
        let capacity = rows.size_hint().0;
        let mut output = Self {
            left: PrimitiveChunkedBuilder::new("left".into(), capacity),
            right: PrimitiveChunkedBuilder::new("right".into(), capacity),
        };

        for (left, right) in rows {
            append(&mut output.left, left);
            append(&mut output.right, right);
        }
        output
    }
}

impl PairColumns {
    fn finish(self) -> Series {
        finish_struct(self.left.finish(), self.right.finish())
    }
}

fn direct_collect_path() -> Series {
    let output: PairColumns = rows().collect();
    output.finish()
}

fn measure(mut run: impl FnMut() -> Series) -> (Duration, Duration) {
    let _ = black_box(run());
    let mut minimum = Duration::MAX;
    let mut total = Duration::ZERO;
    for _ in 0..RUNS {
        let start = Instant::now();
        let _ = black_box(run());
        let elapsed = start.elapsed();
        minimum = minimum.min(elapsed);
        total += elapsed;
    }
    (minimum, total / RUNS as u32)
}

fn micros(duration: Duration) -> f64 {
    duration.as_secs_f64() * 1_000_000.0
}

fn main() {
    let expected = builder_path();
    assert!(expected.equals_missing(&vec_collect_path()));
    assert!(expected.equals_missing(&direct_collect_path()));

    println!("Nullable Float64 pair struct: {N} rows, {RUNS} runs");
    println!("path           | min (µs) | mean (µs)");
    println!("-------------- | --------:| ---------:");
    for (name, run) in [
        ("builder", builder_path as fn() -> Series),
        ("vec-collect", vec_collect_path as fn() -> Series),
        ("direct-collect", direct_collect_path as fn() -> Series),
    ] {
        let (minimum, mean) = measure(run);
        println!(
            "{name:<14} | {:>8.1} | {:>9.1}",
            micros(minimum),
            micros(mean),
        );
    }
}
