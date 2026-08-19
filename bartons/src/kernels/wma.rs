use pyo3::prelude::*;
use polars::prelude::*;
use serde::Deserialize;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use pyo3_polars::derive::polars_expr;

use crate::utils::{run_unary, Filter};

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
    period: i64,
    denom: f64,    // sum of weights 1..period
    buf: Vec<f64>, // ring buffer of the current run's window
    idx: usize,    // next write slot == oldest element once full
    count: i64,
    rsum: f64, // running simple sum of the window
    wsum: f64, // running weighted sum (oldest weight 1 .. newest weight period)
}

impl WmaFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        if period <= 0 {
            return Err("WMA period must be > 0".to_string());
        }
        Ok(Self {
            period,
            denom: period as f64 * (period as f64 + 1.0) / 2.0,
            buf: vec![0.0; period as usize],
            idx: 0,
            count: 0,
            rsum: 0.0,
            wsum: 0.0,
        })
    }
}

impl Filter for WmaFilter {
    type Input = Option<f64>;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        // A null breaks the current run: reset and emit null.
        let Some(val) = input else {
            self.rsum = 0.0;
            self.wsum = 0.0;
            self.count = 0;
            self.idx = 0;
            return None;
        };

        if self.count < self.period {
            self.count += 1;
            self.rsum += val;
            self.wsum += self.count as f64 * val;
        } else {
            // Slide the full window: drop one from every existing weight,
            // evict the oldest, and add the new value with weight `period`.
            let oldest = self.buf[self.idx]; // read before overwriting
            self.wsum += self.period as f64 * val - self.rsum;
            self.rsum += val - oldest;
        }
        self.buf[self.idx] = val;
        self.idx += 1;
        if self.idx == self.buf.len() {
            self.idx = 0;
        }

        // Warmup period emits null; otherwise the weighted mean.
        (self.count >= self.period).then_some(self.wsum / self.denom)
    }
}

fn wma(series: &Series, period: i64) -> PolarsResult<Series> {
    let filter = WmaFilter::new(period).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_unary(series, "wma", filter)
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
