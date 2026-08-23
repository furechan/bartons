use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use crate::ring_buffer::RingBuffer;
use crate::utils::{run_filter, Filter};

#[derive(Deserialize)]
pub struct AlmaKwargs {
    period: i64,
    offset: f64,
    sigma: f64,
}

/// Streaming Arnaud Legoux Moving Average filter.
///
/// Gaussian weights are computed and normalized once at construction. Each
/// full window is then a dot product in chronological order. A null resets the
/// fixed window and restarts warmup.
pub struct AlmaFilter {
    buffer: RingBuffer<f64>,
    weights: Vec<f64>,
}

impl AlmaFilter {
    pub fn new(period: i64, offset: f64, sigma: f64) -> Result<Self, String> {
        if period <= 0 {
            return Err("ALMA period must be > 0".to_string());
        }
        if !offset.is_finite() {
            return Err("ALMA offset must be finite".to_string());
        }
        if !sigma.is_finite() || sigma <= 0.0 {
            return Err("ALMA sigma must be finite and > 0".to_string());
        }

        let period = period as usize;
        let center = offset * (period - 1) as f64;
        let width = period as f64 / sigma;
        let mut weights: Vec<_> = (0..period)
            .map(|index| {
                let distance = index as f64 - center;
                (-distance * distance / (2.0 * width * width)).exp()
            })
            .collect();
        let total: f64 = weights.iter().sum();
        if total == 0.0 {
            return Err("ALMA weights underflowed; offset or sigma is too large".to_string());
        }
        for weight in &mut weights {
            *weight /= total;
        }

        Ok(Self {
            buffer: RingBuffer::new(period),
            weights,
        })
    }
}

impl Filter for AlmaFilter {
    type Input = Option<f64>;
    type Output = f64;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        let Some(value) = input else {
            self.buffer.clear();
            return None;
        };

        self.buffer.push(value);
        self.buffer.is_full().then(|| {
            self.buffer
                .iter()
                .zip(&self.weights)
                .map(|(value, weight)| value * weight)
                .sum()
        })
    }
}

fn alma(series: &Series, period: i64, offset: f64, sigma: f64) -> PolarsResult<Series> {
    let filter = AlmaFilter::new(period, offset, sigma)
        .map_err(|error| PolarsError::InvalidOperation(error.into()))?;
    run_filter(series, "alma", filter)
}

#[polars_expr(output_type = Float64)]
fn alma_expr(inputs: &[Series], kwargs: AlmaKwargs) -> PolarsResult<Series> {
    alma(&inputs[0], kwargs.period, kwargs.offset, kwargs.sigma)
}

/// Arnaud Legoux Moving Average.
///
/// Args:
///     series: input values.
///     period: Gaussian window length (default 9).
///     offset: Gaussian center within the window (default 0.85).
///     sigma: Gaussian shape parameter (default 6.0).
///
/// Returns:
///     A Float64 series; null during warmup and after a null resets the window.
#[pyfunction]
#[pyo3(name = "alma", signature = (series, *, period=9, offset=0.85, sigma=6.0))]
pub fn alma_py(series: PySeries, period: i64, offset: f64, sigma: f64) -> PyResult<PySeries> {
    let series: Series = series.into();
    let result = alma(&series, period, offset, sigma).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn weights_are_normalized_once() {
        let filter = AlmaFilter::new(9, 0.85, 6.0).unwrap();
        assert!((filter.weights.iter().sum::<f64>() - 1.0).abs() < 1e-15);
    }
}
