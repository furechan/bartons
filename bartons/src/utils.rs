use polars::prelude::*;
use itertools::izip;

/// A streaming unary filter: fed one `Option<f64>` at a time, emitting one
/// `Option<f64>` per input.
///
/// Implementors own their warmup and null-reset semantics. By convention a
/// `None` input breaks the current run (gap reset), and a `None` output is
/// emitted while warming up.
pub(crate) trait Filter {
    fn next(&mut self, input: Option<f64>) -> Option<f64>;
}

/// Drive a unary [`Filter`] over a series.
///
/// Casts the input to `Float64`, feeds each `Option<f64>` to the filter, and
/// collects the `Option<f64>` outputs into a nullable `Float64` series, with
/// `None` outputs becoming nulls.
pub(crate) fn run_unary<F: Filter>(
    series: &Series,
    name: &str,
    mut filter: F,
) -> PolarsResult<Series> {
    let series = series.cast(&DataType::Float64)?;
    let ca = series.f64()?;
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new(name.into(), ca.len());

    for opt_val in ca.iter() {
        match filter.next(opt_val) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }

    Ok(builder.finish().into_series())
}

/// Drive a ternary streaming filter over three aligned series.
///
/// Casts each input to `Float64`, feeds the per-row `(Option<f64>, Option<f64>,
/// Option<f64>)` triples to `step`, and collects the `Option<f64>` outputs into
/// a nullable `Float64` series, with `None` outputs becoming nulls. The `step`
/// closure owns all per-row and cross-row state.
pub(crate) fn run_ternary(
    a: &Series,
    b: &Series,
    c: &Series,
    name: &str,
    mut step: impl FnMut(Option<f64>, Option<f64>, Option<f64>) -> Option<f64>,
) -> PolarsResult<Series> {
    let a = a.cast(&DataType::Float64)?;
    let b = b.cast(&DataType::Float64)?;
    let c = c.cast(&DataType::Float64)?;
    let a = a.f64()?;
    let b = b.f64()?;
    let c = c.f64()?;
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new(name.into(), a.len());

    for (oa, ob, oc) in izip!(a.iter(), b.iter(), c.iter()) {
        match step(oa, ob, oc) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }

    Ok(builder.finish().into_series())
}
