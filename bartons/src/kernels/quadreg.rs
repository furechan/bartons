use std::str::FromStr;

use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use crate::utils::{run_filter, Filter};

const MIN_REBASE_INTERVAL: i64 = 1000;

#[derive(Clone, Copy, Debug, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum QuadRegOutput {
    Forecast,
    Curve,
    Slope,
    #[serde(rename = "rvalue")]
    RValue,
    Rmse,
}

impl QuadRegOutput {
    fn series_name(self) -> &'static str {
        match self {
            Self::Forecast => "quadreg",
            Self::Curve => "quadreg_curve",
            Self::Slope => "quadreg_slope",
            Self::RValue => "quadreg_rvalue",
            Self::Rmse => "quadreg_rmse",
        }
    }
}

impl FromStr for QuadRegOutput {
    type Err = PolarsError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value {
            "forecast" => Ok(Self::Forecast),
            "curve" => Ok(Self::Curve),
            "slope" => Ok(Self::Slope),
            "rvalue" => Ok(Self::RValue),
            "rmse" => Ok(Self::Rmse),
            _ => polars_bail!(
                InvalidOperation:
                "invalid QUADREG output '{}'; expected 'forecast', 'curve', 'slope', 'rvalue', or 'rmse'",
                value
            ),
        }
    }
}

#[derive(Deserialize)]
pub struct QuadRegKwargs {
    period: i64,
    #[serde(default)]
    offset: i64,
    #[serde(default)]
    rebase_interval: Option<i64>,
    output: QuadRegOutput,
}

/// One-pass rolling quadratic-regression filter. Pure-x moments use a centered
/// window grid; data-dependent moments use an anchored grid that is periodically
/// rebased to bound floating-point drift.
pub struct QuadRegFilter {
    buffer: Vec<(usize, f64)>,
    idx: usize,
    count: usize,
    rebase_interval: usize,
    next_i: usize,
    anchor: usize,
    offset: i64,
    output: QuadRegOutput,
    s: f64,
    su2: f64,
    vxx: f64,
    vuu: f64,
    sz: f64,
    sxz: f64,
    sx2z: f64,
    szz: f64,
}

impl QuadRegFilter {
    pub fn new(
        period: i64,
        offset: i64,
        rebase_interval: Option<i64>,
        output: QuadRegOutput,
    ) -> Result<Self, String> {
        if period < 3 {
            return Err("QUADREG period must be >= 3".to_string());
        }
        if rebase_interval.is_some_and(|interval| interval < 0) {
            return Err("QUADREG rebase_interval must be >= 0 or None".to_string());
        }
        if offset != 0 && !matches!(output, QuadRegOutput::Forecast | QuadRegOutput::Slope) {
            return Err(
                "QUADREG offset is only valid when output='forecast' or output='slope'".to_string(),
            );
        }

        let s = period as f64;
        let half = (s - 1.0) / 2.0;
        let mut su2 = 0.0;
        let mut su4 = 0.0;
        for x in 0..period {
            let u = x as f64 - half;
            let u2 = u * u;
            su2 += u2;
            su4 += u2 * u2;
        }
        let vxx = su2 / s;
        let vuu = su4 / s - (su2 / s) * (su2 / s);

        Ok(Self {
            buffer: vec![(0, 0.0); period as usize],
            idx: 0,
            count: 0,
            rebase_interval: rebase_interval
                .unwrap_or_else(|| MIN_REBASE_INTERVAL.max(period.saturating_mul(2)))
                as usize,
            next_i: 0,
            anchor: 0,
            offset,
            output,
            s,
            su2,
            vxx,
            vuu,
            sz: 0.0,
            sxz: 0.0,
            sx2z: 0.0,
            szz: 0.0,
        })
    }

    fn reset(&mut self) {
        self.idx = 0;
        self.count = 0;
        self.clear_sums();
    }

    fn clear_sums(&mut self) {
        self.sz = 0.0;
        self.sxz = 0.0;
        self.sx2z = 0.0;
        self.szz = 0.0;
    }

    fn slide(&mut self, i: usize, value: f64) {
        let (tail_i, tail_value) = self.buffer[self.idx];
        self.sub(tail_i, tail_value);
        self.push(i, value);
        self.add(i, value);
    }

    fn push(&mut self, i: usize, value: f64) {
        if self.count == 0 {
            self.anchor = i;
        }
        if self.count < self.buffer.len() {
            self.count += 1;
        }

        self.buffer[self.idx] = (i, value);
        self.idx += 1;
        if self.idx == self.buffer.len() {
            self.idx = 0;
        }
    }

    fn add(&mut self, i: usize, z: f64) {
        let x = (i - self.anchor) as f64;
        self.sz += z;
        self.sxz += x * z;
        self.sx2z += x * x * z;
        self.szz += z * z;
    }

    fn sub(&mut self, i: usize, z: f64) {
        let x = (i - self.anchor) as f64;
        self.sz -= z;
        self.sxz -= x * z;
        self.sx2z -= x * x * z;
        self.szz -= z * z;
    }

    fn rebase_interval_reached(&self, i: usize) -> bool {
        self.rebase_interval > 0 && i - self.anchor >= self.rebase_interval
    }

    fn rebase_sums(&mut self) {
        if self.count == self.buffer.len() {
            self.clear_sums();
            self.anchor = self.buffer[self.idx].0;
            for idx in 0..self.buffer.len() {
                let (i, value) = self.buffer[idx];
                self.add(i, value);
            }
        }
    }
}

impl Filter for QuadRegFilter {
    type Input = Option<f64>;
    type Output = f64;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        let i = self.next_i;
        self.next_i += 1;

        let Some(value) = input else {
            self.reset();
            return None;
        };

        if self.count < self.buffer.len() {
            self.push(i, value);
            self.add(i, value);
        } else if self.rebase_interval_reached(i) {
            self.push(i, value);
            self.rebase_sums();
        } else {
            self.slide(i, value);
        }

        if self.count < self.buffer.len() {
            return None;
        }

        let half = (self.s - 1.0) / 2.0;
        let current_x = (i - self.anchor) as f64;
        let xbar = current_x - half;
        let suz = self.sxz - xbar * self.sz;
        let su2z = self.sx2z - 2.0 * xbar * self.sxz + xbar * xbar * self.sz;
        let slope = suz / self.s / self.vxx;
        let szz_r = self.szz - 2.0 * slope * suz + slope * slope * self.su2;
        let vuz = su2z / self.s - self.su2 * self.sz / self.s / self.s;
        let vzz = szz_r / self.s - self.sz * self.sz / self.s / self.s;
        let curve = vuz / self.vuu;
        let rvalue = if self.vuu * vzz > 0.0 {
            vuz / (self.vuu * vzz).sqrt()
        } else {
            f64::NAN
        };

        Some(match self.output {
            QuadRegOutput::Curve => curve,
            QuadRegOutput::Slope => {
                let x_end = half + self.offset as f64;
                slope + 2.0 * curve * x_end
            },
            QuadRegOutput::RValue => rvalue,
            QuadRegOutput::Rmse => (vzz * (1.0 - rvalue * rvalue).max(0.0)).sqrt(),
            QuadRegOutput::Forecast => {
                let alpha = self.sz / self.s - curve * self.su2 / self.s;
                let x_end = half + self.offset as f64;
                alpha + slope * x_end + curve * x_end * x_end
            },
        })
    }
}

fn quadreg(
    series: &Series,
    period: i64,
    offset: i64,
    rebase_interval: Option<i64>,
    output: QuadRegOutput,
) -> PolarsResult<Series> {
    let name = output.series_name();
    let filter = QuadRegFilter::new(period, offset, rebase_interval, output)
        .map_err(|e| PolarsError::InvalidOperation(e.into()))?;
    run_filter(series, name, filter)
}

#[polars_expr(output_type = Float64)]
fn quadreg_expr(inputs: &[Series], kwargs: QuadRegKwargs) -> PolarsResult<Series> {
    quadreg(
        &inputs[0],
        kwargs.period,
        kwargs.offset,
        kwargs.rebase_interval,
        kwargs.output,
    )
}

/// Rolling quadratic regression statistic.
///
/// Args:
///     series: input values.
///     period: regression-window length (default 20; minimum 3).
///     offset: projection offset (default 0); nonzero values require output="forecast"
///         or output="slope".
///     rebase_interval: maximum bar span for incrementally maintained sums before
///         rebasing from the current window. None selects max(1000, 2 * period);
///         0 disables rebasing.
///     output: statistic to return: "forecast", "curve", "slope", "rvalue", or "rmse".
///
/// Returns:
///     A Float64 series; null during warmup and after a null resets the window.
#[pyfunction]
#[pyo3(name = "quadreg", signature = (series, period=20, offset=0, rebase_interval=None, *, output="forecast"))]
pub fn quadreg_py(
    series: PySeries,
    period: i64,
    offset: i64,
    rebase_interval: Option<i64>,
    output: &str,
) -> PyResult<PySeries> {
    let series: Series = series.into();
    let output = output.parse::<QuadRegOutput>().map_err(PyPolarsErr::from)?;
    let result =
        quadreg(&series, period, offset, rebase_interval, output).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rebase_discards_history_before_the_current_window() {
        let mut filter = QuadRegFilter::new(3, 0, Some(4), QuadRegOutput::Forecast).unwrap();
        for value in [1.0, 4.0, 9.0, 16.0] {
            filter.next(Some(value));
        }

        filter.next(Some(25.0));
        assert_eq!(filter.next_i - filter.anchor, 3);
        assert_eq!(filter.buffer, vec![(3, 16.0), (4, 25.0), (2, 9.0)]);
        assert_eq!(filter.idx, 2);
        assert_eq!(filter.sxz, 66.0);
        assert_eq!(filter.sx2z, 116.0);
    }

    #[test]
    fn automatic_rebase_interval_scales_with_period() {
        let short = QuadRegFilter::new(20, 0, None, QuadRegOutput::Forecast).unwrap();
        let long = QuadRegFilter::new(600, 0, None, QuadRegOutput::Forecast).unwrap();

        assert_eq!(short.rebase_interval, 1000);
        assert_eq!(long.rebase_interval, 1200);
    }
}
