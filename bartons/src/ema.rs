use pyo3::prelude::*;
use polars::prelude::*;
use serde::Deserialize;
use pyo3_polars::PySeries;
use pyo3_polars::derive::polars_expr;
use pyo3::exceptions::PyRuntimeError;

use crate::utils::{run_unary, Filter};

#[derive(Deserialize)]
pub struct EmaKwargs {
    period: i64,
}

/// Streaming EMA filter: feed one `Option<f64>` at a time via [`Filter::next`].
///
/// A `None` input breaks the current run (gap reset); output is `None` during
/// the warmup period, then the running EMA value.
pub struct EmaFilter {
    period: i64,
    alpha: f64,
    value: f64,
    count: i64,
}

impl EmaFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        if period <= 0 {
            return Err("EMA period must be > 0".to_string());
        }
        Ok(Self {
            period,
            alpha: 2.0 / (period as f64 + 1.0),
            value: f64::NAN,
            count: 0,
        })
    }
}

impl Filter for EmaFilter {
    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        // A null breaks the current run: reset and emit null.
        let Some(val) = input else {
            self.value = f64::NAN;
            self.count = 0;
            return None;
        };

        if self.count == 0 {
            self.value = val;
        } else {
            self.value += self.alpha * (val - self.value);
        }
        self.count += 1;

        // Warmup period emits null; otherwise the running EMA value.
        (self.count >= self.period).then_some(self.value)
    }
}

fn calc_ema(series: &Series, period: i64) -> PolarsResult<Series> {
    let filter = EmaFilter::new(period).map_err(|e| PolarsError::ComputeError(e.into()))?;
    run_unary(series, "ema", filter)
}

#[polars_expr(output_type = Float64)]
fn ema_expr(inputs: &[Series], kwargs: EmaKwargs) -> PolarsResult<Series> {
    calc_ema(&inputs[0], kwargs.period)
}

#[pyfunction]
#[pyo3(signature = (series, *, period=20))]
pub fn ema(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();

    let result = match calc_ema(&series, period) {
        Ok(s) => s,
        Err(e) => return Err(PyRuntimeError::new_err(e.to_string())),
    };

    let result: PySeries = PySeries(result);
    Ok(result)
}
