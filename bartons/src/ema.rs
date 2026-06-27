
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
    let ca = series.f64()?;
    let len = ca.len();
    let name = "ema";

    if period <= 0 {
        return Err(PolarsError::ComputeError("EMA period must be > 0".into()));
    }

    let alpha = 2.0 / (period as f64 + 1.0);
    let mut ema: f64 = f64::NAN;
    let mut count: i64 = 0;
    let mut builder = PrimitiveChunkedBuilder::<Float64Type>::new(name.into(), len);

    for opt_val in ca.iter() {
        // A null breaks the current run: reset, emit null, and continue.
        let Some(val) = opt_val else {
            ema = f64::NAN;
            count = 0;
            builder.append_null();
            continue;
        };

        if count == 0 {
            ema = val;
        } else {
            ema += alpha * (val - ema);
        }
        count += 1;

        // Warmup period emits null; otherwise the running EMA value.
        if count >= period {
            builder.append_value(ema);
        } else {
            builder.append_null();
        }
    }

    let output = builder.finish().into_series();

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
