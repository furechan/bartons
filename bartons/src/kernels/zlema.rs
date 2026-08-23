use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use crate::kernels::ema::EmaFilter;
use crate::ring_buffer::RingBuffer;
use crate::utils::{run_filter, Filter};

#[derive(Deserialize)]
pub struct ZlemaKwargs {
    period: i64,
}

/// Fused zero-lag EMA: EMA of `src + (src - src[lag])`.
pub struct ZlemaFilter {
    lag: usize,
    buffer: RingBuffer<f64>,
    ema: EmaFilter,
}

impl ZlemaFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        if period <= 0 {
            return Err("ZLEMA period must be > 0".to_string());
        }
        let lag = ((period - 1) / 2) as usize;
        Ok(Self {
            lag,
            // Periods 1 and 2 have zero lag and bypass this storage.
            buffer: RingBuffer::new(lag.max(1)),
            ema: EmaFilter::new(period)?,
        })
    }
}

impl Filter for ZlemaFilter {
    type Input = Option<f64>;
    type Output = f64;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        let adjusted = match input {
            None => {
                self.buffer.clear();
                None
            }
            Some(value) if self.lag == 0 => Some(value),
            Some(value) => self
                .buffer
                .push(value)
                .map(|delayed| 2.0 * value - delayed),
        };
        self.ema.next(adjusted)
    }
}

fn zlema(series: &Series, period: i64) -> PolarsResult<Series> {
    let filter = ZlemaFilter::new(period).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_filter(series, "zlema", filter)
}

#[polars_expr(output_type = Float64)]
fn zlema_expr(inputs: &[Series], kwargs: ZlemaKwargs) -> PolarsResult<Series> {
    zlema(&inputs[0], kwargs.period)
}

/// Zero-lag exponential moving average.
///
/// Args:
///     series: input values.
///     period: averaging period (default 20).
#[pyfunction]
#[pyo3(name = "zlema", signature = (series, *, period=20))]
pub fn zlema_py(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();
    Ok(PySeries(zlema(&series, period).map_err(PyPolarsErr::from)?))
}
