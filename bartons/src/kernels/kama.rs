use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use super::ker::KerFilter;
use crate::utils::{run_filter, Filter};

#[derive(Deserialize)]
pub struct KamaKwargs {
    period: i64,
    fastn: i64,
    slown: i64,
}

/// Streaming Kaufman Adaptive Moving Average filter, fed one value at a time
/// via [`Filter::next`].
///
///   alpha = (slow + KER * (fast - slow))^2
///   KAMA += alpha * (value - KAMA)
///
/// An EMA whose smoothing constant is re-derived every bar from the efficiency
/// ratio: a clean trend (KER near 1) pulls alpha towards `fast`, chop (KER near
/// 0) towards `slow`, so the average tracks closely when the move is real and
/// goes nearly flat when it is not. This is what makes KAMA a kernel rather than
/// an expression — the coefficient depends on the data, so there is no
/// `ewm_mean` form to reach for.
///
/// One [`KerFilter`] supplies the ratio. It cannot be hoisted out and passed in
/// as a precomputed series the way `CCI` takes typical price, because it is
/// stateful over time rather than elementwise — so it lives here, and
/// `bartons.indicators.KER` is the same kernel rather than a second definition
/// of the formula.
///
/// The two halves take their own family's null convention, which is the whole
/// of the divergence between them. The ratio's window resets on a null (see
/// [`KerFilter`]); the running average does not — it carries across the gap like
/// EMA and RMA, so once the ratio has warmed up again, smoothing resumes from
/// the pre-gap value instead of re-seeding. Output is null for as long as the
/// ratio is, which is `period` valid changes after the gap.
pub struct KamaFilter {
    ker: KerFilter,
    fast: f64,
    slow: f64,
    value: f64,
}

impl KamaFilter {
    pub fn new(period: i64, fastn: i64, slown: i64) -> Result<Self, String> {
        if fastn <= 0 || slown <= 0 {
            return Err("KAMA fastn and slown must be > 0".to_string());
        }
        Ok(Self {
            ker: KerFilter::new(period).map_err(|_| "KAMA period must be > 0".to_string())?,
            fast: 2.0 / (fastn as f64 + 1.0),
            slow: 2.0 / (slown as f64 + 1.0),
            value: f64::NAN,
        })
    }
}

impl Filter for KamaFilter {
    type Input = Option<f64>;
    type Output = f64;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        // Feed the ratio unconditionally — a null has to reach it, so that it
        // resets its window rather than spanning the gap.
        let ratio = self.ker.next(input)?;
        // Unreachable once the ratio is `Some`, but written as a total match
        // rather than an assertion.
        let value = input?;

        let alpha = (self.slow + ratio * (self.fast - self.slow)).powi(2);
        self.value = if self.value.is_nan() {
            value
        } else {
            self.value + alpha * (value - self.value)
        };
        Some(self.value)
    }
}

fn kama(series: &Series, period: i64, fastn: i64, slown: i64) -> PolarsResult<Series> {
    let filter =
        KamaFilter::new(period, fastn, slown).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_filter(series, "kama", filter)
}

#[polars_expr(output_type = Float64)]
fn kama_expr(inputs: &[Series], kwargs: KamaKwargs) -> PolarsResult<Series> {
    kama(&inputs[0], kwargs.period, kwargs.fastn, kwargs.slown)
}

/// Kaufman Adaptive Moving Average.
///
/// An exponential moving average whose smoothing constant is re-derived each
/// bar from the efficiency ratio, so it tracks clean trends closely and flattens
/// out in chop.
///
/// Args:
///     series: input values.
///     period: number of changes in the efficiency-ratio window (default 10).
///     fastn: period of the fast smoothing bound (default 2).
///     slown: period of the slow smoothing bound (default 30).
///
/// Returns:
///     A Float64 series; null during the warmup period.
#[pyfunction]
#[pyo3(name = "kama", signature = (series, *, period=10, fastn=2, slown=30))]
pub fn kama_py(series: PySeries, period: i64, fastn: i64, slown: i64) -> PyResult<PySeries> {
    let series: Series = series.into();
    let result = kama(&series, period, fastn, slown).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}
