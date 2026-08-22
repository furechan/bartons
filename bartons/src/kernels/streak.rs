use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::derive::polars_expr;
use pyo3_polars::error::PyPolarsErr;
use pyo3_polars::PySeries;

use crate::utils::{run_filter, Filter};

/// Count consecutive true values.
///
/// False and null both reset the count and emit zero. Treating null as not true
/// makes predicates built from `diff` start naturally at zero.
#[derive(Default)]
pub struct StreakFilter {
    count: i64,
}

impl StreakFilter {
    pub fn new() -> Self {
        Self::default()
    }
}

impl Filter for StreakFilter {
    type Input = Option<bool>;
    type Output = i64;

    fn next(&mut self, input: Option<bool>) -> Option<i64> {
        if input == Some(true) {
            self.count += 1;
        } else {
            self.count = 0;
        }
        Some(self.count)
    }
}

fn streak(series: &Series) -> PolarsResult<Series> {
    run_filter(series, "streak", StreakFilter::new())
}

#[polars_expr(output_type = Int64)]
fn streak_expr(inputs: &[Series]) -> PolarsResult<Series> {
    streak(&inputs[0])
}

/// Count consecutive true values.
///
/// Args:
///     series: Boolean input values; false and null reset the count.
///
/// Returns:
///     A non-null Int64 series starting at one within each true run and zero
///     otherwise.
#[pyfunction]
#[pyo3(name = "streak", signature = (series,))]
pub fn streak_py(series: PySeries) -> PyResult<PySeries> {
    let series: Series = series.into();
    let result = streak(&series).map_err(PyPolarsErr::from)?;
    Ok(PySeries(result))
}
