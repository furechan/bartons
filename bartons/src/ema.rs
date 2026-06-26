
// Version 49 — renamed compute_ema to raw_ema
// Architecture: Copy (i64), single-state EMA, nulls from NaNs via from_vec_validity

// :dep polars = "0.39"
// :dep serde = { version = "1.0", features = ["derive"] }

// For plugin usage, uncomment:

use pyo3::prelude::*;
use polars::prelude::*;
use serde::Deserialize;
use pyo3_polars::PySeries;
use pyo3_polars::derive::polars_expr;
use pyo3::exceptions::PyRuntimeError;

#[derive(Deserialize)]
pub struct EmaKwargs {
    period: i64,
}


fn calc_ema(series: &Series, period: i64) -> PolarsResult<Series> {
    let series = series.cast(&DataType::Float64)?;
    let ca = series.f64().unwrap();
    let len = ca.len();
    let name = "ema";

    if period <= 0 {
        return Err(PolarsError::ComputeError("EMA period must be > 0".into()));
    }

    let alpha = 2.0 / (period as f64 + 1.0);
    let mut ema: f64 = f64::NAN;
    let mut count: i64 = 0;
    let mut out = vec![f64::NAN; len];

    for (i, opt_val) in ca.into_iter().enumerate() {
        let val = opt_val.unwrap_or(f64::NAN);

        if val.is_nan() {
            ema = f64::NAN;
            count = 0;
        } else if ema.is_nan() {
            ema = val;
            count = 1;
        } else {
            ema += alpha * (val - ema);
            count += 1;
        }

        if count >= period {
            out[i] = ema;
        }
    }

    // Convert NaNs in `out` to nulls using a validity bitmap
    let validity = out.iter().map(|v| !v.is_nan()).collect::<Vec<bool>>();
    let output = Float64Chunked::from_vec_validity(name.into(), out, Some(validity.into())).into_series();

    Ok(output)
}

#[polars_expr(output_type = Float64)]
fn ema_expr(inputs: &[Series], kwargs: EmaKwargs) -> PolarsResult<Series> {
    calc_ema(&inputs[0], kwargs.period)
}

#[pyfunction]
#[pyo3(signature = (series, *, period=20))]
pub fn ema(series: PySeries, period: i64) -> PyResult<PySeries> {
    let series: Series = series.into();

    let result = match calc_ema(&series, period) {
        Ok(s) => s,
        Err(e) => return Err(PyRuntimeError::new_err(e.to_string())),
    };

    let result: PySeries = PySeries(result);
    Ok(result)
}
