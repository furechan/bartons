use pyo3::prelude::*;
use polars::prelude::*;
use pyo3_polars::PySeries;
use pyo3_polars::derive::polars_expr;
use pyo3::exceptions::PyRuntimeError;

use crate::utils::run_ternary;

/// Streaming True Range filter: feed one bar's `(high, low, close)` at a time
/// via [`Self::next`].
///
///   TR = max(high - low, |high - prev_close|, |low - prev_close|)
///
/// The first bar (no previous close) uses high - low. A bar with a missing
/// high or low yields `None`. There is no period/warmup — TR is per-bar.
#[derive(Default)]
pub struct TrangeFilter {
    prev_close: Option<f64>,
}

impl TrangeFilter {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn next(
        &mut self,
        high: Option<f64>,
        low: Option<f64>,
        close: Option<f64>,
    ) -> Option<f64> {
        let tr = match (high, low) {
            (Some(hi), Some(lo)) => {
                let mut tr = hi - lo;
                if let Some(pc) = self.prev_close {
                    tr = tr.max((hi - pc).abs()).max((lo - pc).abs());
                }
                Some(tr)
            }
            _ => None,
        };
        // The current close becomes the previous close for the next bar.
        self.prev_close = close;
        tr
    }
}

fn calc_trange(high: &Series, low: &Series, close: &Series) -> PolarsResult<Series> {
    let mut filter = TrangeFilter::new();
    run_ternary(high, low, close, "trange", |h, l, c| filter.next(h, l, c))
}

#[polars_expr(output_type = Float64)]
fn trange_expr(inputs: &[Series]) -> PolarsResult<Series> {
    calc_trange(&inputs[0], &inputs[1], &inputs[2])
}

#[pyfunction]
#[pyo3(signature = (high, low, close))]
pub fn trange(high: PySeries, low: PySeries, close: PySeries) -> PyResult<PySeries> {
    let high: Series = high.into();
    let low: Series = low.into();
    let close: Series = close.into();

    let result = match calc_trange(&high, &low, &close) {
        Ok(s) => s,
        Err(e) => return Err(PyRuntimeError::new_err(e.to_string())),
    };

    let result: PySeries = PySeries(result);
    Ok(result)
}
