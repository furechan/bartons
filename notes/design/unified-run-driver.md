# Typed `run_filter` driver

**Status: implemented.** SAR added the third distinct input shape to the kernel layer: unary float, binary float, and ternary float. Rather than add a third copy of the driver loop, it introduced the typed `run_filter` design below. SAR exercised it first, TRANGE and ATR followed through the float-triple implementation, and the unary kernels now use it through `Option<f64>`. The former arity-specific drivers are gone.

## Contract

`Filter` declares the type of one input row and one output value:

```rust
pub(crate) trait Filter {
    type Input;
    type Output;

    fn next(&mut self, input: Self::Input) -> Option<Self::Output>;
}
```

Those associated types select two adapters. `FilterInput` maps an exact Polars source signature to the rows accepted by `next`; `FilterOutput` maps emitted values to a nullable Polars series.

```rust
pub(crate) trait FilterInput: Sized {
    type Sources<'a>;
    type Casted;

    fn cast(sources: Self::Sources<'_>) -> PolarsResult<Self::Casted>;
    fn len(casted: &Self::Casted) -> usize;
    fn for_each(casted: &Self::Casted, emit: impl FnMut(Self));
}

pub(crate) trait FilterOutput: Sized {
    type Builder;

    fn builder(name: &str, capacity: usize) -> Self::Builder;
    fn append(builder: &mut Self::Builder, value: Option<Self>);
    fn finish(builder: Self::Builder) -> Series;
}
```

The row type is the dispatch key. SAR declares:

```rust
impl Filter for SarFilter {
    type Input = (Option<f64>, Option<f64>);
    type Output = f64;
}
```

That selects an implementation whose source signature is exactly `(&Series, &Series)`, not a dynamically checked `&[&Series]`:

```rust
impl FilterInput for (Option<f64>, Option<f64>) {
    type Sources<'a> = (&'a Series, &'a Series);
    type Casted = (Float64Chunked, Float64Chunked);
    // ...
}
```

Consequently the call site preserves the kernel's arity:

```rust
run_filter((high, low), "sar", filter)
```

Passing one or three series to that filter is a compile-time type error.

## Why the traits specialize on row types

The original proposal implemented `Inputs` on `&Series` and hard-coded both rows and outputs to `f64`. That generalized arity but not dtype. A future streak filter should be able to declare `Input = Option<bool>` and `Output = i64`; those types should select Boolean input traversal and an Int64 output builder without changing the driver.

Implementing `FilterInput` on the row signature handles arity and dtype together:

```rust
Option<f64>                              // one numeric source
Option<bool>                             // one Boolean source
(Option<f64>, Option<f64>)               // two numeric sources
(Option<f64>, Option<f64>, Option<f64>)  // three numeric sources
```

Only combinations used by real filters need implementations. There is no matrix of every theoretical dtype and arity.

Each signature currently has one conversion policy. For example, `Option<f64>` means numeric inputs are cast to Float64. If two filters someday need different policies for the same row type, introduce an explicit marker row type rather than adding runtime flags.

## Staged rollout

The completed rollout provides:

- `FilterInput for Option<f64>`, used by all unary float filters;
- `FilterInput for (Option<f64>, Option<f64>)`, used only by SAR;
- `FilterInput` for the float triple, used by TRANGE and ATR;
- `FilterOutput for f64`;
- one `run_filter` driver used by every filter.

Future extensions are demand-driven:

STREAK subsequently added `FilterInput for Option<bool>` and `FilterOutput for
i64`, validating that the driver generalizes across dtype as well as arity.
Future filters should add only the concrete mixed-type or higher-arity input
signatures required by real kernels.

## Rejected shapes

**A slice of series.** `&[&Series]` makes arity a runtime property, requires an arity check, and weakens call-site errors. The generic associated `Sources` type preserves the exact source signature instead.

**Implementing the trait on source containers.** `impl Inputs for &Series` cannot express multiple extraction types for the same source cleanly. The filter's row type is already the required dispatch key.

**A variadic driver macro.** It can generate specialized loops, but type errors point into macro expansion and the driver stops being a normal function with a documentable contract.

**Dynamic row values.** Slices or `AnyValue` would support arbitrary mixtures but lose named tuple destructuring and the static, allocation-free path through the filter.
