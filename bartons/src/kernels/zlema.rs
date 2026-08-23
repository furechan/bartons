use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use crate::kernels::ema::EmaFilter;
use crate::utils::{run_filter, Filter};

#[derive(Deserialize)]
pub struct ZlemaKwargs {
    period: i64,
}

/// Fused zero-lag EMA: EMA of `src + (src - src[lag])`.
pub struct ZlemaFilter {
    lag: usize,
    buffer: Vec<f64>,
    idx: usize,
    count: usize,
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
            buffer: vec![0.0; lag],
            idx: 0,
            count: 0,
            ema: EmaFilter::new(period)?,
        })
    }

    fn reset_lag(&mut self) {
        self.idx = 0;
        self.count = 0;
    }
}

impl Filter for ZlemaFilter {
    type Input = Option<f64>;
    type Output = f64;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        let Some(value) = input else {
            self.reset_lag();
            return self.ema.next(None);
        };

        if self.lag == 0 {
            return self.ema.next(Some(value));
        }

        if self.count < self.lag {
            self.buffer[self.idx] = value;
            self.idx += 1;
            self.count += 1;
            if self.idx == self.buffer.len() {
                self.idx = 0;
            }
            return self.ema.next(None);
        }

        let delayed = self.buffer[self.idx];
        self.buffer[self.idx] = value;
        self.idx += 1;
        if self.idx == self.buffer.len() {
            self.idx = 0;
        }
        self.ema.next(Some(2.0 * value - delayed))
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
