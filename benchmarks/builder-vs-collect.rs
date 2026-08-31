//! EMA kernel micro-benchmark: what the streaming-filter abstraction costs, and
//! what the output-construction path costs. Recorded results and the reading of
//! them are in `notes/benchmarks/builder-vs-collect.md`.
//!
//! Five implementations of one EMA recurrence. Four of them are a 2x2 over the
//! two independent choices, which is the point — measuring only the diagonal
//! conflates them:
//!
//! | | manual `match` | `append_option` |
//! |---|---|---|
//! | inline logic | `builder` | `builder_opt` |
//! | `Ema::next` struct method | `filter_mat` | `filter` |
//!
//! Plus `collect` — map over `ca.iter()` into `.collect()`, a different output
//! path entirely, mirroring what polars' own `ewm_mean` does.
//!
//! `filter_mat` vs `builder` isolates the abstraction; `builder_opt` vs
//! `builder` isolates `append_option`. `run_unary`/`run_ternary` in
//! `bartons/src/utils.rs` are the `filter_mat` shape.
//!
//! The input carries a leading null, so the nullable path (validity bitmap) is
//! exercised rather than the all-valid fast path.
//!
//! NOT part of the cargo build — cargo only looks under `bartons/`, and this
//! could not live there anyway: `polars-utils` pulls `numpy` -> `pyo3`, and the
//! crate enables pyo3's `extension-module`, so it deliberately does not link
//! libpython and no example/test/bin target in that package can link at all.
//! The recurrence is therefore re-implemented here rather than imported. That
//! suits what this measures — the `Filter`-into-builder *pattern*, not EMA.
//!
//! Run it from a throwaway crate (~1 min, mostly compiling polars). Match the
//! polars pin in `bartons/Cargo.toml` or the numbers describe another version:
//!
//! ```sh
//! cargo new /tmp/bvc && cd /tmp/bvc
//! cargo add polars@0.55.1 --features dtype-struct
//! cp <repo>/benchmarks/builder-vs-collect.rs src/main.rs
//! cargo run --release            # release only; a debug build measures nothing
//! cargo run --release -- collect filter builder   # or name them to reorder
//! ```
//!
//! Timing is noisy run to run — compare `min`, and treat differences under ~10%
//! as noise. Passing names in a different order guards against ordering
//! artifacts, which is worth doing before believing any gap.

use polars::prelude::*;
use std::time::Instant;

/// N f64 values as a reproducible random walk, with a leading null.
fn make_input(n: usize) -> Float64Chunked {
    let mut data: Vec<Option<f64>> = Vec::with_capacity(n);
    data.push(None); // leading null -> forces the nullable path (validity bitmap)
    let mut acc = 100.0f64;
    let mut state: u64 = 0x9E37_79B9_7F4A_7C15;
    for _ in 1..n {
        // xorshift64 for reproducible pseudo-random steps
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        let u = (state >> 11) as f64 / ((1u64 << 53) as f64);
        acc += u - 0.5;
        data.push(Some(acc));
    }
    data.iter().copied().collect()
}

/// Inline loop appending into a `PrimitiveChunkedBuilder`.
fn ema_builder(ca: &Float64Chunked, period: i64) -> Float64Chunked {
    let alpha = 2.0 / (period as f64 + 1.0);
    let mut ema = f64::NAN;
    let mut count: i64 = 0;
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("ema".into(), ca.len());
    for opt_val in ca.iter() {
        let Some(val) = opt_val else {
            ema = f64::NAN;
            count = 0;
            builder.append_null();
            continue;
        };
        if count == 0 {
            ema = val;
        } else {
            ema += alpha * (val - ema);
        }
        count += 1;
        if count >= period {
            builder.append_value(ema);
        } else {
            builder.append_null();
        }
    }
    builder.finish()
}

/// Inline loop, but appending via `append_option` instead of a manual match.
fn ema_builder_option(ca: &Float64Chunked, period: i64) -> Float64Chunked {
    let alpha = 2.0 / (period as f64 + 1.0);
    let mut ema = f64::NAN;
    let mut count: i64 = 0;
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("ema".into(), ca.len());
    for opt_val in ca.iter() {
        let out = match opt_val {
            None => {
                ema = f64::NAN;
                count = 0;
                None
            }
            Some(val) => {
                if count == 0 {
                    ema = val;
                } else {
                    ema += alpha * (val - ema);
                }
                count += 1;
                (count >= period).then_some(ema)
            }
        };
        builder.append_option(out);
    }
    builder.finish()
}

/// Map over the iterator into `.collect()` (TrustedLen), mirroring `ewm_mean`.
fn ema_collect(ca: &Float64Chunked, period: i64) -> Float64Chunked {
    let alpha = 2.0 / (period as f64 + 1.0);
    let mut ema = f64::NAN;
    let mut count: i64 = 0;
    ca.iter()
        .map(|opt_val| match opt_val {
            None => {
                ema = f64::NAN;
                count = 0;
                None
            }
            Some(val) => {
                if count == 0 {
                    ema = val;
                } else {
                    ema += alpha * (val - ema);
                }
                count += 1;
                (count >= period).then_some(ema)
            }
        })
        .collect()
}

/// Same iterator as `ema_collect`, but explicitly selects Polars' TrustedLen
/// Arrow collector so it can omit per-element capacity checks.
fn ema_collect_trusted(ca: &Float64Chunked, period: i64) -> Float64Chunked {
    let alpha = 2.0 / (period as f64 + 1.0);
    let mut ema = f64::NAN;
    let mut count: i64 = 0;
    ca.iter()
        .map(|opt_val| match opt_val {
            None => {
                ema = f64::NAN;
                count = 0;
                None
            }
            Some(val) => {
                if count == 0 {
                    ema = val;
                } else {
                    ema += alpha * (val - ema);
                }
                count += 1;
                (count >= period).then_some(ema)
            }
        })
        .collect_ca_trusted(PlSmallStr::EMPTY)
}

/// The streaming-filter shape the crate actually uses, in miniature.
struct Ema {
    period: i64,
    alpha: f64,
    ema: f64,
    count: i64,
}

impl Ema {
    #[inline]
    fn new(period: i64) -> Self {
        Self {
            period,
            alpha: 2.0 / (period as f64 + 1.0),
            ema: f64::NAN,
            count: 0,
        }
    }

    #[inline]
    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        let Some(val) = input else {
            self.ema = f64::NAN;
            self.count = 0;
            return None;
        };
        if self.count == 0 {
            self.ema = val;
        } else {
            self.ema += self.alpha * (val - self.ema);
        }
        self.count += 1;
        (self.count >= self.period).then_some(self.ema)
    }
}

/// Same builder as `ema_builder`, differing only by the abstraction.
fn ema_filter(ca: &Float64Chunked, period: i64) -> Float64Chunked {
    let mut f = Ema::new(period);
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("ema".into(), ca.len());
    // append_option (ChunkedBuilder trait, via the prelude) = the value/null match.
    for x in ca.iter() {
        builder.append_option(f.next(x));
    }
    builder.finish()
}

/// Struct method, but appended via a manual match rather than `append_option`.
fn ema_filter_match(ca: &Float64Chunked, period: i64) -> Float64Chunked {
    let mut f = Ema::new(period);
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new("ema".into(), ca.len());
    for x in ca.iter() {
        match f.next(x) {
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

fn bench<F: FnMut() -> Float64Chunked>(label: &str, runs: usize, mut f: F) {
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
    println!(
        "{:<9} min = {:8.1} us   mean = {:8.1} us   ({} runs)",
        label,
        best,
        total / runs as f64,
        runs
    );
}

fn main() {
    let n = 100_000usize;
    let period = 20i64;
    let runs = 200;

    let ca = make_input(n);
    println!(
        "input     len = {}, nulls = {}, period = {}",
        ca.len(),
        ca.null_count(),
        period
    );

    // All three must agree before any timing is worth reading.
    let a = ema_builder(&ca, period);
    let b = ema_collect(&ca, period);
    let c = ema_filter(&ca, period);
    let d = ema_builder_option(&ca, period);
    let e = ema_filter_match(&ca, period);
    let identical = same(&a, &b) && same(&a, &c) && same(&a, &d) && same(&a, &e);
    println!(
        "identical = {}  (out len = {}, nulls = {})",
        identical,
        a.len(),
        a.null_count()
    );
    assert!(identical, "implementations disagree — timings are meaningless");

    let order: Vec<String> = std::env::args().skip(1).collect();
    let order: Vec<&str> = if order.is_empty() {
        vec![
            "builder",
            "builder_option",
            "filter_match",
            "filter",
            "collect",
            "collect_trusted",
        ]
    } else {
        order.iter().map(|s| s.as_str()).collect()
    };
    for name in order {
        match name {
            "builder" => bench("builder", runs, || ema_builder(&ca, period)),
            "collect" => bench("collect", runs, || ema_collect(&ca, period)),
            "collect_trusted" => bench("collect_tr", runs, || ema_collect_trusted(&ca, period)),
            "builder_option" => bench("builder_opt", runs, || ema_builder_option(&ca, period)),
            "filter_match" => bench("filter_mat", runs, || ema_filter_match(&ca, period)),
            "filter" => bench("filter", runs, || ema_filter(&ca, period)),
            other => panic!("unknown bench: {other}"),
        }
    }
}
