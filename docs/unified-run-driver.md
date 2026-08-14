# Proposal: one `run` driver via an `Inputs` trait

**Status: deferred.** Sketched 2026-08-14, not built. The trigger to revisit is a
fourth input arity — an OHLC indicator. Nothing here is a bug or a TODO; the
current two-driver design is intentional and fine at today's scale.

## The problem it solves

`rust/src/utils.rs` has two drivers doing the same job at different arities:
`run_unary` for the single-series indicators and `run_ternary` for the
three-series ones (TRANGE, ATR). Each casts to `Float64`, iterates in lockstep,
and collects into a nullable series. A third arity would mean a third near-copy.

The related asymmetry — `run_ternary` taking a closure while `run_unary` took a
`Filter` — is **already fixed**: `Filter` now carries an associated `Input`, so
both drivers bind the same trait. What remains is only the duplicated driver
body, which is a much smaller problem.

## The proposal

Carry the arity in a trait implemented once per tuple shape. This is the standard
Rust workaround for having no variadic generics — the same technique `axum` uses
to type handlers.

```rust
trait Inputs {
    type Casted;
    type Row;
    fn cast(self) -> PolarsResult<Self::Casted>;
    fn len(casted: &Self::Casted) -> usize;
    fn rows(casted: &Self::Casted) -> impl Iterator<Item = Self::Row> + '_;
}

impl Inputs for &Series {
    type Casted = Float64Chunked;
    type Row = Option<f64>;
    fn cast(self) -> PolarsResult<Float64Chunked> { f64c(self) }
    fn len(c: &Float64Chunked) -> usize { c.len() }
    fn rows(c: &Float64Chunked) -> impl Iterator<Item = Option<f64>> + '_ { c.iter() }
}

impl Inputs for (&Series, &Series, &Series) {
    type Casted = (Float64Chunked, Float64Chunked, Float64Chunked);
    type Row = Triple;
    fn cast(self) -> PolarsResult<Self::Casted> {
        check_len!(self.0, self.1, self.2)?;
        Ok((f64c(self.0)?, f64c(self.1)?, f64c(self.2)?))
    }
    fn len(c: &Self::Casted) -> usize { c.0.len() }
    fn rows(c: &Self::Casted) -> impl Iterator<Item = Triple> + '_ {
        izip!(c.0.iter(), c.1.iter(), c.2.iter())
    }
}
```

`run_unary` and `run_ternary` then collapse into one function:

```rust
pub(crate) fn run<I: Inputs, F: Filter<Input = I::Row>>(
    inputs: I,
    name: &str,
    mut filter: F,
) -> PolarsResult<Series>
```

Call sites become `run(series, "ema", filter)` and
`run((high, low, close), "atr", filter)`.

Two details that make it work:

- **`I::Row` ties the input arity to `Filter::Input`** in the type system,
  checked once at the definition. A filter of the wrong arity is a compile error
  at the call site with a normal type error, not a failure inside a macro.
- **`Casted` holds `Float64Chunked`, not `Series`.** The casted `Series` is owned
  while the `ChunkedArray` borrows from it, which would otherwise force a
  two-step cast-then-borrow dance with the driver holding the storage between.
  Storing the chunked array directly avoids that, and `ChunkedArray::clone` is
  cheap — the chunks are `Arc`'d.

Adding an arity is one impl, and the impls themselves can be macro-generated if
the count ever justifies it.

## Cost

Roughly **line-neutral**: about 45 lines, against the ~43 that `run_unary` and
`run_ternary` occupy today.

The real cost is **indirection**. Today a reader opens `run_ternary` and sees
cast, zip, build in fifteen straight lines. Afterwards they follow `I::Row` and
`I::Casted` into an impl-per-arity to answer the same question. That is the whole
argument against doing it now — not the size.

## When to revisit

When a fourth input arity appears. At that point this is clearly right: the
marginal cost of each additional arity is about ten lines, and it keeps the
contract in the type system, where the associated-`Input` refactor just put it.

Until then it buys nothing concrete — there are two arities and one of them is
the trivial case.

## Rejected en route

Recorded so they aren't re-derived.

**A slice — `run_nary(inputs: &[&Series], …)`.** Fixes collecting the inputs but
not the output side: `Filter::Input` must still be N-ary, so each row becomes
`&[Option<f64>]` gathered into a scratch buffer. Loses named destructuring
(`(high, low, close)`), loses compile-time arity, and gives up the fused-iterator
codegen the design review credited.

**A `run_nary!` macro** expanding the whole driver body inline, the way `izip!`
does. This genuinely works, and the non-obvious part is worth keeping: capture
the inputs as `$s:ident` rather than `expr` and shadow each in place —

```rust
$( let $s = $s.cast(&DataType::Float64)?; )+
$( let $s = $s.f64()?;                    )+
```

— which sidesteps `macro_rules!` having no gensym, since you reuse the caller's
identifiers instead of inventing names. Rejected because the `Filter` bound stops
being a checked contract and becomes a typecheck inside macro expansion, errors
point into generated code, and the driver stops being a documentable function
with a signature.

**Typed arrays (`&Float64Chunked`) as the driver's input** instead of `&Series`.
Simplifies the trait, but relocates the cast into all seven `calc_*` kernels
rather than removing it — the same call-site repetition, moved — and scatters a
documented, tested behavior (`test_integer_input_is_cast`) across seven places
where it can drift. Going further to `&[f64]` would need rechunking and lose the
null bitmap.
