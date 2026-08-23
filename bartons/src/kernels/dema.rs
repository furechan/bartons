use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use crate::kernels::ema::EmaFilter;
use crate::utils::{run_filter, Filter};

#[derive(Deserialize)]
pub struct DemaKwargs {
    period: i64,
}

/// Fused double exponential moving average: `2 * EMA(src) - EMA(EMA(src))`.
pub struct DemaFilter {
    first: EmaFilter,
    second: EmaFilter,
}

impl DemaFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        if period <= 0 {
            return Err("DEMA period must be > 0".to_string());
        }
        Ok(Self {
            first: EmaFilter::new(period)?,
            second: EmaFilter::new(period)?,
        })
    }
}

impl Filter for DemaFilter {
    type Input = Option<f64>;
    type Output = f64;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        let first = self.first.next(input);
        let second = self.second.next(first);
        Some(2.0 * first? - second?)
    }
}

fn dema(series: &Series, period: i64) -> PolarsResult<Series> {
    let filter = DemaFilter::new(period).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_filter(series, "dema", filter)
}

#[polars_expr(output_type = Float64)]
fn dema_expr(inputs: &[Series], kwargs: DemaKwargs) -> PolarsResult<Series> {
    dema(&inputs[0], kwargs.period)
}

/// Double exponential moving average.
///
/// Args:
///     series: input values.
///     period: averaging period (default 20).
#[pyfunction]
#[pyo3(name = "dema", signature = (series, *, period=20))]
pub fn dema_py(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();
    Ok(PySeries(dema(&series, period).map_err(PyPolarsErr::from)?))
}
