use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use crate::utils::{run_filter, Filter};

#[derive(Deserialize)]
pub struct ClagKwargs {
    period: i64,
}

/// Hold the last confirmed discrete state until a candidate repeats.
///
/// A value is confirmed after its first observation plus `period` repeats.
/// Null and NaN inputs emit themselves without changing the candidate, repeat
/// count, or confirmed state.
pub struct ClagFilter {
    period: usize,
    candidate: Option<f64>,
    repeats: usize,
    confirmed: Option<f64>,
}

impl ClagFilter {
    pub fn new(period: i64) -> Result<Self, String> {
        if period < 0 {
            return Err("CLAG period must be >= 0".to_string());
        }
        Ok(Self {
            period: period as usize,
            candidate: None,
            repeats: 0,
            confirmed: None,
        })
    }
}

impl Filter for ClagFilter {
    type Input = Option<f64>;
    type Output = f64;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        let value = input?;
        if value.is_nan() {
            return Some(value);
        }

        if self.candidate == Some(value) {
            self.repeats += 1;
        } else {
            self.candidate = Some(value);
            self.repeats = 0;
        }

        if self.repeats >= self.period {
            self.confirmed = Some(value);
        }
        self.confirmed
    }
}

fn clag(series: &Series, period: i64) -> PolarsResult<Series> {
    let filter =
        ClagFilter::new(period).map_err(|error| PolarsError::InvalidOperation(error.into()))?;
    run_filter(series, "clag", filter)
}

#[polars_expr(output_type = Float64)]
fn clag_expr(inputs: &[Series], kwargs: ClagKwargs) -> PolarsResult<Series> {
    clag(&inputs[0], kwargs.period)
}

/// Hold the last confirmed discrete state until a candidate repeats.
///
/// Args:
///     series: discrete numeric, integer, or Boolean input states.
///     period: required repeats after the first observation; zero is identity
///         (default 1).
///
/// Returns:
///     A Float64 series; null until the first state is confirmed.
#[pyfunction]
#[pyo3(name = "clag", signature = (series, *, period=1))]
pub fn clag_py(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();
    let result = clag(&series, period).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zero_period_is_identity() {
        let mut filter = ClagFilter::new(0).unwrap();
        let output = [Some(1.0), None, Some(-1.0), Some(f64::NAN), Some(0.5)]
            .into_iter()
            .map(|value| filter.next(value))
            .collect::<Vec<_>>();
        assert_eq!(&output[..3], &[Some(1.0), None, Some(-1.0)]);
        assert!(output[3].is_some_and(f64::is_nan));
        assert_eq!(output[4], Some(0.5));
    }

    #[test]
    fn confirms_after_the_required_repeats() {
        let mut filter = ClagFilter::new(1).unwrap();
        let output: Vec<_> = [1.0, 1.0, 2.0, 2.0, 3.0, 2.0, 2.0]
            .into_iter()
            .map(|value| filter.next(Some(value)))
            .collect();
        assert_eq!(
            output,
            vec![
                None,
                Some(1.0),
                Some(1.0),
                Some(2.0),
                Some(2.0),
                Some(2.0),
                Some(2.0)
            ]
        );
    }

    #[test]
    fn null_and_nan_skip_without_changing_confirmation() {
        let mut filter = ClagFilter::new(2).unwrap();
        let output = [
            Some(1.0),
            None,
            Some(1.0),
            Some(f64::NAN),
            Some(1.0),
            Some(2.0),
            None,
            Some(2.0),
            Some(2.0),
        ]
        .into_iter()
        .map(|value| filter.next(value))
        .collect::<Vec<_>>();
        assert_eq!(&output[..3], &[None, None, None]);
        assert!(output[3].is_some_and(f64::is_nan));
        assert_eq!(output[4], Some(1.0));
        assert_eq!(&output[5..], &[Some(1.0), None, Some(1.0), Some(2.0)]);
    }
}
