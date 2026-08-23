use pyo3::prelude::*;
use polars::prelude::*;
use serde::Deserialize;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use pyo3_polars::derive::polars_expr;

use crate::ring_buffer::RingBuffer;
use crate::utils::{run_filter, Filter};

#[derive(Deserialize)]
pub struct WmaKwargs {
    period: i64,
}

/// Streaming WMA filter: feed one `Option<f64>` at a time via [`Filter::next`].
///
/// A `None` input breaks the current run (gap reset); output is `None` during
/// the warmup period, then the linearly-weighted mean (oldest weight 1 ..
/// newest weight `period`).
pub struct WmaFilter {
    denom: f64,    // sum of weights 1..period
    buffer: RingBuffer<f64>,
    rsum: f64, // running simple sum of the window
    wsum: f64, // running weighted sum (oldest weight 1 .. newest weight period)
}

impl WmaFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        if period <= 0 {
            return Err("WMA period must be > 0".to_string());
        }
        Ok(Self {
            denom: period as f64 * (period as f64 + 1.0) / 2.0,
            buffer: RingBuffer::new(period as usize),
            rsum: 0.0,
            wsum: 0.0,
        })
    }
}

impl Filter for WmaFilter {
    type Input = Option<f64>;
    type Output = f64;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        // A null breaks the current run: reset and emit null.
        let Some(val) = input else {
            self.rsum = 0.0;
            self.wsum = 0.0;
            self.buffer.clear();
            return None;
        };

        match self.buffer.push(val) {
            None => {
                let weight = self.buffer.count() as f64;
                self.rsum += val;
                self.wsum += weight * val;
            }
            Some(evicted) => {
                // Slide the full window: drop one from every existing weight,
                // evict the oldest, and add the new value with the full weight.
                self.wsum += self.buffer.capacity() as f64 * val - self.rsum;
                self.rsum += val - evicted;
            }
        }

        // Warmup period emits null; otherwise the weighted mean.
        self.buffer.is_full().then_some(self.wsum / self.denom)
    }
}

fn wma(series: &Series, period: i64) -> PolarsResult<Series> {
    let filter = WmaFilter::new(period).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_filter(series, "wma", filter)
}

#[polars_expr(output_type = Float64)]
fn wma_expr(inputs: &[Series], kwargs: WmaKwargs) -> PolarsResult<Series> {
    wma(&inputs[0], kwargs.period)
}

/// Weighted moving average (linearly weighted).
///
/// Args:
///     series: input values.
///     period: window length (default 20).
///
/// Returns:
///     A Float64 series; null during the warmup period.
#[pyfunction]
#[pyo3(name = "wma", signature = (series, *, period=20))]
pub fn wma_py(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();

    let result = wma(&series, period).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}
