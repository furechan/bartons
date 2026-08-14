# Design review: the `Filter` + driver-loop core

Review of the `Filter` trait and the `run_unary` / `run_ternary` drivers in
[bartons/src/utils.rs](../bartons/src/utils.rs), 2026-08-14. Covers all seven
indicators as they stood at that date.

**Verdict: keep the loop-over-`Filter` design.** It is the right core for this
library. Three rough edges are worth fixing, and two more are decisions to
record rather than defects to repair.

**Status:** all three items have since been acted on — see the resolution note
under each. Items 1 and 2 were implemented as proposed; item 3's pyfunction half
was implemented differently (the helper it asks for already exists upstream) and
its kernel half was deliberately declined. The recorded decisions below stand.

## Why the design holds up

**Most of these indicators are inherently sequential.** EMA, RMA, RSI and ATR
are recursive — there is no vectorized alternative being given up. And because
the drivers are generic over `F: Filter`, they monomorphize and `next` inlines:
the emitted code matches a hand-written per-indicator loop. The abstraction is
free here, which is exactly when a trait earns its place.

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

**Resolved.** Implemented as described. `AtrFilter::next` now passes the triple
straight through to its inner `TrangeFilter` rather than unpacking and
respreading it. The tuple alias ended up spelled two ways on purpose:
`utils::Triple` on the driver side, which is arity-generic and assumes nothing
about what the three series mean, and `indicators::Hlc` on the kernel side,
which does — same type, so an `Hlc` filter satisfies the `Triple` bound
directly. Going further and collapsing `run_unary` and `run_ternary` into a
single generic `run` was considered and deferred; see
[unified-run-driver.md](unified-run-driver.md).

### 2. `run_ternary` doesn't validate lengths — a latent bug

`izip!` truncates to the shortest input while the builder is sized from
`a.len()`. A length-1 input (`close=pl.lit(100.0)` broadcasts in polars, but
plugin inputs arrive un-broadcast) silently yields a one-row result instead of
an error. Add an explicit length check up front returning `ShapeMismatch`, and
decide deliberately whether length-1 broadcast should be supported.

**Resolved.** `run_ternary` opens with `check_len!(a, b, c)?` — a variadic macro
over `utils::check_lengths` — and sizes its builder from the checked length. A
mismatch raises `InvalidOperation` naming the disagreeing series and both
lengths. (The review says `ShapeMismatch`; that was the original choice, later
changed — `PyPolarsErr` maps `InvalidOperation` to the builtin `ValueError`,
while `ShapeMismatch` maps to a `ShapeError` class in a module Python cannot
import. See item 3.)

On the open question: **length-1 inputs are a mismatch, not a broadcast.** Plugin
inputs arrive un-broadcast, so `pl.lit(100.0)` as an input is now a loud error
rather than the silent one-row result it used to produce. Both behaviors are
pinned by tests (`test_mismatched_lengths_raise`,
`test_length_one_input_is_not_broadcast`), so the decision can't drift either way
unnoticed.

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

**Resolved for the pyfunction half**, though not in the shape proposed here. The
kernel half is **declined**, see below.

The `to_pyseries` helper this review asks for **was not written**:
`pyo3_polars::error::PyPolarsErr` already exists, maps 14 `PolarsError` variants
onto Python exceptions, and implements `From<_> for PyErr` — so `?` alone
replaces the four-line match, and the variant classification survives to Python
instead of being flattened by `e.to_string()`. The review missed that the
dependency already ships this.

That also reframed the `PyValueError` remark. It was never a matter of picking a
nicer exception type at the end: `PyPolarsErr` maps `InvalidOperation` to the
builtin `ValueError` automatically. What was needed was for the error to *carry*
its classification, so each `calc_*` now raises `InvalidOperation` rather than
`ComputeError` for a bad period. The chain went from
`String → ComputeError → RuntimeError`, discarding at each hop information that
was exact at the first, to `String → InvalidOperation → ValueError`, which
preserves it.

`check_lengths` was moved to `InvalidOperation` for the same reason. The literal
`ShapeMismatch` maps to a `ShapeError` whose module (`exceptions`) does not exist
as far as Python is concerned — not importable, not on `bartons.plugin`, not
`polars.exceptions.ShapeError` — so it is catchable only as bare `Exception`.
Only the variants landing on builtins (`ValueError`, `IndexError`, `IOError`,
`AssertionError`) are usable by callers.

One limit is structural: only the **eager** path benefits. Polars' plugin FFI
catches whatever a `#[polars_expr]` returns and re-wraps it, so `EMA(0)` inside a
`select` still surfaces as `polars.exceptions.ComputeError` with the message
intact, regardless of the variant. That boundary is not ours.

First, a correction: the count is **six**, not seven, for the kernel half. TRANGE
has no period to validate, so it has neither the `Result<Self, String>` nor the
`map_err`.

### The kernel error stays as it is — decided, not deferred

This review's first proposal — `polars_bail!` inside `new()` — is **rejected
outright**. It puts a polars type in every kernel constructor, discarding the
polars-independence the `String` error was introduced to buy (see the CHANGELOG
entry "Move period validation out of the kernels"). That independence is real
and still holds: no polars type appears in any filter struct or any of its
impls, and the `Filter` trait is `Option<f64>` in, `Option<f64>` out. The filters
are streaming abstractions that happen to be driven by polars, not polars
abstractions.

A middle option was considered and also declined: a local `KernelError` with
`impl From<KernelError> for PolarsError` in `utils.rs` (which compiles — the
orphan rule permits it, since the local type is the trait's parameter). That
would keep the kernels polars-free *and* let `?` collapse each
`.map_err(|e| PolarsError::ComputeError(e.into()))?` to a bare `?`.

It was declined because the explicit `map_err` is doing work: it **makes the
boundary visible**. Every crossing from kernel-land into polars-land is spelled
out where it happens. A `From` impl declares the conversion once and makes the
six crossings silent. In a design whose central claim is that the kernels are
independent, a visible seam is worth more than six lines of saved noise.

So the repetition here is deliberate. Treat it as belonging with the recorded
decisions below rather than as a defect to repair.

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
