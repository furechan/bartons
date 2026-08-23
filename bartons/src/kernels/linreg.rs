use std::str::FromStr;

use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use crate::ring_buffer::RingBuffer;
use crate::utils::{run_filter, Filter};

const MIN_REBASE_INTERVAL: i64 = 1000;

#[derive(Clone, Copy, Debug, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum LinRegOutput {
    Forecast,
    Slope,
    #[serde(rename = "rvalue")]
    RValue,
    Rmse,
}

impl LinRegOutput {
    fn series_name(self) -> &'static str {
        match self {
            Self::Forecast => "linreg",
            Self::Slope => "linreg_slope",
            Self::RValue => "linreg_rvalue",
            Self::Rmse => "linreg_rmse",
        }
    }
}

impl FromStr for LinRegOutput {
    type Err = PolarsError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value {
            "forecast" => Ok(Self::Forecast),
            "slope" => Ok(Self::Slope),
            "rvalue" => Ok(Self::RValue),
            "rmse" => Ok(Self::Rmse),
            _ => polars_bail!(
                InvalidOperation:
                "invalid LINREG output '{}'; expected 'forecast', 'slope', 'rvalue', or 'rmse'",
                value
            ),
        }
    }
}

#[derive(Deserialize)]
pub struct LinRegKwargs {
    period: i64,
    #[serde(default)]
    offset: i64,
    #[serde(default)]
    rebase_interval: Option<i64>,
    output: LinRegOutput,
}

/// One-pass rolling linear-regression filter. The output selector changes only
/// the statistic emitted; every variant shares this window state and math.
pub struct LinRegFilter {
    // Nulls clear the window, so retained values always have consecutive row
    // indices. For a full window at row `i`, the evicted row is `i - capacity`.
    buffer: RingBuffer<f64>,
    rebase_interval: usize,
    next_i: usize,
    anchor: usize,
    offset: i64,
    output: LinRegOutput,
    s: f64,
    sx: f64,
    sxx: f64,
    sy: f64,
    sxy: f64,
    syy: f64,
}

impl LinRegFilter {
    pub fn new(
        period: i64,
        offset: i64,
        rebase_interval: Option<i64>,
        output: LinRegOutput,
    ) -> Result<Self, String> {
        if period < 2 {
            return Err("LINREG period must be >= 2".to_string());
        }
        if rebase_interval.is_some_and(|interval| interval < 0) {
            return Err("LINREG rebase_interval must be >= 0 or None".to_string());
        }
        if offset != 0 && output != LinRegOutput::Forecast {
            return Err("LINREG offset is only valid when output='forecast'".to_string());
        }

        Ok(Self {
            buffer: RingBuffer::new(period as usize),
            rebase_interval: rebase_interval
                .unwrap_or_else(|| MIN_REBASE_INTERVAL.max(period.saturating_mul(2)))
                as usize,
            next_i: 0,
            anchor: 0,
            offset,
            output,
            s: 0.0,
            sx: 0.0,
            sxx: 0.0,
            sy: 0.0,
            sxy: 0.0,
            syy: 0.0,
        })
    }

    fn reset(&mut self) {
        self.buffer.clear();
        self.clear_sums();
    }

    fn clear_sums(&mut self) {
        self.s = 0.0;
        self.sx = 0.0;
        self.sxx = 0.0;
        self.sy = 0.0;
        self.sxy = 0.0;
        self.syy = 0.0;
    }

    fn add(&mut self, i: usize, y: f64) {
        let x = (i - self.anchor) as f64;
        self.s += 1.0;
        self.sx += x;
        self.sxx += x * x;
        self.sy += y;
        self.sxy += x * y;
        self.syy += y * y;
    }

    fn sub(&mut self, i: usize, y: f64) {
        let x = (i - self.anchor) as f64;
        self.s -= 1.0;
        self.sx -= x;
        self.sxx -= x * x;
        self.sy -= y;
        self.sxy -= x * y;
        self.syy -= y * y;
    }

    fn rebase_needed(&self, i: usize) -> bool {
        self.rebase_interval > 0 && i - self.anchor >= self.rebase_interval
    }

    fn rebase_sums(&mut self, i: usize) {
        if !self.buffer.is_full() {
            return;
        }

        let anchor = i + 1 - self.buffer.capacity();
        let mut sy = 0.0;
        let mut sxy = 0.0;
        let mut syy = 0.0;
        for (x, &value) in self.buffer.iter().enumerate() {
            let x = x as f64;
            sy += value;
            sxy += x * value;
            syy += value * value;
        }

        let s = self.buffer.capacity() as f64;
        self.anchor = anchor;
        self.s = s;
        self.sx = s * (s - 1.0) / 2.0;
        self.sxx = s * (s - 1.0) * (2.0 * s - 1.0) / 6.0;
        self.sy = sy;
        self.sxy = sxy;
        self.syy = syy;
    }
}

impl Filter for LinRegFilter {
    type Input = Option<f64>;
    type Output = f64;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        let i = self.next_i;
        self.next_i += 1;

        let Some(value) = input else {
            self.reset();
            return None;
        };

        if self.buffer.is_empty() {
            self.anchor = i;
        }
        match self.buffer.push(value) {
            None => self.add(i, value),
            Some(_) if self.rebase_needed(i) => self.rebase_sums(i),
            Some(evicted) => {
                self.sub(i - self.buffer.capacity(), evicted);
                self.add(i, value);
            }
        }

        if !self.buffer.is_full() {
            return None;
        }

        let mean_x = self.sx / self.s;
        let mean_y = self.sy / self.s;
        let vxx = self.sxx / self.s - mean_x * mean_x;
        let vxy = self.sxy / self.s - mean_x * mean_y;
        let vyy = (self.syy / self.s - mean_y * mean_y).max(0.0);
        let slope = vxy / vxx;

        Some(match self.output {
            LinRegOutput::Slope => slope,
            LinRegOutput::Forecast => {
                let intercept = mean_y - slope * mean_x;
                let current_x = (i - self.anchor) as f64;
                intercept + slope * (current_x + self.offset as f64)
            },
            LinRegOutput::RValue => {
                if vyy > 0.0 {
                    vxy / (vxx * vyy).sqrt()
                } else {
                    f64::NAN
                }
            },
            LinRegOutput::Rmse => {
                if vyy > 0.0 {
                    let corr = vxy / (vxx * vyy).sqrt();
                    (vyy * (1.0 - corr * corr).max(0.0)).sqrt()
                } else {
                    f64::NAN
                }
            },
        })
    }
}

fn linreg(
    series: &Series,
    period: i64,
    offset: i64,
    rebase_interval: Option<i64>,
    output: LinRegOutput,
) -> PolarsResult<Series> {
    let name = output.series_name();
    let filter = LinRegFilter::new(period, offset, rebase_interval, output)
        .map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_filter(series, name, filter)
}

#[polars_expr(output_type = Float64)]
fn linreg_expr(inputs: &[Series], kwargs: LinRegKwargs) -> PolarsResult<Series> {
    linreg(
        &inputs[0],
        kwargs.period,
        kwargs.offset,
        kwargs.rebase_interval,
        kwargs.output,
    )
}

/// Rolling linear regression statistic.
///
/// Args:
///     series: input values.
///     period: regression-window length (default 20; minimum 2).
///     offset: forecast offset (default 0); nonzero values require output="forecast".
///     rebase_interval: maximum bar span for incrementally maintained sums before
///         rebasing from the current window. None selects max(1000, 2 * period);
///         0 disables rebasing.
///     output: statistic to return: "forecast", "slope", "rvalue", or "rmse".
///
/// Returns:
///     A Float64 series; null during warmup and after a null resets the window.
#[pyfunction]
#[pyo3(name = "linreg", signature = (series, period=20, offset=0, rebase_interval=None, *, output="forecast"))]
pub fn linreg_py(
    series: PySeries,
    period: i64,
    offset: i64,
    rebase_interval: Option<i64>,
    output: &str,
) -> PyResult<PySeries> {
    let series: Series = series.into();
    let output = output.parse::<LinRegOutput>().map_err(PyPolarsErr::from)?;
    let result =
        linreg(&series, period, offset, rebase_interval, output).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rebase_discards_history_before_the_current_window() {
        let mut filter = LinRegFilter::new(3, 0, Some(4), LinRegOutput::Forecast).unwrap();
        for value in [1.0, 2.0, 3.0, 4.0] {
            filter.next(Some(value));
        }
        assert_eq!(filter.next_i - filter.anchor, 4);
        assert_eq!(filter.sx, 6.0); // retained x coordinates are 1, 2, 3

        filter.next(Some(5.0));
        assert_eq!(filter.next_i - filter.anchor, 3);
        assert_eq!(filter.sx, 3.0); // re-anchored to 0, 1, 2
        assert_eq!(
            filter.buffer.iter().copied().collect::<Vec<_>>(),
            [3.0, 4.0, 5.0]
        );
    }

    #[test]
    fn interval_at_or_below_period_rebases_every_full_window_slide() {
        let mut filter = LinRegFilter::new(3, 0, Some(2), LinRegOutput::Forecast).unwrap();
        for value in [1.0, 2.0, 3.0, 4.0, 5.0] {
            filter.next(Some(value));
            assert!(filter.next_i - filter.anchor <= 3);
        }
    }

    #[test]
    fn automatic_rebase_interval_scales_with_period() {
        let short = LinRegFilter::new(20, 0, None, LinRegOutput::Forecast).unwrap();
        let long = LinRegFilter::new(600, 0, None, LinRegOutput::Forecast).unwrap();

        assert_eq!(short.rebase_interval, 1000);
        assert_eq!(long.rebase_interval, 1200);
    }
}
