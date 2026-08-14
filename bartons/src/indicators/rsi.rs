use pyo3::prelude::*;
use polars::prelude::*;
use serde::Deserialize;
use pyo3_polars::PySeries;
use pyo3_polars::derive::polars_expr;
use pyo3::exceptions::PyRuntimeError;

use super::rma::RmaFilter;
use crate::utils::{run_unary, Filter};

#[derive(Deserialize)]
pub struct RsiKwargs {
    period: i64,
}

/// Streaming Wilder RSI filter: feed one `Option<f64>` price at a time via
/// [`Filter::next`].
///
/// Splits each bar-to-bar change into gains and losses, smooths each with a
/// Wilder average ([`RmaFilter`]), and emits
/// `100 * avg_gain / (avg_gain + avg_loss)`. A flat run (no gains or losses)
/// yields `0.0`, matching TA-Lib. A `None` input is skipped entirely — all state
/// (the gain/loss averages and the previous price) carries across the gap, so the
/// next bar measures the real change across it; output is `None` until the first
/// delta plus the averages' warmup.
pub struct RsiFilter {
    prev: Option<f64>,
    gain: RmaFilter,
    loss: RmaFilter,
}

impl RsiFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        Ok(Self {
            prev: None,
            gain: RmaFilter::new(period)?,
            loss: RmaFilter::new(period)?,
        })
    }
}

impl Filter for RsiFilter {
    type Input = Option<f64>;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        // A null is skipped entirely: emit null but carry all state across the gap
        // — the gain/loss averages (feeding them None would be a no-op now) and
        // `prev`, so the next valid bar measures the real change across the gap.
        let Some(price) = input else {
            return None;
        };

        // First value of the series: store it, no delta to measure yet.
        let Some(prev) = self.prev.replace(price) else {
            return None;
        };

        let delta = price - prev;
        let avg_gain = self.gain.next(Some(delta.max(0.0)));
        let avg_loss = self.loss.next(Some((-delta).max(0.0)));

        match (avg_gain, avg_loss) {
            (Some(gain), Some(loss)) => {
                let denom = gain + loss;
                // Flat run (no gains or losses) -> 0, matching TA-Lib.
                Some(if denom == 0.0 { 0.0 } else { 100.0 * gain / denom })
            }
            _ => None,
        }
    }
}

fn calc_rsi(series: &Series, period: i64) -> PolarsResult<Series> {
    let filter = RsiFilter::new(period).map_err(|e| PolarsError::ComputeError(e.into()))?;
    run_unary(series, "rsi", filter)
}

#[polars_expr(output_type = Float64)]
fn rsi_expr(inputs: &[Series], kwargs: RsiKwargs) -> PolarsResult<Series> {
    calc_rsi(&inputs[0], kwargs.period)
}

/// Wilder's Relative Strength Index.
///
/// Args:
///     series: input values.
///     period: smoothing period (default 14).
///
/// Returns:
///     A Float64 series in 0..=100; null during the warmup period.
#[pyfunction]
#[pyo3(signature = (series, *, period=14))]
pub fn rsi(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();

    let result = match calc_rsi(&series, period) {
        Ok(s) => s,
        Err(e) => return Err(PyRuntimeError::new_err(e.to_string())),
    };

    let result: PySeries = PySeries(result);
    Ok(result)
}
