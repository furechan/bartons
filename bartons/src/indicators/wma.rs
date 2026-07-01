use pyo3::prelude::*;
use polars::prelude::*;
use serde::Deserialize;
use pyo3_polars::PySeries;
use pyo3_polars::derive::polars_expr;
use pyo3::exceptions::PyRuntimeError;

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
    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        // A null breaks the current run: reset and emit null.
        let Some(val) = input else {
            self.rsum = 0.0;
            self.wsum = 0.0;
            self.count = 0;
            self.idx = 0;
            return None;
        };

        self.count += 1;
        self.rsum += val;
        self.wsum += self.count as f64 * val;

        if self.count > self.period {
            // Slide the window: drop one from every weight, then evict the oldest.
            let oldest = self.buf[self.idx]; // read before overwriting
            self.wsum -= self.rsum;
            self.rsum -= oldest;
            self.count -= 1;
        }
        self.buf[self.idx] = val;
        self.idx = (self.idx + 1) % self.buf.len();

        // Warmup period emits null; otherwise the weighted mean.
        (self.count >= self.period).then_some(self.wsum / self.denom)
    }
}

fn calc_wma(series: &Series, period: i64) -> PolarsResult<Series> {
    let filter = WmaFilter::new(period).map_err(|e| PolarsError::ComputeError(e.into()))?;
    run_unary(series, "wma", filter)
}

#[polars_expr(output_type = Float64)]
fn wma_expr(inputs: &[Series], kwargs: WmaKwargs) -> PolarsResult<Series> {
    calc_wma(&inputs[0], kwargs.period)
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
#[pyo3(signature = (series, *, period=20))]
pub fn wma(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();

    let result = match calc_wma(&series, period) {
        Ok(s) => s,
        Err(e) => return Err(PyRuntimeError::new_err(e.to_string())),
    };

    let result: PySeries = PySeries(result);
    Ok(result)
}
