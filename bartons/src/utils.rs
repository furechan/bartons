use itertools::izip;
use polars::prelude::*;
use polars_arrow::array::{BooleanArray, PrimitiveArray};

/// Check that every input series has the same length, returning that length.
///
/// `check_len!(a, b, c)?` yields the shared length, or an `InvalidOperation`
/// naming the first series that disagrees. Variadic sugar over [`check_lengths`],
/// which holds the actual logic.
macro_rules! check_len {
    ($($series:expr),+ $(,)?) => {
        $crate::utils::check_lengths(&[$($series),+])
    };
}

/// The body of [`check_len!`]: all inputs must agree on length.
///
/// Plugin inputs arrive un-broadcast, so a length-1 series is a genuine
/// mismatch rather than a scalar to stretch — `pl.lit(100.0)` as an input is an
/// error here, not a broadcast.
///
/// Raises `InvalidOperation`, not the more literal `ShapeMismatch`, because
/// `PyPolarsErr` maps the former to Python's builtin `ValueError` and the latter
/// to a `ShapeError` class that lives in a module Python cannot import — so it
/// would be catchable only as bare `Exception`. Nothing but the Python boundary
/// reads these variants, and the expression path flattens them anyway.
pub(crate) fn check_lengths(inputs: &[&Series]) -> PolarsResult<usize> {
    let Some((first, rest)) = inputs.split_first() else {
        return Ok(0);
    };

    let len = first.len();
    for series in rest {
        if series.len() != len {
            polars_bail!(
                InvalidOperation:
                "input lengths differ: '{}' has {} rows but '{}' has {}",
                first.name(), len, series.name(), series.len()
            );
        }
    }

    Ok(len)
}

/// A streaming filter: fed one [`Self::Input`] at a time, emitting one optional
/// [`Self::Output`] per input. Today the row is a plain `Option<f64>` for the
/// single-series indicators, or an explicit tuple for multi-series indicators.
///
/// Implementors own their warmup and null semantics. A `None` output is emitted
/// while warming up; on a `None` input the recursive filters (EMA, RMA) skip —
/// emitting `None` but carrying their running state across the gap — while the
/// windowed filters (SMA, WMA) reset the window.
pub(crate) trait Filter {
    type Input;
    type Output;

    fn next(&mut self, input: Self::Input) -> Option<Self::Output>;
}

/// A filter row type that knows which typed Polars sources produce it.
///
/// Implementations bind three things in one place: the exact source arity, the
/// casts needed to own those sources at their working dtype, and the row shape
/// passed to [`Filter::next`]. This keeps both arity and element types checked
/// at compile time without teaching the driver every possible combination.
pub(crate) trait FilterInput: Sized {
    type Sources<'a>;
    type Casted;

    fn cast(sources: Self::Sources<'_>) -> PolarsResult<Self::Casted>;
    fn len(casted: &Self::Casted) -> usize;
    fn for_each(casted: &Self::Casted, emit: impl FnMut(Self));
}

/// A filter value type that knows how to build its nullable Polars output.
pub(crate) trait FilterOutput: Sized {
    type Builder;

    fn builder(name: &str, capacity: usize) -> Self::Builder;
    fn append(builder: &mut Self::Builder, value: Option<Self>);
    fn finish(builder: Self::Builder) -> Series;
}

impl FilterInput for Option<f64> {
    type Sources<'a> = &'a Series;
    type Casted = Float64Chunked;

    fn cast(series: Self::Sources<'_>) -> PolarsResult<Self::Casted> {
        Ok(series.cast(&DataType::Float64)?.f64()?.clone())
    }

    fn len(casted: &Self::Casted) -> usize {
        casted.len()
    }

    fn for_each(casted: &Self::Casted, emit: impl FnMut(Self)) {
        fast_iter(casted).for_each(emit);
    }
}

impl FilterInput for Option<bool> {
    type Sources<'a> = &'a Series;
    type Casted = BooleanChunked;

    fn cast(series: Self::Sources<'_>) -> PolarsResult<Self::Casted> {
        if series.dtype() != &DataType::Boolean {
            polars_bail!(
                InvalidOperation:
                "filter input must be Boolean, got {} for series '{}'",
                series.dtype(), series.name()
            );
        }
        Ok(series.bool()?.clone())
    }

    fn len(casted: &Self::Casted) -> usize {
        casted.len()
    }

    fn for_each(casted: &Self::Casted, emit: impl FnMut(Self)) {
        casted
            .downcast_iter()
            .flat_map(BooleanArray::iter)
            .for_each(emit);
    }
}

impl FilterInput for (Option<f64>, Option<f64>) {
    type Sources<'a> = (&'a Series, &'a Series);
    type Casted = (Float64Chunked, Float64Chunked);

    fn cast((a, b): Self::Sources<'_>) -> PolarsResult<Self::Casted> {
        check_len!(a, b)?;
        Ok((
            a.cast(&DataType::Float64)?.f64()?.clone(),
            b.cast(&DataType::Float64)?.f64()?.clone(),
        ))
    }

    fn len(casted: &Self::Casted) -> usize {
        casted.0.len()
    }

    fn for_each(casted: &Self::Casted, mut emit: impl FnMut(Self)) {
        for pair in izip!(fast_iter(&casted.0), fast_iter(&casted.1)) {
            emit(pair);
        }
    }
}

impl FilterInput for (Option<f64>, Option<f64>, Option<f64>) {
    type Sources<'a> = (&'a Series, &'a Series, &'a Series);
    type Casted = (Float64Chunked, Float64Chunked, Float64Chunked);

    fn cast((a, b, c): Self::Sources<'_>) -> PolarsResult<Self::Casted> {
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

    fn for_each(casted: &Self::Casted, mut emit: impl FnMut(Self)) {
        for triple in izip!(
            fast_iter(&casted.0),
            fast_iter(&casted.1),
            fast_iter(&casted.2)
        ) {
            emit(triple);
        }
    }
}

impl FilterOutput for f64 {
    type Builder = PrimitiveChunkedBuilder<Float64Type>;

    fn builder(name: &str, capacity: usize) -> Self::Builder {
        PrimitiveChunkedBuilder::new(name.into(), capacity)
    }

    fn append(builder: &mut Self::Builder, value: Option<Self>) {
        match value {
            Some(value) => builder.append_value(value),
            None => builder.append_null(),
        }
    }

    fn finish(builder: Self::Builder) -> Series {
        builder.finish().into_series()
    }
}

impl FilterOutput for i64 {
    type Builder = PrimitiveChunkedBuilder<Int64Type>;

    fn builder(name: &str, capacity: usize) -> Self::Builder {
        PrimitiveChunkedBuilder::new(name.into(), capacity)
    }

    fn append(builder: &mut Self::Builder, value: Option<Self>) {
        match value {
            Some(value) => builder.append_value(value),
            None => builder.append_null(),
        }
    }

    fn finish(builder: Self::Builder) -> Series {
        builder.finish().into_series()
    }
}

/// Drive a typed streaming filter over its exact Polars source shape.
pub(crate) fn run_filter<F>(
    sources: <F::Input as FilterInput>::Sources<'_>,
    name: &str,
    mut filter: F,
) -> PolarsResult<Series>
where
    F: Filter,
    F::Input: FilterInput,
    F::Output: FilterOutput,
{
    let casted = F::Input::cast(sources)?;
    let mut builder = F::Output::builder(name, F::Input::len(&casted));

    F::Input::for_each(&casted, |row| {
        F::Output::append(&mut builder, filter.next(row));
    });

    Ok(F::Output::finish(builder))
}

/// Iterate any numeric ChunkedArray through its concrete Arrow arrays.
///
/// Keeping `Option::copied` outside the Arrow validity iterator avoids the
/// slower generic `StaticArray::iter` shape used by `ChunkedArray::iter` while
/// remaining safe and fully general across unaligned chunk boundaries.
fn fast_iter<T>(values: &ChunkedArray<T>) -> impl Iterator<Item = Option<T::Native>> + '_
where
    T: PolarsNumericType,
{
    values
        .downcast_iter()
        .flat_map(|array| PrimitiveArray::<T::Native>::iter(array).map(|value| value.copied()))
}
