use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use crate::kernels::ema::EmaFilter;
use crate::utils::{run_filter, Filter};

#[derive(Deserialize)]
pub struct TemaKwargs {
    period: i64,
}

/// Fused triple exponential moving average.
pub struct TemaFilter {
    first: EmaFilter,
    second: EmaFilter,
    third: EmaFilter,
}

impl TemaFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        if period <= 0 {
            return Err("TEMA period must be > 0".to_string());
        }
        Ok(Self {
            first: EmaFilter::new(period)?,
            second: EmaFilter::new(period)?,
            third: EmaFilter::new(period)?,
        })
    }
}

impl Filter for TemaFilter {
    type Input = Option<f64>;
    type Output = f64;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        let first = self.first.next(input);
        let second = self.second.next(first);
        let third = self.third.next(second);
        Some(3.0 * first? - 3.0 * second? + third?)
    }
}

fn tema(series: &Series, period: i64) -> PolarsResult<Series> {
    let filter = TemaFilter::new(period).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_filter(series, "tema", filter)
}

#[polars_expr(output_type = Float64)]
fn tema_expr(inputs: &[Series], kwargs: TemaKwargs) -> PolarsResult<Series> {
    tema(&inputs[0], kwargs.period)
}

/// Triple exponential moving average.
///
/// Args:
///     series: input values.
///     period: averaging period (default 20).
#[pyfunction]
#[pyo3(name = "tema", signature = (series, *, period=20))]
pub fn tema_py(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();
    Ok(PySeries(tema(&series, period).map_err(PyPolarsErr::from)?))
}
