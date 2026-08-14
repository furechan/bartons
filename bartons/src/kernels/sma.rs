use pyo3::prelude::*;
use polars::prelude::*;
use serde::Deserialize;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use pyo3_polars::derive::polars_expr;

use crate::utils::{run_unary, Filter};

#[derive(Deserialize)]
pub struct SmaKwargs {
    period: i64,
}

/// Streaming SMA filter: feed one `Option<f64>` at a time via [`Filter::next`].
///
/// A `None` input breaks the current run (gap reset); output is `None` during
/// the warmup period, then the rolling mean over the last `period` values.
pub struct SmaFilter {
    period: i64,
    buf: Vec<f64>, // ring buffer of the current run's window
    idx: usize,    // next write slot == oldest element once full
    count: i64,
    sum: f64,
}

impl SmaFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        if period <= 0 {
            return Err("SMA period must be > 0".to_string());
        }
        Ok(Self {
            period,
            buf: vec![0.0; period as usize],
            idx: 0,
            count: 0,
            sum: 0.0,
        })
    }
}

impl Filter for SmaFilter {
    type Input = Option<f64>;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        // A null breaks the current run: reset and emit null.
        let Some(val) = input else {
            self.count = 0;
            self.sum = 0.0;
            self.idx = 0;
            return None;
        };

        if self.count >= self.period {
            self.sum -= self.buf[self.idx]; // evict the oldest value
        } else {
            self.count += 1;
        }
        self.sum += val;
        self.buf[self.idx] = val;
        self.idx = (self.idx + 1) % self.buf.len();

        // Warmup period emits null; otherwise the rolling mean.
        (self.count >= self.period).then_some(self.sum / self.period as f64)
    }
}

fn sma(series: &Series, period: i64) -> PolarsResult<Series> {
    let filter = SmaFilter::new(period).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_unary(series, "sma", filter)
}

#[polars_expr(output_type = Float64)]
fn sma_expr(inputs: &[Series], kwargs: SmaKwargs) -> PolarsResult<Series> {
    sma(&inputs[0], kwargs.period)
}

/// Simple moving average.
///
/// Args:
///     series: input values.
///     period: window length (default 20).
///
/// Returns:
///     A Float64 series; null during the warmup period.
#[pyfunction]
#[pyo3(name = "sma", signature = (series, *, period=20))]
pub fn sma_py(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();

    let result = sma(&series, period).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}
