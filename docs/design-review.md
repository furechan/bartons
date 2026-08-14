# Design review: the `Filter` + driver-loop core

Review of the `Filter` trait and the `run_unary` / `run_ternary` drivers in
[bartons/src/utils.rs](../bartons/src/utils.rs), 2026-08-14. Covers all seven
indicators as they stood at that date.

**Verdict: keep the loop-over-`Filter` design.** It is the right core for this
library. Three rough edges are worth fixing, and two more are decisions to
record rather than defects to repair.

## Why the design holds up

**Most of these indicators are inherently sequential.** EMA, RMA, RSI and ATR
are recursive — there is no vectorized alternative being given up. And because
`run_unary<F: Filter>` is generic, it monomorphizes and `next` inlines: the
emitted code matches a hand-written per-indicator loop. The abstraction is free
here, which is exactly when a trait earns its place.

**Composability is the real payoff.** `AtrFilter` is a `TrangeFilter` feeding an
`RmaFilter`; `RsiFilter` is two `RmaFilter`s. A vectorized design would force
each composite to materialize intermediate Series. Per-element stateful steps
compose for free — and the same filters are what a live/incremental bar-feed API
would expose later.

**Null policy lives where the math lives.** Skip-vs-reset is a single early
return at the top of each `next`, which is why the recursive (EMA, RMA — carry
state across the gap) versus windowed (SMA, WMA — reset the run) split reads
clearly instead of being smeared across a driver.

## Worth fixing

### 1. The ternary path escapes the trait

`TrangeFilter` and `AtrFilter` expose an inherent `next`, and `run_ternary`
takes a closure — so the two drivers share no contract, and every ternary call
site repeats the `let mut filter … |h, l, c| filter.next(h, l, c)` dance.

Generalize the trait over the input shape:

```rust
pub(crate) trait Filter {
    type Input;
    fn next(&mut self, input: Self::Input) -> Option<f64>;
}
```

with `EmaFilter::Input = Option<f64>` and
`AtrFilter::Input = (Option<f64>, Option<f64>, Option<f64>)`. `run_ternary`
becomes `run_ternary<F: Filter<Input = (…)>>` and both call sites collapse to
`run_ternary(h, l, c, "atr", filter)`. Each filter has exactly one input shape,
so an associated type beats a generic parameter.

### 2. `run_ternary` doesn't validate lengths — a latent bug

`izip!` truncates to the shortest input while the builder is sized from
`a.len()`. A length-1 input (`close=pl.lit(100.0)` broadcasts in polars, but
plugin inputs arrive un-broadcast) silently yields a one-row result instead of
an error. Add an explicit length check up front returning `ShapeMismatch`, and
decide deliberately whether length-1 broadcast should be supported.

### 3. Error plumbing is duplicated seven times

Every kernel returns `Result<Self, String>` and then
`map_err(|e| PolarsError::ComputeError(e.into()))`; every pyfunction repeats the
same four-line match into `PyRuntimeError`. Two small moves:

- have `new()` return `PolarsResult<Self>` directly
  (`polars_bail!(ComputeError: "EMA period must be > 0")`);
- add one `fn to_pyseries(r: PolarsResult<Series>) -> PyResult<PySeries>` to
  `utils.rs`.

Each pyfunction body then drops to three lines. Incidentally, `PyValueError`
fits an invalid `period` better than `PyRuntimeError`.

## Decisions to record, not defects

**Hardcoded output names** (`"ema"`, `"sma"`, …). Pleasant for
`df.with_columns(EMA(20))`, but it diverges from the polars convention of
keeping the input's name, and two EMAs over different columns in one
`with_columns` collide on name instead of producing distinct outputs. Either
choice is defensible — the point is to write down which one was made and why.

**Running-sum drift** in SMA and WMA. `sum` / `rsum` / `wsum` accumulate
floating-point error over long series with large magnitudes. Polars does the
same, so this is acceptable — but a comment beats rediscovering it later against
a reference implementation.

## Explicitly not worth doing yet

The `% self.buf.len()` in the ring buffers (a branch would be cheaper) and
`ca.iter()` versus slice iteration over a rechunked, null-free array. Both are
micro-optimizations; leave them until a benchmark asks for them.
