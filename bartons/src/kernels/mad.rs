use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use crate::utils::{run_unary, Filter};

#[derive(Deserialize)]
pub struct MadKwargs {
    period: i64,
}

/// Streaming rolling mean absolute deviation filter.
///
/// A null resets the window. Once the window is full, the result is the mean
/// of `abs(value - window_mean)` over all values in that window.
pub struct MadFilter {
    period: i64,
    buf: Vec<f64>,
    idx: usize,
    count: i64,
    sum: f64,
}

impl MadFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        if period <= 0 {
            return Err("MAD period must be > 0".to_string());
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

impl Filter for MadFilter {
    type Input = Option<f64>;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        let Some(value) = input else {
            self.idx = 0;
            self.count = 0;
            self.sum = 0.0;
            return None;
        };

        if self.count < self.period {
            self.count += 1;
        } else {
            self.sum -= self.buf[self.idx];
        }
        self.sum += value;
        self.buf[self.idx] = value;
        self.idx += 1;
        if self.idx == self.buf.len() {
            self.idx = 0;
        }

        if self.count < self.period {
            return None;
        }

        let mean = self.sum / self.period as f64;
        let deviation = self
            .buf
            .iter()
            .map(|value| (value - mean).abs())
            .sum::<f64>();
        Some(deviation / self.period as f64)
    }
}

fn mad(series: &Series, period: i64) -> PolarsResult<Series> {
    let filter = MadFilter::new(period).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_unary(series, "mad", filter)
}

#[polars_expr(output_type = Float64)]
fn mad_expr(inputs: &[Series], kwargs: MadKwargs) -> PolarsResult<Series> {
    mad(&inputs[0], kwargs.period)
}

/// Rolling mean absolute deviation.
///
/// Args:
///     series: input values.
///     period: window length (default 20).
///
/// Returns:
///     A Float64 series; null during the warmup period.
#[pyfunction]
#[pyo3(name = "mad", signature = (series, *, period=20))]
pub fn mad_py(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();
    let result = mad(&series, period).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}
