use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use super::mad::MadFilter;
use super::Hlc;
use crate::utils::{run_ternary, run_unary, Filter};

/// Lambert's constant, which scales CCI so that roughly 70-80% of values fall
/// in -100..=100. Fixed at the conventional 0.015, as in TA-Lib and mintalib.
const LAMBERT: f64 = 0.015;

#[derive(Deserialize)]
pub struct CciKwargs {
    period: i64,
}

/// Streaming Commodity Channel Index filter, fed one value at a time via
/// [`Filter::next`].
///
///   CCI = (input - SMA(input)) / (0.015 * MAD(input))
///
/// Standard CCI feeds it typical price, `(high + low + close) / 3` — what
/// `CCI()` and [`HlcCciFilter`] supply — but nothing here requires that; the
/// filter works on whatever single price series it is given.
///
/// One [`MadFilter`] backs both terms: its window mean *is* the SMA, so
/// [`MadFilter::next_stats`] yields the pair and no second window is kept. A
/// `None` input resets the window (the windowed-indicator convention); output
/// is `None` during the warmup.
///
/// Reducing three columns to one stays *outside* the filter because that step
/// is elementwise and stateless — unlike ATR's true range, which needs the
/// bar's three values together. Leaving it out means one series crosses the
/// plugin boundary instead of three, which matters most under `.over()`, where
/// polars partitions every input column per group.
pub struct CciFilter {
    mad: MadFilter,
}

impl CciFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        Ok(Self {
            mad: MadFilter::new(period).map_err(|_| "CCI period must be > 0".to_string())?,
        })
    }
}

impl Filter for CciFilter {
    type Input = Option<f64>;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        let (mean, mad) = self.mad.next_stats(input)?;
        // A full window implies this value went into it.
        let input = input?;
        // A zero MAD means a flat window, so the numerator is zero too and this
        // is 0/0 -> NaN. That matches the expression composition this replaces.
        Some((input - mean) / (LAMBERT * mad))
    }
}

fn cci(series: &Series, period: i64) -> PolarsResult<Series> {
    let filter = CciFilter::new(period).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_unary(series, "cci", filter)
}

/// Feeds [`CciFilter`] typical price derived from three raw columns, for the
/// eager binding.
///
/// The expression path never uses this: `CCI()` builds the same reduction as a
/// polars expression, which the engine evaluates vectorized before the plugin is
/// reached. Same arithmetic in the same order, so both surfaces agree bit for
/// bit.
struct HlcCciFilter {
    cci: CciFilter,
}

impl Filter for HlcCciFilter {
    type Input = Hlc;

    fn next(&mut self, (high, low, close): Hlc) -> Option<f64> {
        let typical = high
            .zip(low)
            .zip(close)
            .map(|((hi, lo), cl)| (hi + lo + cl) / 3.0);
        self.cci.next(typical)
    }
}

/// The eager path: typical price and CCI in one pass over the three columns.
fn cci_hlc(high: &Series, low: &Series, close: &Series, period: i64) -> PolarsResult<Series> {
    let cci = CciFilter::new(period).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_ternary(high, low, close, "cci", HlcCciFilter { cci })
}

#[polars_expr(output_type = Float64)]
fn cci_expr(inputs: &[Series], kwargs: CciKwargs) -> PolarsResult<Series> {
    cci(&inputs[0], kwargs.period)
}

/// Commodity Channel Index.
///
/// Args:
///     high: high prices.
///     low: low prices.
///     close: close prices.
///     period: window length (default 20).
///
/// Returns:
///     A Float64 series; null during the warmup period.
#[pyfunction]
#[pyo3(name = "cci", signature = (high, low, close, *, period=20))]
pub fn cci_py(high: PySeries, low: PySeries, close: PySeries, period: i64) -> PyResult<PySeries> {
    let high: Series = high.into();
    let low: Series = low.into();
    let close: Series = close.into();

    let result = cci_hlc(&high, &low, &close, period).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}
