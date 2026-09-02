use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;
use serde::Deserialize;

use crate::utils::{run_filter, Filter};

#[derive(Deserialize)]
pub struct StepKwargs {
    threshold: f64,
}

/// Limit the absolute change in a series to `threshold` per row.
///
/// The first valid value seeds the state and emits null. Each later output
/// moves from the previous output toward the current input by at most the
/// threshold. Null and NaN inputs emit themselves without changing the state.
pub struct StepFilter {
    threshold: f64,
    previous: Option<f64>,
}

impl StepFilter {
    pub fn new(threshold: f64) -> Result<Self, String> {
        if !threshold.is_finite() || threshold < 0.0 {
            return Err("STEP threshold must be finite and >= 0".to_string());
        }
        Ok(Self {
            threshold,
            previous: None,
        })
    }
}

impl Filter for StepFilter {
    type Input = Option<f64>;
    type Output = f64;

    fn next(&mut self, input: Option<f64>) -> Option<f64> {
        let value = input?;
        if value.is_nan() {
            return Some(value);
        }

        let Some(previous) = self.previous else {
            self.previous = Some(value);
            return None;
        };

        let change = value - previous;
        let output = if change > self.threshold {
            previous + self.threshold
        } else if change < -self.threshold {
            previous - self.threshold
        } else {
            value
        };
        self.previous = Some(output);
        Some(output)
    }
}

fn step(series: &Series, threshold: f64) -> PolarsResult<Series> {
    let filter =
        StepFilter::new(threshold).map_err(|error| PolarsError::InvalidOperation(error.into()))?;
    run_filter(series, "step", filter)
}

#[polars_expr(output_type = Float64)]
fn step_expr(inputs: &[Series], kwargs: StepKwargs) -> PolarsResult<Series> {
    step(&inputs[0], kwargs.threshold)
}

/// Limit the absolute change in a series per row.
///
/// Args:
///     series: input values.
///     threshold: maximum absolute change per row (default 1.0).
///
/// Returns:
///     A Float64 series. The first finite value is null; later null and NaN
///     inputs emit themselves without changing the running state.
#[pyfunction]
#[pyo3(name = "step", signature = (series, *, threshold=1.0))]
pub fn step_py(series: PySeries, threshold: f64) -> PyResult<PySeries> {
    let series: Series = series.into();
    let result = step(&series, threshold).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn limits_each_change_from_the_previous_output() {
        let mut filter = StepFilter::new(1.0).unwrap();
        let output: Vec<_> = [0.0, 3.2, 3.8, 4.3, 1.0, -2.5]
            .into_iter()
            .map(|value| filter.next(Some(value)))
            .collect();
        assert_eq!(
            output,
            vec![None, Some(1.0), Some(2.0), Some(3.0), Some(2.0), Some(1.0)]
        );
    }

    #[test]
    fn null_and_nan_skip_without_changing_state() {
        let mut filter = StepFilter::new(0.5).unwrap();
        let output = [
            Some(1.0),
            Some(2.0),
            None,
            Some(4.0),
            Some(5.0),
            Some(f64::NAN),
            Some(7.0),
            Some(8.0),
        ]
        .into_iter()
        .map(|value| filter.next(value))
        .collect::<Vec<_>>();
        assert_eq!(&output[..5], &[None, Some(1.5), None, Some(2.0), Some(2.5)]);
        assert!(output[5].is_some_and(f64::is_nan));
        assert_eq!(&output[6..], &[Some(3.0), Some(3.5)]);
    }
}
