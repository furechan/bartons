use polars::prelude::*;
use itertools::izip;

/// Three values from one row — the [`Filter::Input`] of the three-series
/// indicators, fed as a single value so they share the single-series filters'
/// contract.
///
/// Named by arity because the drivers here are: nothing in this module assumes
/// what the three series mean. The indicator layer aliases it to
/// `indicators::Hlc`, which is what the kernels that consume it actually say.
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

    for opt_val in ca.iter() {
        match filter.next(opt_val) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }

    Ok(builder.finish().into_series())
}

/// Drive a [`Triple`]-input [`Filter`] over three aligned series.
///
/// Casts each input to `Float64`, feeds the per-row [`Triple`] to the filter,
/// and collects the `Option<f64>` outputs into a nullable `Float64` series, with
/// `None` outputs becoming nulls.
pub(crate) fn run_ternary<F: Filter<Input = Triple>>(
    a: &Series,
    b: &Series,
    c: &Series,
    name: &str,
    mut filter: F,
) -> PolarsResult<Series> {
    let a = a.cast(&DataType::Float64)?;
    let b = b.cast(&DataType::Float64)?;
    let c = c.cast(&DataType::Float64)?;
    let a = a.f64()?;
    let b = b.f64()?;
    let c = c.f64()?;
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new(name.into(), a.len());

    for triple in izip!(a.iter(), b.iter(), c.iter()) {
        match filter.next(triple) {
            Some(v) => builder.append_value(v),
            None => builder.append_null(),
        }
    }

    Ok(builder.finish().into_series())
}
