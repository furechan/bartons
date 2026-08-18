# Proposal: one `run_filter` driver via an `Inputs` trait

**Status: deferred.** Sketched 2026-08-14, not built. The trigger to revisit is a
fourth input arity — an OHLC indicator. Nothing here is a bug or a TODO; the
current two-driver design is intentional and fine at today's scale.

## The problem it solves

`bartons/src/utils.rs` has two drivers doing the same job at different arities:
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
use polars_arrow::array::PrimitiveArray;

pub(crate) trait Inputs {
    type Casted;
    type Row;

    fn cast(self) -> PolarsResult<Self::Casted>;
    fn len(casted: &Self::Casted) -> usize;
    fn for_each(
        casted: &Self::Casted,
        emit: impl FnMut(Self::Row),
    );
}

impl Inputs for &Series {
    type Casted = Float64Chunked;
    type Row = Option<f64>;

    fn cast(self) -> PolarsResult<Self::Casted> {
        Ok(self.cast(&DataType::Float64)?.f64()?.clone())
    }

    fn len(casted: &Self::Casted) -> usize {
        casted.len()
    }

    fn for_each(
        casted: &Self::Casted,
        emit: impl FnMut(Self::Row),
    ) {
        casted.iter().for_each(emit);
    }
}

/// A copy-free cursor that hoists the Arrow downcast once per chunk.
struct ChunkCursor<'a> {
    parts: Vec<&'a PrimitiveArray<f64>>,
    chunk: usize,
    offset: usize,
    left: usize,
}

trait FastIter {
    fn fast_iter(&self) -> ChunkCursor<'_>;
}

impl FastIter for Float64Chunked {
    fn fast_iter(&self) -> ChunkCursor<'_> {
        ChunkCursor {
            parts: self.downcast_iter().collect(),
            chunk: 0,
            offset: 0,
            left: self.len(),
        }
    }
}

impl Iterator for ChunkCursor<'_> {
    type Item = Option<f64>;

    #[inline]
    fn next(&mut self) -> Option<Self::Item> {
        if self.left == 0 {
            return None;
        }
        self.left -= 1;

        while self.offset >= self.parts[self.chunk].len() {
            self.chunk += 1;
            self.offset = 0;
        }

        let index = self.offset;
        self.offset += 1;

        // SAFETY: the loop above establishes that `index` is in bounds.
        Some(unsafe { self.parts[self.chunk].get_unchecked(index) })
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        (self.left, Some(self.left))
    }
}

impl Inputs for (&Series, &Series, &Series) {
    type Casted = (
        Float64Chunked,
        Float64Chunked,
        Float64Chunked,
    );
    type Row = Triple;

    fn cast(self) -> PolarsResult<Self::Casted> {
        let (a, b, c) = self;
        check_len!(a, b, c)?;

        Ok((
            a.cast(&DataType::Float64)?.f64()?.clone(),
            b.cast(&DataType::Float64)?.f64()?.clone(),
            c.cast(&DataType::Float64)?.f64()?.clone(),
        ))
    }

    fn len(casted: &Self::Casted) -> usize {
        casted.0.len()
    }

    fn for_each(
        casted: &Self::Casted,
        mut emit: impl FnMut(Self::Row),
    ) {
        let (a, b, c) = casted;

        for row in izip!(a.fast_iter(), b.fast_iter(), c.fast_iter()) {
            emit(row);
        }
    }
}
```

`run_unary` and `run_ternary` then collapse into one function:

```rust
pub(crate) fn run_filter<I: Inputs, F: Filter<Input = I::Row>>(
    inputs: I,
    name: &str,
    mut filter: F,
) -> PolarsResult<Series> {
    let casted = inputs.cast()?;
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new(
        name.into(),
        I::len(&casted),
    );

    I::for_each(&casted, |row| {
        match filter.next(row) {
            Some(value) => builder.append_value(value),
            None => builder.append_null(),
        }
    });

    Ok(builder.finish().into_series())
}
```

Call sites become `run_filter(series, "ema", filter)` and
`run_filter((high, low, close), "atr", filter)`.

Two details that make it work:

- **`I::Row` ties the input arity to `Filter::Input`** in the type system,
  checked once at the definition. A filter of the wrong arity is a compile error
  at the call site with a normal type error, not a failure inside a macro.
- **`Casted` holds `Float64Chunked`, not `Series`.** The casted `Series` is owned
  while the `ChunkedArray` borrows from it, which would otherwise force a
  two-step cast-then-borrow dance with the driver holding the storage between.
  Storing the chunked array directly avoids that, and `ChunkedArray::clone` is
  cheap — the chunks are `Arc`'d.
- **`for_each` lets an input shape choose its traversal.** The ternary
  implementation uses the same copy-free `FastIter` extension as today's
  drivers. A separate direct-index single-chunk branch remains deliberately
  out of scope; there is one traversal implementation for now.

Adding an arity is one impl, and the impls themselves can be macro-generated if
the count ever justifies it.

## Cost

With the ownership conversion and fast cursor written out explicitly, this is
a meaningful source increase over the two current drivers. Most of that is the
shared `ChunkCursor`, not the arity abstraction. Each additional arity after
that adds only its `Inputs` implementation rather than another copy of the
output loop.

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
Simplifies the trait, but relocates the cast into all seven kernels
rather than removing it — the same call-site repetition, moved — and scatters a
documented, tested behavior (`test_integer_input_is_cast`) across seven places
where it can drift. Going further to `&[f64]` would need rechunking and lose the
null bitmap.
