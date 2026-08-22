use pyo3::prelude::*;
use polars::prelude::*;
use serde::Deserialize;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use pyo3_polars::derive::polars_expr;

use crate::utils::{run_filter, Filter};

#[derive(Deserialize)]
pub struct RmaKwargs {
    period: i64,
}

/// Streaming RMA (Wilder's) filter: feed one `Option<f64>` at a time via
/// [`Filter::next`].
///
/// A `None` input is skipped: it emits `None` but carries the running average
/// across the gap (matching polars/pandas `ewm` and mintalib). Output is `None`
/// during the warmup period. The first `period` values are seeded with a simple
/// average, then Wilder smoothing takes over.
pub struct RmaFilter {
    period: i64,
    alpha: f64, // Wilder smoothing factor
    value: f64,
    total: f64,
    count: i64,
}

impl RmaFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        if period <= 0 {
            return Err("RMA period must be > 0".to_string());
        }
        Ok(Self {
            period,
            alpha: 1.0 / period as f64,
            value: f64::NAN,
            total: 0.0,
            count: 0,
        })
    }
}

impl Filter for RmaFilter {
    type Input = Option<f64>;
    type Output = f64;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        // A null is skipped: emit null but carry the running state across the gap.
        let val = input?;

        self.count += 1;
        if self.count <= self.period {
            // Simple-average seeding until `period` values are accumulated.
            self.total += val;
            self.value = self.total / self.count as f64;
        } else {
            // Wilder smoothing: value += (val - value) / period.
            self.value += self.alpha * (val - self.value);
        }

        // Warmup period emits null; otherwise the running RMA value.
        (self.count >= self.period).then_some(self.value)
    }
}

fn rma(series: &Series, period: i64) -> PolarsResult<Series> {
    let filter = RmaFilter::new(period).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_filter(series, "rma", filter)
}

#[polars_expr(output_type = Float64)]
fn rma_expr(inputs: &[Series], kwargs: RmaKwargs) -> PolarsResult<Series> {
    rma(&inputs[0], kwargs.period)
}

/// Wilder's running moving average (SMMA / Wilder smoothing).
///
/// Args:
///     series: input values.
///     period: smoothing period (default 20).
///
/// Returns:
///     A Float64 series; null during the warmup period.
#[pyfunction]
#[pyo3(name = "rma", signature = (series, *, period=20))]
pub fn rma_py(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();

    let result = rma(&series, period).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}
