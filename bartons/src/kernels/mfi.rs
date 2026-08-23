use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use crate::utils::{run_filter, Filter, Pair};

#[derive(Deserialize)]
pub struct MfiKwargs {
    period: i64,
}

/// Streaming Money Flow Index filter.
///
/// Each source value determines whether `src * volume` enters the positive or
/// negative rolling flow sum. Missing source values reset both the direction
/// comparison and rolling window. Missing volume resets the rolling window but
/// retains the source value, which is still available to determine the
/// direction of the next complete bar.
pub struct MfiFilter {
    buffer: Vec<f64>,
    idx: usize,
    count: usize,
    positive: f64,
    negative: f64,
    previous: Option<f64>,
}

impl MfiFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        if period <= 0 {
            return Err("MFI period must be > 0".to_string());
        }

        Ok(Self {
            buffer: vec![0.0; period as usize],
            idx: 0,
            count: 0,
            positive: 0.0,
            negative: 0.0,
            previous: None,
        })
    }

    fn reset_window(&mut self) {
        self.idx = 0;
        self.count = 0;
        self.positive = 0.0;
        self.negative = 0.0;
    }

    fn reset(&mut self) {
        self.reset_window();
        self.previous = None;
    }

    fn push(&mut self, flow: f64) {
        if self.count == self.buffer.len() {
            let oldest = self.buffer[self.idx];
            if oldest > 0.0 {
                self.positive -= oldest;
            } else if oldest < 0.0 {
                self.negative += oldest;
            }
        } else {
            self.count += 1;
        }

        if flow > 0.0 {
            self.positive += flow;
        } else if flow < 0.0 {
            self.negative -= flow;
        }

        self.buffer[self.idx] = flow;
        self.idx += 1;
        if self.idx == self.buffer.len() {
            self.idx = 0;
        }
    }
}

impl Filter for MfiFilter {
    type Input = Pair;
    type Output = f64;

    fn next(&mut self, (src, volume): Pair) -> Option<f64> {
        let Some(src) = src else {
            self.reset();
            return None;
        };

        let previous = self.previous.replace(src);
        let Some(volume) = volume else {
            self.reset_window();
            return None;
        };
        let Some(previous) = previous else {
            return None;
        };

        let raw_flow = src * volume;
        let flow = if src > previous {
            raw_flow
        } else if src < previous {
            -raw_flow
        } else {
            0.0
        };
        self.push(flow);

        if self.count < self.buffer.len() {
            return None;
        }

        let total = self.positive + self.negative;
        Some(if total == 0.0 {
            f64::NAN
        } else {
            100.0 * self.positive / total
        })
    }
}

fn mfi(src: &Series, volume: &Series, period: i64) -> PolarsResult<Series> {
    let filter = MfiFilter::new(period).map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_filter((src, volume), "mfi", filter)
}

#[polars_expr(output_type = Float64)]
fn mfi_expr(inputs: &[Series], kwargs: MfiKwargs) -> PolarsResult<Series> {
    mfi(&inputs[0], &inputs[1], kwargs.period)
}

/// Money Flow Index.
///
/// Args:
///     src: source prices, conventionally typical price.
///     volume: traded volume, cast to Float64.
///     period: rolling money-flow period (default 14).
///
/// Returns:
///     A Float64 series in 0..=100; null during warmup and after incomplete bars.
#[pyfunction]
#[pyo3(name = "mfi", signature = (src, volume, *, period=14))]
pub fn mfi_py(src: PySeries, volume: PySeries, period: i64) -> PyResult<PySeries> {
    let src: Series = src.into();
    let volume: Series = volume.into();

    let result = mfi(&src, &volume, period).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rolling_flow_sums_evict_the_oldest_value() {
        let mut filter = MfiFilter::new(2).unwrap();
        assert_eq!(filter.next((Some(1.0), Some(10.0))), None);
        assert_eq!(filter.next((Some(2.0), Some(10.0))), None);
        assert_eq!(filter.next((Some(3.0), Some(10.0))), Some(100.0));
        assert_eq!(filter.next((Some(2.0), Some(10.0))), Some(60.0));
    }

    #[test]
    fn missing_volume_keeps_source_but_resets_window() {
        let mut filter = MfiFilter::new(1).unwrap();
        filter.next((Some(1.0), Some(10.0)));
        assert_eq!(filter.next((Some(2.0), None)), None);
        assert_eq!(filter.next((Some(3.0), Some(10.0))), Some(100.0));
    }
}
