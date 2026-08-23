use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use crate::kernels::wma::WmaFilter;
use crate::utils::{run_filter, Filter};

#[derive(Deserialize)]
pub struct HmaKwargs {
    period: i64,
}

/// Fused Hull moving average.
pub struct HmaFilter {
    half: WmaFilter,
    full: WmaFilter,
    root: WmaFilter,
}

impl HmaFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        if period < 2 {
            return Err("HMA period must be > 1".to_string());
        }
        let half_period = period / 2;
        let root_period = (period as f64).sqrt() as i64;
        Ok(Self {
            half: WmaFilter::new(half_period)?,
            full: WmaFilter::new(period)?,
            root: WmaFilter::new(root_period)?,
        })
    }
}

impl Filter for HmaFilter {
    type Input = Option<f64>;
    type Output = f64;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        let half = self.half.next(input);
        let full = self.full.next(input);
        let combined = match (half, full) {
            (Some(half), Some(full)) => Some(2.0 * half - full),
            _ => None,
        };
        self.root.next(combined)
    }
}

fn hma(series: &Series, period: i64) -> PolarsResult<Series> {
    let filter = HmaFilter::new(period).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_filter(series, "hma", filter)
}

#[polars_expr(output_type = Float64)]
fn hma_expr(inputs: &[Series], kwargs: HmaKwargs) -> PolarsResult<Series> {
    hma(&inputs[0], kwargs.period)
}

/// Hull moving average.
///
/// Uses periods `period / 2` and `floor(sqrt(period))`.
///
/// Args:
///     series: input values.
///     period: averaging period (default 20; must be greater than 1).
#[pyfunction]
#[pyo3(name = "hma", signature = (series, *, period=20))]
pub fn hma_py(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();
    Ok(PySeries(hma(&series, period).map_err(PyPolarsErr::from)?))
}
