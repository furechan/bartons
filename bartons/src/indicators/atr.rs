use pyo3::prelude::*;
use polars::prelude::*;
use serde::Deserialize;
use pyo3_polars::PySeries;
use pyo3_polars::derive::polars_expr;
use pyo3::exceptions::PyRuntimeError;

use super::rma::RmaFilter;
use super::trange::TrangeFilter;
use crate::utils::{run_ternary, Filter};

#[derive(Deserialize)]
pub struct AtrKwargs {
    period: i64,
}

/// Streaming ATR filter: feed one bar's `(high, low, close)` at a time via
/// [`Self::next`].
///
/// ATR is Wilder's RMA of the True Range, so this composes a [`TrangeFilter`]
/// feeding an [`RmaFilter`]. A bar with a missing high or low yields a `None`
/// true range, which resets the RMA run; output is `None` during the warmup.
pub struct AtrFilter {
    trange: TrangeFilter,
    rma: RmaFilter,
}

impl AtrFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        Ok(Self {
            trange: TrangeFilter::new(),
            rma: RmaFilter::new(period)?,
        })
    }

    pub fn next(
        &mut self,
        high: Option<f64>,
        low: Option<f64>,
        close: Option<f64>,
    ) -> Option<f64> {
        let tr = self.trange.next(high, low, close);
        self.rma.next(tr)
    }
}

fn calc_atr(high: &Series, low: &Series, close: &Series, period: i64) -> PolarsResult<Series> {
    let mut filter = AtrFilter::new(period).map_err(|e| PolarsError::ComputeError(e.into()))?;
    run_ternary(high, low, close, "atr", |h, l, c| filter.next(h, l, c))
}

#[polars_expr(output_type = Float64)]
fn atr_expr(inputs: &[Series], kwargs: AtrKwargs) -> PolarsResult<Series> {
    calc_atr(&inputs[0], &inputs[1], &inputs[2], kwargs.period)
}

#[pyfunction]
#[pyo3(signature = (high, low, close, *, period=14))]
pub fn atr(high: PySeries, low: PySeries, close: PySeries, period: i64) -> PyResult<PySeries> {
    let high: Series = high.into();
    let low: Series = low.into();
    let close: Series = close.into();

    let result = match calc_atr(&high, &low, &close, period) {
        Ok(s) => s,
        Err(e) => return Err(PyRuntimeError::new_err(e.to_string())),
    };

    let result: PySeries = PySeries(result);
    Ok(result)
}
