use itertools::izip;
use polars::prelude::*;
use polars_arrow::array::PrimitiveArray;

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

/// Three values from one row — the [`Filter::Input`] of the three-series
/// indicators, fed as a single value so they share the single-series filters'
/// contract.
///
/// Named by arity because the drivers here are: nothing in this module assumes
/// what the three series mean. The indicator layer aliases it to
/// `kernels::Hlc`, which is what the kernels that consume it actually say.
pub(crate) type Triple = (Option<f64>, Option<f64>, Option<f64>);

/// A streaming filter: fed one [`Self::Input`] at a time, emitting one
/// `Option<f64>` per input. The input is a plain `Option<f64>` for the
/// single-series indicators and a [`Triple`] for the three-series ones.
///
/// Implementors own their warmup and null semantics. A `None` output is emitted
/// while warming up; on a `None` input the recursive filters (EMA, RMA) skip —
/// emitting `None` but carrying their running state across the gap — while the
/// windowed filters (SMA, WMA) reset the window.
pub(crate) trait Filter {
    type Input;

    fn next(&mut self, input: Self::Input) -> Option<f64>;
}

/// A cursor over a `Float64Chunked` that downcasts each Arrow chunk once,
/// rather than re-entering `ChunkedArray`'s flattened iterator per element.
struct ChunkCursor<'a> {
    parts: Vec<&'a PrimitiveArray<f64>>,
    chunk: usize,
    offset: usize,
    remaining: usize,
}

/// Private extension trait for the drivers' copy-free chunk traversal.
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

        // SAFETY: the loop above establishes that `index` is in bounds.
        Some(unsafe { self.parts[self.chunk].get_unchecked(index) })
    }

    #[inline]
    fn size_hint(&self) -> (usize, Option<usize>) {
        (self.remaining, Some(self.remaining))
    }
}

impl ExactSizeIterator for ChunkCursor<'_> {}

/// Drive a single-series [`Filter`] over a series.
///
/// Casts the input to `Float64`, feeds each `Option<f64>` to the filter, and
/// collects the `Option<f64>` outputs into a nullable `Float64` series, with
/// `None` outputs becoming nulls.
pub(crate) fn run_unary<F: Filter<Input = Option<f64>>>(
    series: &Series,
    name: &str,
    mut filter: F,
) -> PolarsResult<Series> {
    let series = series.cast(&DataType::Float64)?;
    let ca = series.f64()?;
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new(name.into(), ca.len());

    for opt_val in ca.fast_iter() {
        match filter.next(opt_val) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }

    Ok(builder.finish().into_series())
}

/// Drive a [`Triple`]-input [`Filter`] over three aligned series.
///
/// Checks that the three inputs agree on length, casts each to `Float64`, feeds
/// the per-row [`Triple`] to the filter, and collects the `Option<f64>` outputs
/// into a nullable `Float64` series, with `None` outputs becoming nulls.
///
/// The length check is not decorative: `izip!` stops at the shortest input, so
/// without it a mismatch would silently yield a short result.
pub(crate) fn run_ternary<F: Filter<Input = Triple>>(
    a: &Series,
    b: &Series,
    c: &Series,
    name: &str,
    mut filter: F,
) -> PolarsResult<Series> {
    let len = check_len!(a, b, c)?;

    let a = a.cast(&DataType::Float64)?;
    let b = b.cast(&DataType::Float64)?;
    let c = c.cast(&DataType::Float64)?;
    let a = a.f64()?;
    let b = b.f64()?;
    let c = c.f64()?;
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new(name.into(), len);

    for triple in izip!(a.fast_iter(), b.fast_iter(), c.fast_iter()) {
        match filter.next(triple) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }

    Ok(builder.finish().into_series())
}
