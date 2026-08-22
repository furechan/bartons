use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use super::mad::MadFilter;
use crate::utils::{run_filter, Filter};

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
/// `TYPPRICE()` builds and `CCI()` supplies by default — but nothing here
/// requires that; the filter works on whatever single price series it is given.
///
/// One [`MadFilter`] backs both terms: its window mean *is* the SMA, so
/// [`MadFilter::next_stats`] yields the pair and no second window is kept. A
/// `None` input resets the window (the windowed-indicator convention); output
/// is `None` during the warmup.
///
/// Reducing three columns to one stays *outside* the kernel, on both surfaces,
/// because that step is elementwise and stateless — unlike ATR's true range,
/// which needs the bar's three values together. Polars already vectorizes it,
/// as an expression on the lazy path and as `Series` arithmetic on the eager
/// one, so there is no typical-price kernel and the formula has exactly one
/// definition, in `bartons.indicators.TYPPRICE`. Keeping it out also means one
/// series crosses the plugin boundary instead of three, which matters most
/// under `.over()`, where polars partitions every input column per group: a
/// ternary variant measured 0.51x there.
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
    type Output = f64;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        let (mean, mad) = self.mad.next_stats(input)?;
        // A full window implies this value went into it.
        let input = input?;
        // A zero MAD means a flat window, so the numerator is zero too and this
        // is 0/0 -> NaN, matching the SMA/MAD composition in tests/refimpl.py.
        Some((input - mean) / (LAMBERT * mad))
    }
}

fn cci(series: &Series, period: i64) -> PolarsResult<Series> {
    let filter = CciFilter::new(period).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_filter(series, "cci", filter)
}

#[polars_expr(output_type = Float64)]
fn cci_expr(inputs: &[Series], kwargs: CciKwargs) -> PolarsResult<Series> {
    cci(&inputs[0], kwargs.period)
}

/// Commodity Channel Index.
///
/// Takes the price series to run over, conventionally typical price:
/// ``kernels.cci((high + low + close) / 3, period=20)``. The reduction is
/// plain Series arithmetic, which polars already vectorizes.
///
/// Args:
///     series: input prices.
///     period: window length (default 20).
///
/// Returns:
///     A Float64 series; null during the warmup period.
#[pyfunction]
#[pyo3(name = "cci", signature = (series, *, period=20))]
pub fn cci_py(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();
    let result = cci(&series, period).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}
