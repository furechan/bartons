use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use super::HighLowInput;
use crate::utils::{run_filter, Filter};

#[derive(Deserialize)]
pub struct SarKwargs {
    afs: f64,
    maxaf: f64,
}

/// Streaming Parabolic Stop and Reverse state machine.
///
/// This is the Rust form of the shared mintalib/bearta algorithm. The value
/// emitted for a bar is the SAR established by the preceding bar; reversals are
/// applied before that value is emitted, and the next SAR is calculated after.
///
/// A missing or malformed bar (`high < low`) emits null without changing any
/// state. The next valid bar therefore continues from the last valid bar rather
/// than resetting the trend.
pub struct SarFilter {
    afs: f64,
    maxaf: f64,
    ep: Option<f64>,
    sar: Option<f64>,
    af: f64,
    previous: Option<(f64, f64)>,
    trend: i8,
}

impl SarFilter {
    pub fn new(afs: f64, maxaf: f64) -> Self {
        Self {
            afs,
            maxaf,
            ep: None,
            sar: None,
            af: f64::NAN,
            previous: None,
            trend: 0,
        }
    }
}

impl Filter for SarFilter {
    type Input = HighLowInput;
    type Output = f64;

    fn next(&mut self, (high, low): HighLowInput) -> Option<f64> {
        let (Some(high), Some(low)) = (high, low) else {
            return None;
        };
        if high < low {
            return None;
        }

        let Some((previous_high, previous_low)) = self.previous.replace((high, low)) else {
            return None;
        };

        let high2 = previous_high.max(high);
        let low2 = previous_low.min(low);

        if self.trend > 0 && low < self.sar.expect("an established trend has a SAR") {
            self.sar = self.ep;
            self.ep = Some(low);
            self.af = self.afs;
            self.trend = -1;
        } else if self.trend < 0 && high > self.sar.expect("an established trend has a SAR") {
            self.sar = self.ep;
            self.ep = Some(high);
            self.af = self.afs;
            self.trend = 1;
        }

        let output = self.sar;

        if self.trend == 0 {
            self.af = self.afs;
            if high > previous_high {
                self.ep = Some(high2);
                self.sar = Some(low2);
                self.trend = 1;
            } else {
                self.ep = Some(low2);
                self.sar = Some(high2);
                self.trend = -1;
            }
        } else {
            let ep = self.ep.expect("an established trend has an extreme point");
            let mut next_sar = self.sar.expect("an established trend has a SAR");
            next_sar += self.af * (ep - next_sar);

            if self.trend > 0 {
                next_sar = next_sar.min(low2);
                if high > ep {
                    self.ep = Some(high);
                    self.af += self.afs;
                }
            } else {
                next_sar = next_sar.max(high2);
                if low < ep {
                    self.ep = Some(low);
                    self.af += self.afs;
                }
            }
            self.sar = Some(next_sar);
        }

        if self.maxaf != 0.0 && self.af > self.maxaf {
            self.af = self.maxaf;
        }

        output
    }
}

fn sar(high: &Series, low: &Series, afs: f64, maxaf: f64) -> PolarsResult<Series> {
    run_filter((high, low), "sar", SarFilter::new(afs, maxaf))
}

#[polars_expr(output_type = Float64)]
fn sar_expr(inputs: &[Series], kwargs: SarKwargs) -> PolarsResult<Series> {
    sar(&inputs[0], &inputs[1], kwargs.afs, kwargs.maxaf)
}

/// Parabolic Stop and Reverse.
///
/// Args:
///     high: high prices.
///     low: low prices.
///     afs: starting acceleration factor (default 0.02).
///     maxaf: maximum acceleration factor (default 0.2; zero disables the cap).
///
/// Returns:
///     A Float64 series; null until the trend is initialized and on invalid bars.
#[pyfunction]
#[pyo3(name = "sar", signature = (high, low, *, afs=0.02, maxaf=0.2))]
pub fn sar_py(high: PySeries, low: PySeries, afs: f64, maxaf: f64) -> PyResult<PySeries> {
    let high: Series = high.into();
    let low: Series = low.into();
    let result = sar(&high, &low, afs, maxaf).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}
