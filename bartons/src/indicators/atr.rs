use pyo3::prelude::*;
use polars::prelude::*;
use serde::Deserialize;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use pyo3_polars::derive::polars_expr;

use super::rma::RmaFilter;
use super::trange::TrangeFilter;
use super::Hlc;
use crate::utils::{run_ternary, Filter};

#[derive(Deserialize)]
pub struct AtrKwargs {
    period: i64,
}

/// Streaming ATR filter: feed one bar's `(high, low, close)` at a time via
/// [`Filter::next`].
///
/// ATR is Wilder's RMA of the True Range, so this composes a [`TrangeFilter`]
/// feeding an [`RmaFilter`]. A bar with a missing high or low yields a `None`
/// true range, which the RMA skips — carrying ATR across the missing bar
/// (matching mintalib); output is `None` during the warmup.
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
}

impl Filter for AtrFilter {
    type Input = Hlc;

    fn next(&mut self, hlc: Hlc) -> Option<f64> {
        let tr = self.trange.next(hlc);
        self.rma.next(tr)
    }
}

fn calc_atr(high: &Series, low: &Series, close: &Series, period: i64) -> PolarsResult<Series> {
    let filter = AtrFilter::new(period).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_ternary(high, low, close, "atr", filter)
}

#[polars_expr(output_type = Float64)]
fn atr_expr(inputs: &[Series], kwargs: AtrKwargs) -> PolarsResult<Series> {
    calc_atr(&inputs[0], &inputs[1], &inputs[2], kwargs.period)
}

/// Average True Range (Wilder's).
///
/// Args:
///     high: high prices.
///     low: low prices.
///     close: close prices.
///     period: smoothing period (default 14).
///
/// Returns:
///     A Float64 series; null during the warmup period.
#[pyfunction]
#[pyo3(signature = (high, low, close, *, period=14))]
pub fn atr(high: PySeries, low: PySeries, close: PySeries, period: i64) -> PyResult<PySeries> {
    let high: Series = high.into();
    let low: Series = low.into();
    let close: Series = close.into();

    let result = calc_atr(&high, &low, &close, period).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}
