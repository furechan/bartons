use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use crate::ring_buffer::RingBuffer;
use crate::utils::{run_filter, Filter};

#[derive(Deserialize)]
pub struct MadKwargs {
    period: i64,
}

/// Streaming rolling mean absolute deviation filter.
///
/// A null resets the window. Once the window is full, the result is the mean
/// of `abs(value - window_mean)` over all values in that window.
pub struct MadFilter {
    buffer: RingBuffer<f64>,
    sum: f64,
}

impl MadFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        if period <= 0 {
            return Err("MAD period must be > 0".to_string());
        }
        Ok(Self {
            buffer: RingBuffer::new(period as usize),
            sum: 0.0,
        })
    }

    /// Advance the window and return its `(mean, mad)` for a full window.
    ///
    /// The mean is the window's arithmetic mean — the same value SMA computes —
    /// and MAD is derived from it, so both fall out of one pass. [`CciFilter`]
    /// needs the pair; [`Filter::next`] keeps only the second.
    ///
    /// [`CciFilter`]: crate::kernels::cci::CciFilter
    pub fn next_stats(&mut self, input: Option<f64>) -> Option<(f64, f64)> {
        let Some(value) = input else {
            self.buffer.clear();
            self.sum = 0.0;
            return None;
        };

        if let Some(evicted) = self.buffer.push(value) {
            self.sum -= evicted;
        }
        self.sum += value;

        if !self.buffer.is_full() {
            return None;
        }

        let mean = self.sum / self.buffer.capacity() as f64;
        let deviation = self
            .buffer
            .iter()
            .map(|value| (value - mean).abs())
            .sum::<f64>();
        Some((mean, deviation / self.buffer.capacity() as f64))
    }
}

impl Filter for MadFilter {
    type Input = Option<f64>;
    type Output = f64;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        self.next_stats(input).map(|(_, mad)| mad)
    }
}

fn mad(series: &Series, period: i64) -> PolarsResult<Series> {
    let filter = MadFilter::new(period).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_filter(series, "mad", filter)
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
